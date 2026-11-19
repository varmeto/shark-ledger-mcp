"""Local stdio MCP server for supervised Android UI capture."""
import atexit
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

os.umask(0o077)
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('shark-ledger-extractor')
ROOT = Path(os.environ.get('SHARK_DATA_DIR', '~/.local/share/shark-ledger-mcp')).expanduser().resolve()
HERE = Path(__file__).resolve().parent
_lock = threading.Lock()
_job = {'process': None, 'started': None, 'kind': None, 'output_dir': None}


def command(args, timeout=15):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=True)


def child_path(value):
    candidate = (ROOT / value).resolve()
    if candidate == ROOT or ROOT not in candidate.parents:
        raise ValueError('Path must be inside SHARK_DATA_DIR and cannot be the root itself.')
    return candidate


def device(serial):
    if not re.fullmatch(r'[a-zA-Z0-9._:-]{1,128}', serial):
        raise ValueError('Invalid ADB device serial.')
    return ['adb', '-s', serial]


@mcp.tool()
def diagnose(serial: str) -> dict:
    """Check ADB connection, app version, screen size and foreground app without reading ledger data."""
    try:
        adb = device(serial)
        state = command(adb + ['get-state']).stdout.strip()
        size = command(adb + ['shell', 'wm', 'size']).stdout.strip()
        package = command(adb + ['shell', 'dumpsys', 'package', 'com.shark.jizhang']).stdout
        focus = command(adb + ['shell', 'dumpsys', 'window']).stdout
        version = re.search(r'versionName=([^\s]+)', package)
        foreground = any('mCurrentFocus=Window' in line and 'com.shark.jizhang/' in line for line in focus.splitlines())
        return {'state': state, 'screen': size, 'app_version': version.group(1) if version else None,
                'app_foreground': foreground, 'supported_screen': '1916x2160' in size and ('Override size:' not in size or 'Override size: 1916x2160' in size),
                'tested_version': version is not None and version.group(1) == '5.86.1',
                'note': 'Quick edit and list position require manual confirmation. Other versions are unverified.'}
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        return {'error': type(e).__name__, 'message': 'Could not inspect device. Check ADB, authorization and connection.'}


@mcp.tool()
def start_month_capture(serial: str, output_name: str, quick_edit_disabled: bool, at_month_top: bool) -> dict:
    """Start supervised capture of the current month; set both confirmations only after checking the phone. Does not change settings."""
    if not quick_edit_disabled or not at_month_top:
        return {'error': 'Disable quick edit and verify the current month list is at the top before capture.'}
    try:
        device(serial)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', output_name):
            raise ValueError('Use a simple output name.')
        ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
        dest = child_path(output_name)
        with _lock:
            proc = _job['process']
            if proc is not None and proc.poll() is None:
                return {'error': 'A capture is already running.'}
            dest.mkdir(mode=0o700, parents=True, exist_ok=False)
            os.chmod(dest, 0o700)
            log = dest / 'capture.log'
            with log.open('x', encoding='utf-8') as handle:
                os.chmod(log, 0o600)
                proc = subprocess.Popen([sys.executable, str(HERE / 'collect.py'), '--serial', serial, '--output', str(dest)],
                                        stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT)
            _job.update(process=proc, started=time.time(), kind='month_capture', output_dir=dest)
        return {'state': 'running', 'output_name': output_name, 'note': 'Use capture_status to monitor. Do not touch the phone.'}
    except (ValueError, OSError) as e:
        return {'error': type(e).__name__, 'message': 'Could not start capture. Choose a new output_name under the configured data directory.'}


@mcp.tool()
def capture_status() -> dict:
    """Report capture progress without returning private transaction contents."""
    with _lock:
        proc = _job['process']
        if proc is None:
            return {'state': 'idle'}
        code = proc.poll()
        files = list(_job['output_dir'].glob('*/detail-*.xml'))
        return {'state': 'running' if code is None else ('completed' if code == 0 else 'failed'),
                'exit_code': code, 'details_saved': len(files), 'elapsed_seconds': round(time.time()-_job['started']),
                'output_name': str(_job['output_dir'].relative_to(ROOT)),
                'capture_paths': [str(p.relative_to(ROOT)) for p in _job['output_dir'].glob('*/records.json')],
                'note': 'Exit 0 means monthly sums matched; not proof of completeness. Inspect records.json and the private capture.log; compare record counts.'}


@mcp.tool()
def cancel_capture() -> dict:
    """Stop the running capture; already captured files are kept for manual review."""
    with _lock:
        proc = _job['process']
        if proc is None or proc.poll() is not None:
            return {'state': 'idle'}
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        return {'state': 'stopped', 'note': 'Partial files retained; do not treat the batch as complete.'}


@mcp.tool()
def export_csv(capture_paths: list[str], output_name: str) -> dict:
    """Export verified monthly records.json files inside SHARK_DATA_DIR to a new CSV within that directory."""
    try:
        if not capture_paths: raise ValueError('No captures provided')
        paths = [child_path(p) for p in capture_paths]
        if any(p.name != 'records.json' for p in paths): raise ValueError('Only records.json inputs are accepted')
        target = child_path(output_name)
        if target.suffix.lower() != '.csv': raise ValueError('Output must end in .csv')
        if not target.parent.is_dir(): raise ValueError('Output parent must already exist')
        proc = subprocess.run([sys.executable, str(HERE/'export.py'), *map(str, paths), '--output', str(target)],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode:
            return {'state': 'failed', 'message': 'Export rejected. Check that each month is complete, unique, warning-free and totals match; target must not exist.'}
        return {'state': 'completed', 'output_name': output_name, 'message': 'CSV saved locally; independently verify scope and total count.'}
    except (ValueError, OSError, subprocess.SubprocessError):
        return {'state': 'failed', 'message': 'Invalid path or export failure. All paths must be within SHARK_DATA_DIR.'}

def _shutdown():
    proc = _job['process']
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

atexit.register(_shutdown)

def _terminate(signum, frame):
    _shutdown()
    raise SystemExit(128 + signum)

if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, _terminate)

if __name__ == '__main__':
    mcp.run(transport='stdio')

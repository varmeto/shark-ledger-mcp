import subprocess
import sys
import unittest
from unittest.mock import patch
import server

class ServerTest(unittest.TestCase):
 def test_cancel_stops_process(self):
  proc=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
  try:
   with patch.dict(server._job,{'process':proc}):
    self.assertEqual(server.cancel_capture()['state'],'stopped')
    self.assertIsNotNone(proc.poll())
  finally:
   if proc.poll() is None: proc.kill();proc.wait()
 def test_shutdown_stops_process(self):
  proc=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
  try:
   with patch.dict(server._job,{'process':proc}):
    server._shutdown()
    self.assertIsNotNone(proc.poll())
  finally:
   if proc.poll() is None: proc.kill();proc.wait()

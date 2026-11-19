# Shark Ledger MCP / 鲨鱼记账 MCP

A local MCP server for agents to capture visible Android bookkeeping details, check monthly totals, and export verified batches as CSV. No VIP or root required. 通过手机界面采集账目，不连接或破解应用的服务器接口。

## 适用范围

实验版：仅在 Android 鲨鱼记账 5.86.1、vivo V2229A、1916×2160 屏幕实机验证。界面坐标和元素结构随设备、屏幕设置或应用版本可能改变；程序会拒绝未验证的版本和尺寸。它不具备通用设备支持。

详情页中看不到的字段（例如账户、标签、图片）不能保证采到。程序只读取用户手动选择的账本和月份，不自动搜索其他账号、账本或未同步记录。截图、账目数据和日志不会被本工具上传，但 MCP 客户端或 agent 的日志、上下文和备份策略不受本服务控制。

## 安装与连接

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/) 和 [Android platform-tools / adb](https://developer.android.com/tools/releases/platform-tools)。下载此仓库后，将下面配置中的路径替换为本机实际绝对路径，再加入支持 stdio MCP 的 agent 配置：

```json
{
  "mcpServers": {
    "shark-ledger": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/shark-ledger-mcp", "python", "server.py"],
      "env": {"SHARK_DATA_DIR": "/absolute/path/to/private-data"}
    }
  }
}
```

`SHARK_DATA_DIR` 是本地私人数据目录；省略时默认为 `~/.local/share/shark-ledger-mcp`。不要将它放在公开仓库内。MCP 只使用本地 stdio，不打开网络端口。

## 使用

先用 `adb devices -l` 取得设备序列号，解锁手机，打开应用。在设置中关闭“快捷编辑”，手动选择目标主账本月份，并将列表滚动到该月最上方。每月采集前都需要检查这两项；使用后恢复设置。采集期间不要操作手机。

提供五个 MCP 工具：

- `diagnose(serial)`：检查 ADB、应用版本、前台状态和屏幕尺寸，不读取账目。
- `start_month_capture(serial, output_name, quick_edit_disabled, at_month_top)`：确认快捷编辑已关闭、列表位于顶部后启动采集；`output_name` 是新的简单目录名。
- `capture_status()`：查询运行状态、已保存详情数和本地批次路径。私有 `capture.log` 可协助排错。
- `cancel_capture()`：停止采集并保留已保存的部分结果。
- `export_csv(capture_paths, output_name)`：将已核对的 `records.json` 转换为新 CSV；路径均相对于 `SHARK_DATA_DIR`。

采集器会点击账目、返回和滚动，每笔保存详情 XML 与 JSON。它不会自动切换月份或管理设置。同月重复采集、中断续采需要人工核对重叠；导出器拒绝同月多批和不完整、未通过金额复核的批次，不会覆盖已有 CSV。

月度金额一致不代表完整性得到证明：重复与遗漏可能抵消，同金额记录也可能混淆。请额外核对应用总笔数、全部账本、日期范围及所需字段。采集异常或界面变化时停止操作，不要自动点击编辑、删除或分享。

## 隐私与开发

数据、原始 XML、日志和导出物均为敏感信息。`.gitignore` 只是辅助保护；发布前仍须检查待提交文件、历史记录和日志，确保没有真实数据、设备序列号、令牌或本地路径。

```sh
uv sync
uv run python -m unittest -v
```

此项目是独立工具，与鲨鱼记账官方无关联。开源许可证见 `LICENSE`。

# 鲨鱼记账 MCP

一个给 AI agent 使用的本地账目采集工具。它通过 Android 调试接口读取鲨鱼记账应用中可见的账目详情，按月核对收入和支出，再导出 CSV，方便用 Excel、WPS 或其他工具查看。

如果你的账目留在鲨鱼记账里，希望让支持 MCP 的 agent 协助备份，这个项目提供了一条不用 VIP 导出功能、不需要 root 的方式。它操作手机上已经登录的应用界面；本工具不调用鲨鱼记账的服务端接口。

**目前是实验版，不是通用的一键迁移工具。** 已实机验证的环境只有：Android 版鲨鱼记账 **5.86.1**、vivo V2229A、**1916 × 2160** 屏幕。工具会拒绝其他应用版本或屏幕尺寸；即使尺寸相同，其他设备的界面布局也可能不同，使用前应先用少量数据验证。

## 能做什么

- 让 agent 检查手机连接、应用版本和屏幕尺寸。
- 读取当前选中月份的可见账目，包括日期、收支类型、分类、金额以及详情页显示的备注。
- 每读取一笔就保存原始界面数据，并将当月采集金额与应用显示的月度收入、支出核对。
- 将通过检查的月份导出为 CSV；中断或失败时保留已采集内容供排查。

每次只处理**当前选择的一个月**。你需要手动切换月份和账本、确认列表处于顶部，并在采集前关闭应用里的“快捷编辑”。工具不会自动覆盖已有导出文件。

月度金额相同并不能单独证明所有记录都采全：遗漏与重复可能抵消，同金额记录也可能混淆。请另外核对日期范围、应用总笔数和各账本。详情页没显示的账户、标签、图片等内容，以及其他账号或未同步的数据，不能保证包含在结果中。

## 准备

1. 在电脑上安装 Python 3.11 或更新版本、[uv](https://docs.astral.sh/uv/) 和 [Android platform-tools（adb）](https://developer.android.com/tools/releases/platform-tools)。
2. 克隆仓库，记下本地目录的绝对路径：

   ```sh
   git clone https://github.com/varmeto/shark-ledger-mcp.git
   ```

3. 在 Android 手机上开启开发者选项和 USB 调试，连接电脑并在手机上批准调试授权。也可以使用已配对的无线调试。
4. 在电脑运行 `adb devices -l`，确认目标设备状态为 `device`。解锁手机并打开鲨鱼记账。

## 连接你的 AI agent

将以下示例加入支持 **stdio MCP** 的客户端配置。把两个路径改成你电脑上实际存在的位置；配置文件的位置和格式请以所用客户端的文档为准。

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

Windows 用户应将示例路径改为本机的绝对路径，并按 JSON 规则转义反斜杠；目前 Windows 尚未实机验证。如果客户端找不到 `uv`，可在 `command` 中填写 `uv` 可执行文件的绝对路径。首次运行可能需要下载 Python 依赖。

`SHARK_DATA_DIR` 是保存私人数据的目录；省略时默认为 `~/.local/share/shark-ledger-mcp`。请把它放在仓库之外。服务使用本地 stdio，不会自己打开网络端口。

## 采集一份账单

1. 在鲨鱼记账设置中关闭“快捷编辑”。此功能开启时，点击列表可能进入编辑界面。
2. 打开你要采集的主账本和月份，**手动把账目列表滚到该月最上方**。
3. 告诉 agent，例如：“请用鲨鱼记账 MCP 检查手机连接，采集当前月份并导出 CSV。快捷编辑已关闭，列表已在顶部。” agent 会使用 `diagnose` 和 `start_month_capture`。
4. 采集时不要操作手机。agent 可以通过 `capture_status` 查看进度；需要停止时可调用 `cancel_capture`。每笔详情的原始 XML 和 JSON 保存在私人数据目录中。
5. 检查采集状态和 `records.json`；对下一个月重复上述步骤。完成后恢复“快捷编辑”原来的设置。
6. 使用 `export_csv` 导出已通过核对的月份，并对照应用检查总笔数和范围。导出的 CSV 可用 Excel 或 WPS 打开。

采集器会模拟点击账目、返回和滚动；如果详情与列表不匹配、月份发生变化或金额核对失败，应停止并检查。**请勿让 agent 自动点击应用里的编辑、删除或分享。**

## MCP 工具

| 工具 | 用途 |
| --- | --- |
| `diagnose(serial)` | 检查 ADB、应用版本、前台状态和屏幕尺寸，不读取账目。 |
| `start_month_capture(serial, output_name, quick_edit_disabled, at_month_top)` | 开始采集当前月；两个布尔值只能在手机上确认后设为 `true`。`output_name` 必须是尚不存在的简单目录名。 |
| `capture_status()` | 查看进度和相对于数据目录的批次路径；私有 `capture.log` 可用于排错。 |
| `cancel_capture()` | 停止采集，保留已保存的部分结果。 |
| `export_csv(capture_paths, output_name)` | 将通过核对的 `records.json` 导出为新 CSV；所有路径相对于 `SHARK_DATA_DIR`。 |

中断后不会自动从断点续跑。同一个月多次采集时，需要人工核对重叠；导出器会拒绝同月多批、未完成、有警告或金额不匹配的批次。

## 隐私与排错

账目、原始 XML、日志和 CSV 都可能包含敏感信息。工具本身只将数据写入本地，但所用 agent 或 MCP 客户端的日志、对话上下文和备份策略不由本项目控制。不要把真实数据、设备序列号、令牌或截图提交到公开仓库。

连接失败时先运行 `adb devices -l` 检查授权和连接，再调用 `diagnose`。检查应用版本、屏幕尺寸、前台页面、列表位置和“快捷编辑”状态。采集日志位于对应批次目录下的 `capture.log`；分享日志前请自行检查并删除个人信息。

开发者可运行：

```sh
uv sync
uv run python -m unittest -v
```

本项目是独立工具，与鲨鱼记账官方无关联。开源许可证见 [LICENSE](LICENSE)。

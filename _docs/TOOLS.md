# 第三方工具来源与微信 4.1 说明

本项目把外部工具统一放在 `tools/`。`src/` 是本项目自己写的代码。

## WeChatDecrypt

- 仓库: https://github.com/ylytdeng/wechat-decrypt
- 本地路径: `tools/wechat-decrypt/`
- 用途: 数据库结构、MCP Server、图片/语音等微信数据处理工具。
- 当前项目使用: `key_scan_common.py` 的数据库枚举能力、`config.py` 的配置约定、`mcp_server.py` 的交互查询能力。
- 现状: 它自带的 Windows 内存扫描入口在当前测试环境下没有扫到微信 4.1 密钥，但解密生态和 MCP 仍然有用。

## wx_key

- 仓库: https://github.com/ycccccccy/wx_key
- Release: https://github.com/ycccccccy/wx_key/releases/tag/v2.1.8
- 本地路径: `tools/wx_key/`
- 用途: Windows 上从正在运行的 `Weixin.exe` 进程提取 64 位 hex `raw_key`。
- 当前状态: 仓库已归档。
- 安装方式: 从 Release 下载 Windows 压缩包并解压到 `tools/wx_key/`，本仓库不提交 `wx_key.exe`。

### 是否支持命令行自动输出

本地测试过：

```bat
tools\wx_key\wx_key.exe --help
tools\wx_key\wx_key.exe -h
```

没有命令行帮助或 stdout 输出。上游 README 也只说明解压后运行 `wx_key.exe`，没有记录 CLI 参数。

`wx_key` 包里带有 `data/flutter_assets/assets/dll/wx_key.dll`，上游文档提到 DLL 调用方式，因此理论上可以继续写一个自动化封装器。但当前项目暂时不假设 `wx_key.exe` 能无界面自动输出 raw_key。

## 微信 4.0 / 4.1 的选择

网上很多工具主要覆盖微信 4.0 或更早版本。当前测试环境是微信 4.1，实测结果是：

- WeChatDecrypt 自带 `find_all_keys_windows.py` / `app_gui.py --task decrypt`: 没扫到密钥。
- wx_key v2.1.8: 成功提取 raw_key。
- WeChatDecrypt 的数据库解密、MCP、图片/语音生态: 仍可复用。

所以当前方案不是“只能用 wx_key”，而是：

```text
wx_key 负责提取微信 4.1 raw_key
WeChatDecrypt 负责复用解密生态和 MCP 能力
本项目 src/scripts 负责把二者串起来
```

如果以后 WeChatDecrypt 或其他工具重新支持微信 4.1 的自动密钥提取，可以替换密钥提取这一步。

## 试过但未采用

- wx-cli: https://github.com/jackwener/wx-cli
- chatlog_alpha: https://github.com/lqzhgood/chatlog_alpha
- vchat: https://github.com/lqzhgood/vchat

详细测试过程见 [BLOG.md](BLOG.md)。

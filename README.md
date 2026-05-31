# 微信聊天记录分析工具

本地 Windows 工具：提取微信 4.1 密钥 -> 解密数据库 -> 查询群聊 -> 生成日报。

当前实测方案：

```text
wx_key 提取 raw_key
WeChatDecrypt 复用数据库/MCP/图片语音能力
wechat.py 把流程串起来
```

## 目录结构

```text
wechat-analysis/
├── wechat.py              # 唯一 Python 主入口
├── run_report.ps1         # 双击/手动运行默认日报
├── config.example.jsonc    # 配置模板
├── config.jsonc            # 本地真实配置，gitignore
├── README.md
├── requirements.txt
├── docs/
│   ├── BLOG.md
│   └── TOOLS.md
├── src/                   # 本项目代码，直接平铺
│   ├── decrypt.py
│   ├── keys.py
│   ├── paths.py
│   └── query.py
├── tools/                 # 外部工具
│   ├── wx_key/
│   └── wechat-decrypt/
└── export/                # 本地输出，gitignore
    ├── all_keys.json
    ├── decrypted/
    ├── reports/
    └── logs/
```

真实配置放根目录 `config.jsonc`。WeChatDecrypt 自己的配置由 `wechat.py setup` 自动生成到 `tools/wechat-decrypt/config.json`；密钥和输出都在 `export/`。

## 安装

```bash
git submodule update --init --recursive
pip install -r requirements.txt
```

复制配置模板：

```bat
copy config.example.jsonc config.jsonc
```

## 第一次使用

1. 微信保持登录运行。

2. 打开 wx_key：

```bat
tools\wx_key\wx_key.exe
```

`wx_key` 不提交到本仓库。到 [wx_key v2.1.8 Release](https://github.com/ycccccccy/wx_key/releases/tag/v2.1.8) 下载 Windows 压缩包，解压到 `tools/wx_key/`，保证本地存在 `tools\wx_key\wx_key.exe`。

目前没有确认 `wx_key.exe` 支持命令行自动输出，所以短期需要手动复制它显示的 64 位 hex `raw_key`。

3. 初始化项目：

```bash
python wechat.py setup --raw-key <wx_key输出的64位hex>
```

这个命令会自动检测微信 `db_storage`，写 `tools/wechat-decrypt/config.json`，并生成 `export/all_keys.json`。

如果自动检测失败：

```bash
python wechat.py setup --raw-key <raw_key> --db-dir "D:\path\to\xwechat_files\your_wxid\db_storage"
```

4. 解密数据库：

```bash
python wechat.py decrypt
```

输出在 `export/decrypted/`。

## 日常使用

列出群聊：

```bash
python wechat.py groups
```

生成默认群今天的日报：

```bash
python wechat.py report
```

指定日期和群：

```bash
python wechat.py report --date 2026-05-30 --groups 家,.NET性能优化
```

不调用 LLM，只看消息样本：

```bash
python wechat.py report --dry-run
```

报告输出在 `export/reports/`。

默认群在 `config.jsonc` 里改：

```json
{
  "default_groups": [
    "家",
    ".NET性能优化",
    "西安爱翔股份有钱公司"
  ]
}
```

成员名称显示也在 `config.jsonc` 里改：

```json
{
  "display_name_mode": "remark"
}
```

- `remark`：优先显示你的联系人备注。
- `nickname`：优先显示对方自己的微信昵称。

## 一键运行

手动点这个 PowerShell 脚本即可生成默认日报：

```powershell
powershell -ExecutionPolicy Bypass -File run_report.ps1
```

也可以带参数：

```powershell
powershell -ExecutionPolicy Bypass -File run_report.ps1 --date 2026-05-30 --groups 家
```

不带参数时，`run_report.ps1` 会读取 `config.jsonc` 中的默认群。

## LLM

`wechat.py report` 直接读取 `config.jsonc` 并通过 LiteLLM 调 Anthropic-compatible API，不调用 Claude Code CLI，也不依赖 `LITELLM_*` 环境变量。

模型、base URL、API key 都在 `config.jsonc`。LLM 调用使用 LiteLLM：

```json
{
  "llm": {
    "auth_token": "replace_with_your_api_key",
    "base_url": "https://api.deepseek.com/anthropic",
    "model": "anthropic/deepseek-v4-flash"
  }
}
```

`anthropic/` 是 LiteLLM 的协议/provider 前缀，表示走 DeepSeek 的 Anthropic-compatible endpoint，不代表请求发到 Anthropic。实际请求地址仍由 `base_url` 决定。

速度建议：

- `anthropic/deepseek-v4-flash`：更快，适合日常日报。
- `anthropic/deepseek-v4-pro`：质量可能更好，但 reasoning 会明显更慢。

也可以配置请求控制：

```jsonc
{
  "llm": {
    "timeout": 90,
    "num_retries": 0
  }
}
```

`num_retries: 0` 表示禁用 LiteLLM 隐式重试，避免慢请求被隐藏放大。

不用 AI 时加 `--dry-run`。

报告会同时输出 Markdown 和 HTML。若本机安装了 Python Playwright 的 Chromium，会额外输出 PNG 图片；否则直接打开 HTML 也能看。

PNG 依赖：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

话题划分由大模型按固定 JSON 格式返回，代码只负责统计消息数、参与人数、时段分布等客观指标。`--dry-run` 不调用大模型，因此 HTML 中不会伪造热门话题，只显示未进行 AI 话题分析。

## Windows 定时任务

这是 Windows 自带任务计划程序。平时手动点 `run_report.ps1` 就不用配置。

```cmd
schtasks /create /tn "WeChatDailyReport" /tr "powershell -ExecutionPolicy Bypass -File D:\4_Code\0_Github_Project\wechat-analysis\run_report.ps1" /sc daily /st 22:00 /f
```

## MCP Server

Claude Code 项目级 `.mcp.json` 示例：

```json
{
  "mcpServers": {
    "wechat-decrypt": {
      "command": "python",
      "args": [
        "D:/4_Code/0_Github_Project/wechat-analysis/tools/wechat-decrypt/mcp_server.py"
      ],
      "env": {
        "WECHAT_DECRYPT_APP_DIR": "D:/4_Code/0_Github_Project/wechat-analysis/tools/wechat-decrypt"
      }
    }
  }
}
```

Codex 的 TOML 示例：

```toml
[mcp_servers.wechat-decrypt]
command = "python"
args = ["D:/4_Code/0_Github_Project/wechat-analysis/tools/wechat-decrypt/mcp_server.py"]

[mcp_servers.wechat-decrypt.env]
WECHAT_DECRYPT_APP_DIR = "D:/4_Code/0_Github_Project/wechat-analysis/tools/wechat-decrypt"
```

也可以用 Claude Code 命令注册项目级 MCP：

```bash
claude mcp add --scope project wechat-decrypt -- python D:/4_Code/0_Github_Project/wechat-analysis/tools/wechat-decrypt/mcp_server.py
```

## 致谢

本项目主要串联和改造了两个开源项目的能力：

- [WeChatDecrypt](https://github.com/ylytdeng/wechat-decrypt)：微信数据库解密、MCP Server、图片/语音等工具生态。本仓库通过 git submodule 指向它，不直接复制源码。
- [wx_key](https://github.com/ycccccccy/wx_key)：Windows 微信 4.1 环境下提取 raw_key。请从 [v2.1.8 Release](https://github.com/ycccccccy/wx_key/releases/tag/v2.1.8) 自行下载，本仓库不提交二进制文件。

可选工具：

- [wx-cli](https://github.com/jackwener/wx-cli)：可作为另一种微信数据访问/实验工具。当前项目主流程不依赖它；如需使用，按其 README 安装。

另外，日报视觉结构参考了 `tools/astrbot_plugin_qq_group_daily_analysis` 中的群日报模板思路。

## 敏感文件

不要提交：

- `config.jsonc`
- `export/`
- `tools/wechat-decrypt/config.json`
- `.mcp.json`
- `.mcp.json.local`


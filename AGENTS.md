# 仓库指南

## 项目结构

```
wechat-analysis/
├── wechat.py              # CLI 入口（argparse 子命令）
├── config.jsonc            # 本地配置（gitignore）
├── config.example.jsonc    # 配置模板
├── core-wechat/           # 微信核心 — 完全独立
│   ├── chat_platform.py   # 平台接口实现
│   ├── decrypt.py         # SQLCipher 4 解密
│   ├── keys.py            # raw_key → all_keys.json
│   ├── paths.py           # 输出路径常量
│   ├── query.py           # SQLite 查询、消息解析
│   ├── visual_report.py   # HTML/PNG 报告生成
│   ├── image_extract.py   # 群聊图片提取
│   └── wechat_sender.py   # 自动发送到微信群
├── core-wecom/            # 企业微信核心 — 完全独立
│   └── chat_platform.py   # 平台接口
├── core-dingtalk/         # 钉钉核心 — 完全独立
│   ├── chat_platform.py   # 平台接口
│   ├── find_uid.py        # 自动提取 UID
│   ├── decrypt.py         # AES-128-ECB 解密
│   └── export_all.py      # 数据导出
├── core-feishu/           # 飞书核心（预留）
├── shared/                # 共享组件
│   ├── platform_base.py   # 平台抽象基类
│   └── templates/         # HTML 报告模板（5种风格）
├── api/                   # 后端 API（FastAPI）
│   └── server.py
├── web/                   # 前端界面（Vue + Tailwind + Highcharts）
├── scripts/               # 辅助脚本
│   ├── run_git_pull.ps1
│   └── start_dev.ps1
├── tests/                 # 单元测试
├── tools/                 # 外部工具（git submodule）
├── export_parse_result/   # 输出目录（gitignore）
└── _docs/                 # 文档
```
wechat-analysis/
├── wechat.py              # CLI 入口（argparse 子命令）
├── config.jsonc            # 本地配置（gitignore）
├── config.example.jsonc    # 配置模板
├── core/                   # 核心解密逻辑
│   ├── paths.py            # 路径常量集中管理
│   ├── keys.py             # raw_key → all_keys.json
│   ├── decrypt.py          # 根据密钥解密数据库
│   ├── query.py            # SQLite 查询、发送者解析、消息解析
│   ├── visual_report.py    # HTML/PNG 报告生成
│   ├── image_extract.py    # 群聊图片提取
│   ├── wechat_sender.py    # 自动发送 PNG 到微信群
│   ├── platforms/          # 多平台支持
│   │   ├── __init__.py     # 平台注册表
│   │   ├── base.py         # 抽象基类
│   │   ├── wechat.py       # 微信
│   │   ├── wecom.py        # 企业微信
│   │   └── dingtalk.py     # 钉钉
│   └── templates/          # HTML 报告模板
├── api/                    # 后端 API（FastAPI）
│   ├── server.py           # API 路由
│   └── requirements.txt
├── web/                    # 前端界面（Vue + Tailwind + Highcharts）
│   └── src/
├── scripts/                # 辅助脚本
│   ├── tools/              # 可复用工具
│   │   └── find_dingtalk_uid.py
│   ├── run_git_pull.ps1
│   └── start_dev.ps1
├── tests/                  # 单元测试
├── tools/                  # 外部工具（git submodule）
│   ├── wechat-decrypt/     # 数据库解密 & MCP Server
│   └── wx_key_source_code/ # wx_key 源码
├── export/                 # 输出目录（gitignore）
└── _docs/                  # 文档
```

## 构建、测试与开发命令

```bash
# 初始化子模块
git submodule update --init --recursive

# 安装依赖
pip install -r requirements.txt

# 运行测试
python -m unittest discover tests

# 运行指定测试文件
python -m unittest tests.test_query
python -m unittest tests.test_wechat_report

# 列出群聊
python wechat.py groups

# 生成日报（默认群&日期）
python wechat.py report

# 指定日期和群
python wechat.py report --date 2026-05-30 --groups 家,.NET性能优化

# 不调 LLM 只看消息样本
python wechat.py report --dry-run

# 列出可用 HTML 模板
python wechat.py templates
```

## 编码规范

- **Python**：遵循 PEP 8，缩进 4 空格，行宽 ≤100 字符。
- **命名**：变量/函数用 `snake_case`，类用 `PascalCase`，常量用 `UPPER_SNAKE`。
- **注释**：高信号原则。解释意图、不变量、边界条件和反直觉行为。不写"这段代码做了什么"式的废话注释。
- **类型提示**：函数参数和返回值尽量标注类型。
- **格式化**：当前无自动格式化工具，提交前请自行保持风格一致。

## 测试规范

- **框架**：Python 标准库 `unittest`。
- **数据**：使用 `tempfile.TemporaryDirectory` + 内存 SQLite 构造测试 DB，不依赖真实微信数据。
- **路径隔离**：用 `unittest.mock.patch` 替换模块级路径常量（如 `REPORTS_DIR`），避免污染 `export/`。
- **命名**：测试类 `class XxxTests(unittest.TestCase)`，测试方法 `test_功能描述`。
- **运行**：`python -m unittest discover tests`。

## 提交与 PR 规范

- **提交信息**：用祈使句，首字母大写，不超过 72 字。推荐格式：
  - `fix: 修复 xxx 问题`
  - `feat: 新增 xxx 功能`
  - `refactor: 重构 xxx 模块`
  - `docs: 更新 README`
- **PR**：描述改了什么、为什么改、怎么验证。关联相关 Issue。涉及 UI 变化附截图。

## 安全与配置

- **永远不提交**：`config.jsonc`、`export/`、`tools/wechat-decrypt/config.json`、`.mcp.json`、`.mcp.json.local`、`all_keys.json`。
- **API Key**：只写在本地 `config.jsonc` 的 `llm.auth_token` 字段，不提交到仓库。
- **wx_key 二进制**：`tools/wx_key/wx_key.exe` 约 132MB，需从 Release 页面自行下载，不提交。

## 架构概览

### 数据流

```
wx_key.exe (手动/自动) → raw_key (64位hex)
       ↓
wechat.py setup → keys.py → export/all_keys.json
       ↓
wechat.py decrypt → decrypt.py → export_parse_result/decrypted_wechat/ (SQLite)
       ↓
wechat.py report → query.py (SQLite查询, 名称解析)
       ↓
visual_report.py → HTML/PNG 报告
```

### 关键设计决策

- **LLM 可选**：`--dry-run` 跳过所有 LLM 调用，只输出消息样本。`--skip-analysis` 保留已有分析结果。
- **名称解析管线**：`display_name_priority` 配置优先级链（群昵称 → 微信昵称 → 备注），逐级回退。
- **消息解析策略**：`query.py` 的 `_try_decode` / `_parse_content` 处理 zstd 压缩 protobuf、XML appmsg（引用回复、链接、文件）和纯文本。二进制媒体类型输出描述性标签。
- **模板是 Python 模块**：`src/templates/` 下每个模板导出一个 `render()` 函数。新增模板需创建新文件并在 `__init__.py` 注册。

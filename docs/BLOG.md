# 微信聊天记录分析 — 探索与实现全记录

> 目标：每天自动总结指定微信群的聊天内容，输出 Markdown 日报。
> 最终方案：WeChatDecrypt 提取密钥 → PBKDF2 解密 SQLite → 直接查库 → LLM 总结。

> 注：本文是探索过程记录，里面保留了当时的旧脚本名和旧路径。当前可执行命令以根目录 [README.md](../README.md) 为准。

## 一、选型：五款方案实测

需求很明确：定时自动总结微信群聊天内容。调研了以下方案，逐一测试：

### 1.1 wx-cli（Rust / npm）

- **地址**：[github.com/hxudot/wx-cli](https://github.com/hxudot/wx-cli)，3.1k Star
- **原理**：npm 全局安装，内存扫描 + daemon 常驻进程缓存
- **测试结果**：❌ 放弃
- **失败原因**：
  - 依赖 daemon 常驻进程，Windows 下不稳定
  - 对 WeChat 4.1 的 `message_content` 解析不完整，protobuf 格式消息大量丢失
  - 输出的是已经解析过的文本，无法控制解析逻辑，出现乱码时没法修

### 1.2 chatlog_alpha（Go）

- **地址**：[github.com/lqzhgood/chatlog_alpha](https://github.com/lqzhgood/chatlog_alpha)
- **原理**：Go 编译，内存扫描，带 Web UI 和语义搜索
- **测试结果**：❌ 放弃
- **失败原因**：
  - 主要面向 macOS，Windows 支持不完善
  - Web UI 功能花哨但核心导出不稳定，消息丢失严重
  - Go 的内存扫描在 WeChat 4.1 上命中率低

### 1.3 vchat（Python / macOS 为主）

- **地址**：[github.com/lqzhgood/vchat](https://github.com/lqzhgood/vchat)
- **原理**：Python + 原生 C 扫描，有 group-daily skill
- **测试结果**：❌ 放弃
- **失败原因**：
  - macOS 为主，Windows 几乎不可用
  - 虽然有 group-daily skill 很契合需求，但平台不支持就没法用

### 1.4 WeChatDecrypt 自带内存扫描（Python）

- **地址**：[github.com/ylytdeng/wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt)
- **原理**：直接从微信进程内存提取密钥，解密 SQLite 数据库。比依赖任何中间 CLI 工具都更底层、更可靠。
- **测试了两个入口**：

| 入口 | 命令 | 结果 |
|------|------|------|
| `find_all_keys_windows.py` | `python find_all_keys_windows.py` | ❌ 0/30 salts |
| `app_gui.py --task decrypt` | `python app_gui.py --task decrypt` | ❌ 0/30 salts |

- **失败原因**：扫描了 5 个 `Weixin.exe` 进程（14352/1704/24448/15992/41928），2.6 秒扫完 2603+880+1321+368+372 个内存区域，**0 hex 模式命中**。WCDB 的 hex 缓存格式 `x'<64hex_key><32hex_salt>'` 在当时的微信版本内存中不存在或格式已变化。

**但是**，WeChatDecrypt 项目的其他部分是宝藏——数据库解密逻辑、MCP Server、图片解码、语音转录等全部基于它。

### 1.5 wx_key（Flutter GUI，独立工具）✅ 唯一成功

- **文件**：`wx_key.exe`（Flutter 编译的 Windows GUI，v2.1.8）
- **原理**：独立的内存读取方式（非 hex 模式匹配），直接从微信进程提取 raw_key
- **测试结果**：✅ 成功 — 输出 64 位 hex raw_key
- **输出示例**：`477d0262ad44470686152101eeb615d9164290ccdc3e4a56afdc0cd85328943f`

**最终方案**：`wx_key` 提取 raw_key → `build_keys_json.py` + DB 目录生成 `all_keys.json` → WeChatDecrypt 的解密 + MCP Server 生态。

### 1.6 方案对比总结

| 方案 | 类型 | 密钥提取 | 消息解析 | 最终采用 |
|------|------|----------|----------|----------|
| wx-cli | 中间 CLI | 不需要 | 不完整 | ❌ |
| chatlog_alpha | 中间 CLI | 不需要 | 不稳定 | ❌ |
| vchat | 中间 CLI | 不需要 | 仅 macOS | ❌ |
| WeChatDecrypt 自带扫描 | 底层库 | 失败 | — | ❌ 扫描部分 |
| **wx_key** | 独立工具 | **成功** | — | ✅ 密钥提取 |
| **WeChatDecrypt 解密+MCP** | 底层库 | — | 完整 | ✅ 解密+查询 |

## 二、密钥提取：最关键的第一步

### 2.1 wx_key — 唯一成功的提取工具

尝试了两种方案：

| 方案 | 工具 | 结果 |
|------|------|------|
| WeChatDecrypt 自带 | `find_all_keys_windows.py` / `app_gui.py` | **失败** — 0/30 salts，5 个进程全扫不到 |
| 独立工具 | **wx_key** (Flutter GUI, v2.1.8) | **成功** — 直接输出 raw_key |

WeChatDecrypt 自带的内存扫描方案在当时的微信版本上扫不到任何 hex 缓存模式。而 `wx_key.exe` 作为独立的 Flutter 应用，成功从 `Weixin.exe` 进程内存中提取了 raw_key。

**wx_key 输出**：
```
477d0262ad44470686152101eeb615d9164290ccdc3e4a56afdc0cd85328943f
```

这是一个 64 位 hex 字符串（32 字节 raw_key）。

### 2.2 关键区别：raw_key vs page_key

WCDB 的加密方案有两层密钥：

```
raw_key (32 bytes, wx_key 输出的)
  → PBKDF2-HMAC-SHA512(raw_key, db_salt, 256000 iterations)
  → page_key (32 bytes, WCDB 内存缓存中存储的)
```

- **wx_key** 提取的是 `raw_key`（原始密钥，所有数据库通用）
- **WeChatDecrypt 内存扫描**搜索的是 `x'<page_key><salt>'` 格式（hex 缓存）
- 两者的区别就是 256000 次 PBKDF2 迭代

这意味着不能直接使用 WeChatDecrypt 的 `verify_enc_key` 来验证 wx_key 的输出——需要先做 256000 次 PBKDF2 派生才行。

### 2.3 提取步骤

```bash
# 1. 运行 wx_key.exe（Flutter GUI，微信必须正在运行）
tools\wx_key\wx_key.exe

# 2. 复制输出的 64 位 hex 密钥

# 3. 用 build_keys_json.py 生成 all_keys.json
cd D:\4_Code\0_Github_Project\wechat-analysis
python build_keys_json.py \
    --raw-key 477d0262ad44470686152101eeb615d9164290ccdc3e4a56afdc0cd85328943f \
    --db-dir "D:\path\to\wechat\db_storage" \
    -o all_keys.json
```

`build_keys_json.py` 的工作流程：
1. 遍历 `db_storage` 下所有 `.db` 文件，读取每个文件的 salt（page1[0:16]）
2. 用 raw_key + salt + 256000 次 PBKDF2 验证 HMAC
3. 生成 `all_keys.json`，所有数据库使用同一个 raw_key

### 2.4 输出格式

```json
{
  "message\\message_0.db": {
    "enc_key": "477d0262ad44470686152101eeb615d9164290ccdc3e4a56afdc0cd85328943f",
    "salt": "48803ce10056e24c4deac5222a875711"
  }
}
```

所有数据库使用**同一个 `enc_key`**（raw_key），但有不同的 `salt`。

### 2.5 依赖与要求

- **wx_key**：Windows，微信必须正在运行（`Weixin.exe`）
- **Python 依赖**：`pycryptodome`
- 不需要管理员权限（wx_key 自行处理进程内存读取）

## 三、解密阶段：PBKDF2 是关键

### 3.1 踩坑：raw_key 不能直接当 AES key

最初直接用 raw_key 作为 AES key 去解密数据库，结果失败。后来发现 WeChat 4.1 多了一层 PBKDF2 派生：

```
raw_key (32 bytes)
  → PBKDF2-HMAC-SHA512(raw_key, db_salt, 256000 iterations)
  → page_key (32 bytes)
  → AES-256-CBC(page_key, iv) → 解密页面
```

### 3.2 加密参数

| 参数 | 值 |
|------|-----|
| 页大小 | 4096 bytes |
| 保留区 | 80 bytes |
| Salt | page1[0:16] |
| IV | page1[4096-80:4096-80+16] |
| HMAC | page1[4096-64:4096]（SHA-512）|
| PBKDF2 迭代 | 256,000 |
| MAC key 派生 | PBKDF2(page_key, salt_XOR_0x3a, 2 iterations) |

### 3.3 解密命令

```bash
# 配置 config.json 后运行
python decrypt_db_fixed.py
```

解密后的文件结构：
```
decrypted/
├── message/
│   ├── message_0.db   ← 主消息库（最大）
│   ├── message_1.db
│   └── ...
├── contact/
│   └── contact.db     ← 联系人 + 群信息
└── session/
    └── session.db     ← 会话列表
```

## 四、数据库结构探索

### 4.1 分库分表

微信把消息分散在多个数据库中。每个联系人和群聊在 `message_*.db` 中对应一张表：

```
表名 = Msg_<MD5(username)>
```

例如：群「家」→ `username = 7584761248@chatroom` → MD5 → 表名 `Msg_cb1ecdfa...`

### 4.2 消息表关键字段

| 列名 | 说明 |
|------|------|
| local_id | 本地消息 ID |
| local_type | 消息类型：1=文本, 3=图片, 34=语音, 43=音视频通话, 47=引用回复, 49=分享链接 |
| real_sender_id | 发送者内部 ID（**2 = 设备主人自己**） |
| create_time | Unix 时间戳（**秒级，不是毫秒！**） |
| message_content | 内容（格式见下文） |
| source | 二进制 protobuf |
| packed_info_data | 二进制 protobuf（压缩） |

### 4.3 联系人表

- `contact` 表：username (wxid), nick_name, remark
- `chat_room` 表：username (chatroom_id@chatroom), owner, ext_buffer (protobuf 成员列表)
- `chatroom_member` 表：room_id, member_id

### 4.4 会话表

`SessionTable`：username, type, summary, last_timestamp (**秒**), sort_timestamp (**秒**)

## 五、消息内容格式 — 最坑的地方

同是 `local_type=1`（文本消息），`message_content` 有**三种**存储格式：

**格式 1：纯文本**（自己发的消息）
```
"今天天气不错"
```
- `real_sender_id = 2`（设备主人）
- 无 `wxid:\n` 前缀

**格式 2：带 wxid 前缀的文本**（别人的消息）
```
"wxid_mlqtge1xykd421:\n宿舍分好了，系统分的"
```
- 冒号换行分隔发送者和正文

**格式 3：Protobuf 包装**（群聊中常出现）
```
(\xb5...wxid_v88dad174u7l21:\n今天分享到这里...
```
- 开头 `(\xb5` 是 protobuf 标记
- 正文中夹杂二进制结构，UTF-8 严格解码会失败
- 需要 `errors='ignore'` 跳过无效字节

## 六、发送者解析的坑

### 问题 1：自己的消息显示 "?"

`real_sender_id = 2` 的消息没有 wxid 前缀，导致 `_parse_sender` 返回 `None`。

**解决**：检测 `real_sender_id`，当它等于 2 时，识别为设备主人自己的消息，用 `self_wxid` 查找显示名称。

### 问题 2：如何确定 "self_wxid"

微信不直接告诉你"我是谁"。启发式方法：
1. 在 `contact.db` 中搜索 `remark` 以 `HOME` 开头的联系人
2. 其中有 `HOME  王c`（姓名缩写）、`HOME  b1`（亲属代号）、`HOME  m1` 等
3. 匹配中文姓名缩写模式（`HOME\s+[一-鿿]+[a-z]`）来找到自己

### 问题 3：Protobuf 消息的发送者

Protobuf 包装的消息中，`wxid` 嵌在二进制头部后面。解析需要：
1. 找到 `wxid_` 字节位置（跳过 protobuf 头）
2. 找到紧随其后的 `:\n` 分隔符
3. 提取中间的 wxid

## 七、架构设计

最终系统分为两层：

### 第一层：定时任务（被动）

```
Windows 任务计划程序（每天 22:00）
  → run_daily_report.bat
  → daily_report.py
  → wechat_query.py（查询库）
  → DeepSeek API（Claude 兼容接口）
  → 输出 report_YYYY-MM-DD.md
```

### 第二层：MCP Server（交互）

```
Claude Code
  → claude mcp add wechat-decrypt
  → mcp_server.py（17 个工具）
  → 实时查询 / 搜索 / 解码图片语音
```

两个方案互补：定时任务保证日报不遗漏，MCP Server 提供灵活的即时查询。

## 八、踩坑总结

| # | 问题 | 根因 | 解决 |
|---|------|------|------|
| 1 | 解密失败 | raw_key 不能直接当 AES key | 增加 PBKDF2 256000 次迭代派生 |
| 2 | 数据库损坏 | MCP Server 缓存了错误解密的 DB | 修复解密逻辑 + 清除缓存 |
| 3 | 时间显示 1970 年 | 时间戳是秒级却按毫秒处理 | 去掉 `/1000` |
| 4 | 发送者显示 `?` | 自己的消息无 wxid 前缀 | `real_sender_id=2` 检测 + `self_wxid` 查找 |
| 5 | 文本消息显示 `[消息类型 1]` | protobuf 包装的 bytes 被跳过 | 解析 protobuf 头 + `errors='ignore'` |
| 6 | 消息末尾有二进制垃圾 | protobuf 嵌套结构破坏 UTF-8 | `_strip_binary` 去除控制字符 |
| 7 | self_wxid 返回错误 wxid | LIMIT 1 拿到了第一个 HOME 联系人 | 用正则 `HOME\s+[一-鿿]+[a-z]` 匹配姓名缩写 |
| 8 | MCP Server 连不上 Claude Code | settings.json 不接受 mcpServers | 用 `claude mcp add` 命令行配置 |

## 九、参考

- WeChatDecrypt 项目：[github.com/ylytdeng/wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt)
- WeChat 4.1 加密分析：WCDB/SQLCipher 4 变体，PBKDF2-HMAC-SHA512
- MCP Server 配置：`claude mcp add <name> -- python <script>`

# core-wechat — 微信聊天记录解密

## 加密方案发现过程

微信 4.x 使用 **SQLCipher 4** 加密本地 SQLite 数据库。该方案最早由 [WeChatDecrypt](https://github.com/ylytdeng/wechat-decrypt) 项目逆向确认，通过分析微信进程内存中的 `sqlite3_key` 调用获取密钥。

### 加密参数

| 参数 | 值 | 来源 |
|------|-----|------|
| 加密库 | SQLCipher 4 | DLL 中 `sqlcipher` 字符串 |
| 页面大小 | 4096 字节 | DB 文件第一页结构 |
| KDF 算法 | PBKDF2-HMAC-SHA512 | SQLCipher 4 默认 |
| KDF 迭代次数 | 256000 | SQLCipher 4 默认 |
| 对称加密 | AES-256-CBC | 每页独立密钥 |
| HMAC | HMAC-SHA512 | 页面完整性校验 |
| Reserve 区 | 80 字节 | 页尾存储 IV + HMAC |
| Salt | 16 字节 | 页首前 16 字节 |

### 密钥推导链

```
raw_key (64位hex, wx_key.exe 提取)
    ↓ PBKDF2-HMAC-SHA512 (raw_key, salt, 256000, dklen=32)
page_key (32 bytes)
    ↓ PBKDF2-HMAC-SHA512 (page_key, mac_salt, 2, dklen=32)
mac_key (32 bytes)
```

每个数据库文件的第一页包含独立的 salt，因此不同数据库使用不同的 page_key。

### 页面解密流程

```
第一页 (pgno=1):
  [salt 16B] [encrypted_data] [IV 16B] [HMAC 64B] [reserved]
  ↓ 用 salt 派生 page_key
  ↓ 用 page_key + IV 做 AES-CBC 解密
  ↓ 拼接 SQLite header
  → 正常 SQLite 页面

其他页 (pgno>1):
  [encrypted_data] [IV 16B] [HMAC 64B] [reserved]
  ↓ 用 page_key + IV 做 AES-CBC 解密
  → 正常 SQLite 页面
```

## 数据来源

| 文件 | 来源路径 | 说明 |
|------|---------|------|
| `message_*.db` | `%APPDATA%\Tencent\xwechat\{wxid}\db_storage\message\` | 消息分片，按用户名 hash 分表 |
| `contact.db` | `db_storage\contact\` | 联系人、群昵称 |
| `session.db` | `db_storage\session\` | 会话列表 |
| `all_keys.json` | `export_parse_result\all_keys.json` | 由 `keys.py` 生成 |
| `raw_key` | wx_key.exe 运行时输出 | 64位 hex，进程内存提取 |

### raw_key 说明

`raw_key` 是微信进程内存中的 SQLCipher 主密钥。`wx_key.exe` 通过扫描 `Weixin.exe` 进程的内存空间，定位 `sqlite3_key` 函数调用时传入的密钥参数。该密钥在微信登录后常驻内存。

## 使用方法

```bash
# 第一步：提取密钥（微信必须运行）
tools\wx_key\wx_key.exe
# 复制输出的 64 位 hex

# 第二步：生成密钥文件
python wechat.py setup --raw-key <64位hex>

# 第三步：解密所有数据库
python wechat.py decrypt

# 第四步：查看群聊
python wechat.py groups

# 第五步：生成日报
python wechat.py report --date 2026-06-28 --groups 家
```

## 文件说明

| 文件 | 职责 |
|------|------|
| `decrypt.py` | SQLCipher 4 解密核心（逐页 AES-CBC） |
| `keys.py` | raw_key → all_keys.json（验证 + 生成） |
| `paths.py` | 输出路径常量 |
| `query.py` | SQLite 查询、protobuf/zstd 消息解析、群昵称 |
| `visual_report.py` | HTML/PNG 日报生成 |
| `image_extract.py` | 群聊图片提取 |
| `wechat_sender.py` | 自动发送 PNG 到微信群 |
| `chat_platform.py` | 平台接口（封装 WeChatDB） |

## 数据流

```
wx_key.exe → raw_key (64位hex)
    ↓
keys.py → all_keys.json (每个DB的salt+key映射)
    ↓
decrypt.py → export_parse_result/decrypted_wechat/*.db (明文SQLite)
    ↓
query.py → 消息查询、发送者解析
    ↓
visual_report.py → export_parse_result/reports_wechat/*.html
```

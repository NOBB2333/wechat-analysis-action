# core-dingtalk — 钉钉聊天记录解密

## 加密方案发现过程

钉钉 V3 使用 **AES-128-ECB** 对数据库进行逐页加密。该方案由 [dingwave-V3](https://github.com/E2ern1ty/dingwave-V3) 项目通过逆向分析 `liblark.dll` 确认，密钥推导逻辑来源于[看雪论坛小周学习站的逆向分析](https://bbs.kanxue.com/thread-287455.htm)。

### 加密参数

| 参数 | 值 | 来源 |
|------|-----|------|
| 加密方式 | AES-128-ECB | DLL 中 AES-ECB 模式调用 |
| 页面大小 | 4096 字节 | 标准 SQLite 页大小 |
| 密钥长度 | 16 字节 (128 bit) | AES-128 |
| 密钥推导 | PBKDF2 + MD5 | 逆向分析确认 |
| PBKDF2 算法 | HMAC-SHA1 | DLL 中 `PKCS5_PBKDF2_HMAC_SHA1` |
| PBKDF2 Salt | `"666DingT"` (8 bytes) | 逆向分析硬编码常量 |
| PBKDF2 迭代 | 1000 | 逆向分析确认 |
| PBKDF2 输出 | 32 bytes | SHA1 完整输出 |
| 最终密钥 | `MD5(PBKDF2_output).hex[:16]` | 取前 16 字符作为 AES-128 key |

### 密钥推导链

```
UID (9-10位数字, 从日志提取)
    ↓ 拼接 salt (从 user_config 读取)
password = uid + salt
    ↓ PBKDF2-HMAC-SHA1 (password, "666DingT", 1000, dklen=32)
dk (32 bytes)
    ↓ MD5(dk).hex()[:16]
AES-128 key (16 字节)
    ↓ AES-ECB 逐页解密 (4096 字节/页)
明文 SQLite 数据库
```

### UID 来源

UID 是钉钉用户的数字标识符（9-10 位），从 `%APPDATA%\DingTalk\log\cef_debug.log` 中提取：

```
URL 参数格式: advancedSearch.html?uid=691398452&...
```

UID 不在任何配置文件或注册表中，仅出现在日志文件的 URL 参数里。`find_uid.py` 脚本自动搜索所有日志文件提取此值。

### Salt 来源

Salt 存储在 `{data_dir}/user_config` 文件中，Base64 编码的 JSON 格式：

```python
import base64, json
with open('user_config', 'rb') as f:
    config = json.loads(base64.b64decode(f.read()))
salt = config['salt']  # 32位hex字符串，如 "099cb0c5da9bc3cd22cb34f79e06e561"
```

## 数据来源

| 文件 | 来源路径 | 说明 |
|------|---------|------|
| `dingtalk.db` | `%APPDATA%\DingTalk\{uid_hex}_{version}\DBFiles\` | 主数据库（加密） |
| `user_config` | 同上目录 | Base64 JSON，含 salt |
| `cef_debug.log` | `%APPDATA%\DingTalk\log\` | UID 存储位置 |

## 使用方法

```bash
# 第一步：自动提取 UID
python find_uid.py
# 输出: 691398452

# 第二步：解密数据库
python decrypt.py
# 自动读取 salt，推导密钥，AES-ECB 解密

# 第三步：导出数据
python export_all.py
# 导出 contacts.json, conversations.json, messages/
```

## 数据库结构

```
dingtalk.db (解密后)
├── tbconversation        # 会话列表 (cid, title, type)
├── tbuser_profile_v2     # 联系人 (uid, nick, mobile)
├── tbmsg_000~tbmsg_127   # 消息分片表 (cid, senderId, content, createdAt)
├── tblastmsg             # 最近消息
├── contact_friend        # 好友关系
└── ...
```

消息存储在 `tbmsg_{hash % 127}` 分片表中，需要遍历所有分片表查询。

## 文件说明

| 文件 | 职责 |
|------|------|
| `chat_platform.py` | 平台接口（封装数据库查询） |
| `find_uid.py` | 从日志自动提取 UID |
| `decrypt.py` | AES-128-ECB 解密 |
| `decrypt_uid.py` | UID 辅助解密 |
| `export_all.py` | 数据导出为 JSON |

## 数据流

```
cef_debug.log → UID (691398452)
user_config → salt (099cb0c5da9bc3cd22cb34f79e06e561)
    ↓ PBKDF2(uid+salt, "666DingT", 1000) → MD5[:16]
AES-128 key
    ↓ AES-ECB 逐页解密
export_parse_result/decrypted_dingtalk/dingtalk.db (明文)
    ↓
export_all.py → exported/contacts.json, messages/*.json
```

## V2 vs V3

| 版本 | 目录特征 | 密钥推导 |
|------|---------|---------|
| V2 | 目录名不含 `_v3` | `MD5(uid).hex()[:16]` |
| V3 | 目录名含 `_v3` | `PBKDF2(uid+salt, "666DingT", 1000)` → `MD5[:16]` |

# core-wecom — 企业微信聊天记录解密

## 加密方案发现过程

企业微信使用 **wxSQLite3 AES-128-CBC** 加密本地数据库。该方案由 [WeChatDecrypt](https://github.com/ylytdeng/wechat-decrypt) 项目确认，与个人微信不同的是使用了 16 字节 raw key 而非 SQLCipher 的 32 字节密钥。

### 加密参数

| 参数 | 值 | 来源 |
|------|-----|------|
| 加密库 | wxSQLite3 | DLL 中 wxSQLite3 引用 |
| 加密方式 | AES-128-CBC | 每页独立 IV |
| 密钥长度 | 16 字节 raw key | 不同于 SQLCipher 的 32 字节 |
| 页面大小 | 4096 字节 | 标准 SQLite 页大小 |
| HMAC | 无 | 区别于 SQLCipher |

### 密钥推导

```
raw_key (16 bytes, 从进程内存提取)
    ↓ MD5(raw_key + page_no + "sAlT")
page_key (16 bytes, 每页不同)
    ↓ 生成 IV (基于 page_no 的算法)
AES-128-CBC 解密
```

注意：企微使用 **无 HMAC** 的简化方案，与个人微信的 SQLCipher 4 不同。

## 数据来源

| 文件 | 来源路径 | 说明 |
|------|---------|------|
| `message.db` | `%USERPROFILE%\Documents\WXWork\{uid}\Data\` | 消息 |
| `session.db` | 同上 | 会话 |
| `user.db` | 同上 | 用户信息 |
| `company.db` | 同上 | 公司信息 |

## 使用方法

```bash
# 确保 WXWork 进程运行
python tools/wechat-decrypt/find_wxwork_keys.py   # 内存扫描提取密钥
python tools/wechat-decrypt/decrypt_wxwork_db.py  # 解密数据库
```

## 密钥提取

企微密钥从 WXWork 进程内存中扫描。工具搜索内存中的 `x'...'` 格式的 SQLCipher key literal，或裸 32-hex 格式的 key。每个数据库可能有独立的密钥。

```
WXWork.exe 进程 → 内存扫描 → raw_key (16 bytes)
```

## 文件说明

| 文件 | 职责 |
|------|------|
| `chat_platform.py` | 平台接口（封装数据库查询） |

## 数据流

```
WXWork.exe 进程 → 内存扫描 → raw_key
    ↓ wxSQLite3 AES-128-CBC 逐页解密
明文 SQLite 数据库
```

## 状态

⚠️ 已有解密工具（`tools/wechat-decrypt/`），但密钥自动提取需要 WXWork 进程运行中。

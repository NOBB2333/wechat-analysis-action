# 微信 4.1 解密数据库结构文档

> 本文档梳理微信 Windows 4.1 版本解密后的 SQLite 数据库结构，以及如何从中查找各类数据。

## 一、数据库概览

解密后 `export_parse_result/decrypted_wechat/` 下的文件结构：

```
export_parse_result/decrypted_wechat/
├── contact/
│   └── contact.db           # 联系人、群信息、群昵称
├── session/
│   └── session.db           # 会话列表
└── message/
    ├── message_0.db         # 消息主库（含多个群的表）
    ├── message_1.db ~ message_6.db   # 分片消息库
    ├── message_resource.db  # 媒体资源索引（图片/视频/文件 MD5）
    ├── media_0.db           # 媒体元数据
    └── message_fts.db       # 全文搜索索引（暂未使用）
```

### 多库分片

微信把不同群/联系人的消息分散在多个 `message_*.db` 中。每个库里以 `Msg_<md5>` 命名表，`<md5>` 是 `md5(聊天对象 wxid)` 的 hex 摘要。

例如 `21001820917@chatroom` 的消息表名：
```
Msg_b47ee123606c4ab7041dae4dc3ef0043
```

同一 wxid 的消息表**只出现在一个 message DB 中**，不会跨库分片。

---

## 二、各库表结构

### 2.1 contact.db — 联系人

#### `contact` 表

微信好友、群聊、公众号等所有联系人。

| 列名 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 自增主键 |
| `username` | TEXT | 微信 ID (`wxid_xxx`、`xxx@chatroom`、`xxx@openim`) |
| `nick_name` | TEXT | 对方自己的微信昵称 |
| `remark` | TEXT | 你给对方设置的备注 |
| `alias` | TEXT | 微信号（非 wxid，是用户自定义的微信号） |
| `local_type` | INTEGER | 联系人类型：1=群聊，其他=好友/公众号 |
| `big_head_url` | TEXT | 大头像 URL |
| `small_head_url` | TEXT | 小头像 URL |
| `is_in_chat_room` | INTEGER | 对方是否在某个群中 |
| `extra_buffer` | BLOB | protobuf 扩展数据 |

**样例**：
```
username          | nick_name   | remark | local_type
21001820917@chatroom |             |        | 1 (群聊)
wxid_7dm7trcwtxvz21  | wong        |        | 0 (好友)
```

#### `chat_room` 表

群聊专属信息，**群昵称存储在这里**。

| 列名 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 自增主键，`chatroom_member.room_id` 外键 |
| `username` | TEXT | 群聊 wxid（`xxx@chatroom`） |
| `owner` | TEXT | 群主 wxid |
| `ext_buffer` | BLOB | protobuf 编码的群成员列表（含群昵称） |

**`ext_buffer` 结构**（protobuf）：

```protobuf
message ChatRoomExt {
  repeated Member members = 1;
}
message Member {
  required string wxid = 1;         // tag 1
  optional string display_name = 2; // tag 2，群昵称
  optional int32 role = 3;          // tag 3，群角色
}
```

每个人一条 `Member` 子消息，字段 1 是 wxid，字段 2 是群昵称（可能为空）。

**查询示例**：
```sql
SELECT ext_buffer FROM chat_room WHERE username = '21001820917@chatroom';
```
然后用 protobuf 解析得到 `{wxid: group_nickname}` 映射。

#### `chatroom_member` 表

群聊成员关联表。

| 列名 | 类型 | 说明 |
|------|------|------|
| `room_id` | INTEGER | `chat_room.id` |
| `member_id` | INTEGER | `contact.id` |

#### 其他表

| 表名 | 说明 |
|------|------|
| `contact_label` | 标签（分组） |
| `name2id` | 名称到 ID 的映射 |
| `biz_info` | 公众号信息 |
| `stranger` | 陌生人信息 |

---

### 2.2 message_*.db — 聊天消息

#### `Msg_<md5>` 表（每个聊天对象一张表）

| 列名 | 类型 | 说明 |
|------|------|------|
| `local_id` | INTEGER | 消息本地 ID（递增，但不一定连续） |
| `create_time` | INTEGER | Unix 时间戳（秒） |
| `real_sender_id` | INTEGER | 发送者 ID（引用 `Name2Id.rowid`） |
| `local_type` | INTEGER | 消息类型（见下方类型表） |
| `message_content` | BLOB | 消息体（protobuf/zstd/XML/文本） |
| `source` | BLOB | 发送者来源信息 |
| `packed_info_data` | BLOB | 压缩相关信息 |

#### 消息类型编码

```
local_type ≤ 0xFFFFFFFF: 直接就是 base_type
local_type > 0xFFFFFFFF:
  base_type = local_type & 0xFFFFFFFF    (低 32 位)
  sub_type  = local_type >> 32           (高 32 位)
```

**基础类型**：

| base_type | 标签 |
|-----------|------|
| 1 | 文本消息 |
| 3 | 图片 |
| 34 | 语音 |
| 42 | 名片 |
| 43 | 音视频通话 |
| 47 | 表情 |
| 48 | 位置 |
| 49 | app 消息（链接/文件/引用/红包等） |
| 50 | 音视频通话 |
| 62 | 小视频 |
| 10000 | 系统消息 |

**app 消息子类型**（base_type=49 时的高 32 位）：

| sub_type | 含义 |
|----------|------|
| 5 | 链接卡片 |
| 6 | 文件 |
| 19 | 聊天记录转发 |
| 33, 36 | 小程序 |
| 57 | 引用回复 |
| 62 | 系统消息（撤回等） |
| 2000 | 转账 |
| 2001 | 红包 |

#### `Name2Id` 表

**发送者解析的关键表**。`real_sender_id` → wxid 映射。

| 列名 | 类型 | 说明 |
|------|------|------|
| `rowid` | INTEGER | 隐式主键 = `real_sender_id` |
| `user_name` | TEXT | 发送者 wxid |

**查询示例**：
```sql
SELECT user_name FROM Name2Id WHERE rowid = <real_sender_id>;
```

同一个 wxid 的 `real_sender_id` **在不同 message DB 中可能不同**。本项目的 `WeChatDB._parse_sender` 先从当前 DB 查，找不到再查全局。

---

### 2.3 message_resource.db — 媒体资源

#### `ChatName2Id` 表

| 列名 | 类型 | 说明 |
|------|------|------|
| `rowid` | INTEGER | 自增主键，即 chat_id |
| `user_name` | TEXT | 聊天对象 wxid |

#### `MessageResourceInfo` 表

图片/视频/文件等媒体消息的 MD5 索引。

| 列名 | 类型 | 说明 |
|------|------|------|
| `chat_id` | INTEGER | 聊天对象 ID（引用 `ChatName2Id.rowid`） |
| `message_local_id` | INTEGER | 消息本地 ID（对应 `Msg_<md5>.local_id`） |
| `message_local_type` | INTEGER | 消息类型 |
| `message_create_time` | INTEGER | 消息时间戳 |
| `packed_info` | BLOB | protobuf，内含文件 MD5 |

**提取 MD5**：
```python
# packed_info 中搜索 marker \x12\x22\x0a\x20 + 32 字节 ASCII hex
marker = b'\x12\x22\x0a\x20'
idx = blob.find(marker)
file_md5 = blob[idx+4:idx+36].decode('ascii')  # 32 位 hex，如 "24ca706f6848cb..."
```

**完整链路**：
```
Msg_<md5>.local_id  +  ChatName2Id.user_name
    → MessageResourceInfo (chat_id + message_local_id)
    → packed_info → extract_md5 → 32 位 hex
    → xwechat_files/.../attach/<chat_hash>/<YYYY-MM>/Img/<md5>.dat
    → 解密 .dat → 图片
```

---

### 2.4 session.db — 会话列表

#### `SessionTable` 表

| 列名 | 类型 | 说明 |
|------|------|------|
| `username` | TEXT | 聊天对象 wxid |
| `type` | INTEGER | 会话类型 |
| `summary` | TEXT | 最后一条消息摘要 |
| `last_timestamp` | INTEGER | 最近活动时间戳 |
| `unread_count` | INTEGER | 未读消息数 |

---

## 三、数据查找指南

### 查群聊

**1. 列出所有群**：
```sql
-- contact.db
SELECT username, nick_name, remark FROM contact
WHERE username LIKE '%@chatroom%';
```

**2. 按群名搜索**：
```sql
SELECT username FROM contact
WHERE (nick_name LIKE '%长红巨牛%' OR remark LIKE '%长红巨牛%')
  AND username LIKE '%@chatroom%';
```

**3. 获取群显示名**：
```sql
SELECT nick_name, remark FROM contact WHERE username = '21001820917@chatroom';
```
群聊的 `nick_name` 是群名，`remark` 是你设的群备注。

### 查用户昵称/群昵称

**1. 微信昵称**：
```sql
SELECT nick_name FROM contact WHERE username = 'wxid_xxx';
```

**2. 备注名**：
```sql
SELECT remark FROM contact WHERE username = 'wxid_xxx';
```

**3. 群昵称**（特定用户在特定群里的群昵称）：
```sql
-- 先查 chat_room.ext_buffer，再解析 protobuf
SELECT ext_buffer FROM chat_room WHERE username = '21001820917@chatroom';
```
然后用 protobuf 解析器提取 `{wxid: group_nickname}` 映射。

### 查 wxid

**1. 从 real_sender_id 查**：
```sql
-- 当前 message DB
SELECT user_name FROM Name2Id WHERE rowid = <real_sender_id>;
```

**2. 列出所有 Name2Id 映射**：
```sql
SELECT rowid, user_name FROM Name2Id WHERE user_name != '';
```

**3. 通过自己的身份识别**（如果没设置 self_wxid）：
```sql
-- contact.db 中 remark 以 'HOME' 开头且有中文名的联系人
SELECT username FROM contact WHERE remark LIKE 'HOME%';
```

### 查消息

**1. 确定消息表名**：
```python
import hashlib
table = f"Msg_{hashlib.md5(chatroom.encode()).hexdigest()}"
# 例如 chatroom='21001820917@chatroom' → Msg_b47ee123606c...
```

**2. 查某个时间段的消息**：
```sql
SELECT local_id, create_time, real_sender_id, local_type, message_content
FROM Msg_b47ee123606c4ab7041dae4dc3ef0043
WHERE create_time >= <start_ts> AND create_time <= <end_ts>
ORDER BY create_time;
```

**3. 找消息表在哪个 message DB 中**：
```python
for i in range(10):
    db = sqlite3.connect(f'message_{i}.db')
    if table_name in db.execute("SELECT name FROM sqlite_master").fetchall():
        return db, f'message_{i}.db'
```

### 查头像

头像 URL 存在 `contact` 表中：
```sql
SELECT username, nick_name, big_head_url, small_head_url
FROM contact
WHERE username = 'wxid_xxx';
```

**URL 格式**：
```
https://wx.qlogo.cn/mmhead/.../0     -- 小头像
https://wx.qlogo.cn/mmhead/.../132   -- 中头像
https://wx.qlogo.cn/mmhead/.../0     -- 可改最后数字获取不同尺寸
```

这些 URL 需要**微信登录态 cookie** 才能访问，不能直接下载。下载需要带 `Cookie` 和 `User-Agent` 头。

### 查图片/视频文件

**完整链路**（详见 2.3 节）：

1. 从 `Msg_<md5>` 表拿到图片消息的 `local_id`（`WHERE local_type = 3`）
2. 从 `message_resource.db` 的 `ChatName2Id` 拿到 `chat_id`
3. 从 `MessageResourceInfo` 用 `(chat_id, message_local_id)` 查 `packed_info`
4. 从 `packed_info` 提取 32 位 MD5
5. 在文件系统中找 `.dat` 文件：
```
<xwechat_files>/msg/attach/<md5(chatroom)>/<YYYY-MM>/Img/<file_md5>.dat
<xwechat_files>/msg/attach/<md5(chatroom)>/<YYYY-MM>/Img/<file_md5>_h.dat  (高清)
<xwechat_files>/msg/attach/<md5(chatroom)>/<YYYY-MM>/Img/<file_md5>_t.dat  (缩略)
```
6. 解密 `.dat`：旧格式用自动检测的 XOR key，V2 格式需 AES key（从微信进程内存提取）

**文件命名规则**：
| 文件名 | 含义 | 来源 |
|--------|------|------|
| `<md5>.dat` | 压缩预览 | 微信自动下载 |
| `<md5>_h.dat` | 高清原图 | 手动点"查看原图"后下载 |
| `<md5>_t.dat` | 缩略图 | 聊天列表小图 |
| `<md5>_W.dat` | 新版格式（V2） | WeChat 4.x 版本 |

# 已知问题与技术发现

> 本文记录在开发和调试微信 4.1 聊天记录解析过程中发现的技术细节、已解决的问题、以及当前限制。

## 1. WCDB_CT=4 消息体压缩

### 现象

部分消息的 `message_content` 被 WCDB（微信数据库库）压缩。压缩后的字节流：
- 不是 zlib / zstd / lz4 / brotli / snappy 等已知算法
- 属于微信私有格式，目前无法解压

### 影响范围

- **type 1（文本消息）**：压缩后文本不可读，显示为 `[文本]`
- **type 49 / sub_type 57（引用回复）**：压缩后无法提取回复正文和引用详情，只能显示 `[引用消息]`
- **type 49 其他子类型**：压缩后只能显示类型标签

### 数据库特征

`packed_info_data` 列在微信 4.1 中可能总是非 NULL，**不能**作为判断内容是否压缩的依据。目前通过 `_safe_decode` 的字节有效率检测来间接识别压缩数据。

### 尝试过但不可行的方案

- zlib 各种 wbits 组合：不解压
- zstd / lz4 / brotli / snappy：不解压
- raw deflate 在多个偏移量尝试：不解压
- 需要 WCDB 解压库（微信内部库，未公开）

## 2. 消息类型编码

### local_type 结构

微信把 app 子类型打包进 `local_type` 的高 32 位：

```
local_type > 0xFFFFFFFF 时:
  base_type = local_type & 0xFFFFFFFF   (低 32 位)
  sub_type  = local_type >> 32          (高 32 位)
```

### 已知子类型映射

| sub_type | 含义 |
|----------|------|
| 5 | 链接 |
| 6 | 文件 |
| 33, 36 | 小程序 |
| 57 | 引用消息 |
| 62 | 系统消息（撤回等） |
| 2000 | 转账 |
| 2001 | 红包 |

### 基础类型映射

| type | 标签 | 说明 |
|------|------|------|
| 1 | [文本] | 文本消息 |
| 3 | [图片] | 图片 |
| 34 | [语音] | 语音消息 |
| 42 | [名片] | 名片 |
| 43 | [音视频通话] | 通话 |
| 47 | [表情] | 表情/动画表情 |
| 48 | [位置] | 位置 |
| 49 | [分享/链接] | app 消息（默认标签，具体看子类型） |
| 50 | [音视频通话] | 通话 |
| 62 | [小视频] | 小视频 |
| 10000 | [系统消息] | 系统消息（入群、撤回通知等） |

## 3. `_safe_decode` 文本识别策略

### 问题

微信 `message_content` 的格式是 protobuf 编码的 `(\xb5 [varint] wxid:\n[body]`。对于：
- **真实文本**：`[body]` 是合法 UTF-8
- **WCDB 压缩数据**：`[body]` 是二进制随机字节

不能简单用 `errors="strict"` 区分（正常消息中也可能混入少量非 UTF-8 字节，如 protobuf 包装）。也不能只用 `errors="ignore"`（压缩数据的有效字节会产生乱码但长度够长会被误判）。

### 当前方案

`_safe_decode` 用 `errors="ignore"` 宽松解码后，通过三道关卡判断：

1. **字节有效率**：`len(decoded) / len(raw_bytes) >= 15%`
   - 真实 UTF-8 文本的有效率远高于此（ASCII 约 100%，CJK 约 33-50%）
   - 压缩数据的随机字节绝大多数不是合法 UTF-8，被 `errors="ignore"` 丢弃后的有效率远低于 15%

2. **CJK 字符检测**：至少 1 个汉字 → 直接接受
   - 压缩数据几乎不可能产生合法的 CJK 多字节序列

3. **ASCII 文本回退**：
   - 长文本（> 5 字符）：可打印字符占比 ≥ 85%
   - 短文本（≤ 5 字符）：全部为可打印 ASCII 就接受

### 局限性

- 纯 ASCII 的长压缩数据（罕见的字节分布）可能通过 85% 可打印检查
- 纯表情/emoji 消息可能被误判为不可读（emoji 不在 "可打印" 范围内，但通常伴随文字）

## 4. 引用消息显示

### 非压缩内容（WCDB_CT=0）

`_format_refer_message` 可以完整解析并显示：
```
回复正文 {{引用消息 10:30 张三 发送内容：摘要}}
```
包含：回复者说的话、被引用时间、被引用者名称、被引用内容摘要（≤ 40 字）。

### 压缩内容（WCDB_CT=4）

只能显示 `[引用消息]`，无法提取任何详情。reply 正文和 refermsg 都在被压缩的 XML 中。

## 5. 联系人显示名称优先级

通过 `display_name_priority` 配置，按列表顺序尝试：
```jsonc
"display_name_priority": ["group_nickname", "nickname", "remark"]
```

- `group_nickname`：从 `contact.db` 的 `ChatRoom` 表查群昵称
- `nickname`：微信昵称（`contact.nick_name`）
- `remark`：你设置的备注（`contact.remark`）

旧格式 `display_name_mode` 自动向后兼容转换为新格式。

## 6. 发送者解析

消息表中使用 `real_sender_id`（整数）而非 wxid 存储发送者。通过 `Name2Id` 表映射：

```sql
SELECT user_name FROM Name2Id WHERE rowid = ?
```

同一消息库的 `Name2Id` 优先；找不到时回退到全局 `Name2Id`（跨所有 `message_*.db` 文件），减少 `?` 发送者。

## 7. Protobuf 内容格式

### `(\xb5` 前缀

`message_content` 以 `0x28 0xB5` 开头时，表示 protobuf field 5 wire type 2（length-delimited）。结构为：

```
0x28 0xB5 [varint_length] wxid:\n[message_body]
```

- `0x28 = (5 << 3) | 0`：field number 5, wire type 0（但后续 `0xB5` 说明这是 WCDB 自定义编码）
- `varint_length`：后续内容字节数
- `wxid:\n`：发送者标识和分隔符
- `message_body`：消息正文（文本、XML 或 WCDB 压缩数据）

### 图片/表情等媒体类型的二进制保护

图片（type 3）、表情（type 47）等媒体类型的 protobuf 二进制数据中可能含有 `0x3C`（`<`）字节，容易被误判为 XML 开头。`_try_decode` 只搜索真实 XML 标签（`<?xml`、`<msg>`、`<appmsg` 等），避免误判。

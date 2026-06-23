# 已知问题与技术发现

> 本文记录在开发和调试微信 4.1 聊天记录解析过程中发现的技术细节、已解决的问题、以及当前限制。

## 1. 消息体压缩

微信 4.1 中 `message_content` 可能出现两种压缩/编码：

### 1.1 zstd 压缩（已处理）

部分消息（尤其是引用回复、链接卡片等 app 消息）用 **zstd** 压缩，4 字节 magic 为 `0x28B52FFD`（即 `(\xb5/\xfd`）。

- **处理方式**：`query.py` 中通过 `zstandard` 库解压，再按 protobuf/XML 流程解析
- **影响**：引用回复、链接分享等现在可以正常显示

### 1.2 WCDB_CT=4 私有压缩（无法处理）

部分消息被 WCDB（微信数据库库）用私有算法压缩。压缩后的字节流：
- 不是 zlib / zstd / lz4 / brotli / snappy 等已知算法
- 属于微信内部格式，目前无法解压

#### 影响范围

- **type 1（文本消息）**：压缩后文本不可读，显示为 `[文本]`
- **type 49 / sub_type 57（引用回复）**：压缩后无法提取回复正文和引用详情，只能显示 `[引用消息]`
- **type 49 其他子类型**：压缩后只能显示类型标签

#### 数据库特征

`packed_info_data` 列在微信 4.1 中可能总是非 NULL，**不能**作为判断内容是否压缩的依据。目前通过 `_safe_decode` 的字节有效率检测来间接识别压缩数据。

#### 尝试过但不可行的方案

- zlib 各种 wbits 组合：不解压
- lz4 / brotli / snappy：不解压
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

## 4. 引用/回复消息解析

微信 4.1 中引用回复是 `local_type = 49 | (57 << 32)`，消息体通常先用 **zstd** 压缩，外层是 protobuf 包装：`wxid_...:\n<body>`。

### 解析流程

1. **zstd 解压**
   - 消息体以 4 字节 magic `0x28B52FFD`（即 `(\xb5/\xfd`）开头
   - 用 `zstandard` 解压后得到 `wxid_...:\n<?xml...><msg>...</msg>`

2. **提取外层 XML**
   - `_try_decode` 先搜索 `<?xml` / `<msg>` / `<appmsg>` 等真实 XML 标记
   - 找到第一个 XML 标记后，往回找最近的 `:\n` 作为 sender/text 分隔符
   - **关键**：`<refermsg><content>` 内部还会嵌套被引用消息的 `wxid_...:\n&lt;?xml...`，如果直接搜索第一个 `wxid_` 会误把被引用的内容当主消息。因此必须优先按 XML 标记定位外层回复消息。

3. **解析引用结构**
   - `_format_refer_message` 读取 `<appmsg><type>57</type>` 确认是引用回复
   - `<appmsg><title>`：回复者输入的文字（可能为空，如只发了一个表情）
   - `<refermsg>` 下：
     - `<type>`：被引用消息类型（1 文本、3 图片、43 视频、49 富媒体等）
     - `<content>`：被引用消息的内容（文本或转义后的 XML）
     - `<createtime>`：被引用消息时间
     - `<chatusr>`：被引用者 wxid（注意不是 `<fromusr>`，后者是群聊 id）
     - `<displayname>`：被引用者当时的显示名
   - 被引用者当前显示名通过 `get_display_name(chatusr, chatroom=...)` 解析，优先群昵称

4. **被引用内容摘要**
   - `_summarize_refer_content` 按被引用类型生成摘要：
     - type 1：截取文本前 40 字
     - type 3/34/43/47/48/50：`[图片]`、`[语音]`、`[视频]`、`[动画表情]`、`[位置]`、`[通话]`
     - type 49：再解析 `<appmsg><type>`，生成 `[链接] 标题`、`[文件]`、`[小程序]`、`[红包]`、`[转账]`、`[聊天记录]` 等

5. **渲染格式**
   ```
   回复正文 {{引用消息 HH:MM 发送者 发送内容：摘要}}
   ```
   示例：
   ```
   [强] {{引用消息 08:55 本群第一瓦吹 发送内容：[图片]}}
   是的，自从被套了 {{引用消息 16:12 *ST渣马 发送内容：[图片]}}
   ```

### 过滤问题（已修复）

`normalize_messages` 曾有一条过滤规则：
```python
if not include_system and local_type != 1 and not text.startswith("["):
    continue
```
这导致大量引用消息被丢弃——只有回复正文是 `[强]`、`[图片]` 等以 `[` 开头的消息才会保留。

当前规则改为：非文本消息只要有可读文本就保留，只显式跳过系统消息（`local_type=10000/10002`）。

### 仍无法解析的情况

- **WCDB_CT=4 私有压缩**：如果消息体被微信 WCDB 私有算法压缩（非 zstd），`_safe_decode` 会识别为不可读，最终显示 `[引用消息]`
- 被引用消息本身也是引用消息时，摘要会显示为 `[引用消息] 原回复正文`，不会无限递归展开

## 5. 联系人显示名称优先级

通过 `display_name_priority` 配置，按列表顺序尝试：
```jsonc
"display_name_priority": ["group_nickname", "nickname", "remark"]
```

- `group_nickname`：从 `contact.db` 的 `chat_room` 表解析 `ext_buffer` 中的 protobuf 成员列表获取群昵称
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

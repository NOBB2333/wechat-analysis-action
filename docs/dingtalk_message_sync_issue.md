# 钉钉本地数据库消息缺失 / 同步异常（疑似问题记录）

> **2026-06-30 更新：已定位根因并修复。** 问题不是消息没落到本地，而是原来的解密脚本只解密了主库 `dingtalk.db`，没有处理同样被加密的 WAL 文件 `dingtalk.db-wal`。钉钉的近期消息（包括 `helo`、`好，你好`）都保存在 WAL 里，解密合并后数据已恢复正常。

## 现象

在钉钉 PC 客户端里能看到完整会话和近期消息（例如“提醒推送小助手”里的 `helo`、`好，你好` 等），但解密后的本地 SQLite 数据库 `dingtalk.db` 中对应会话几乎没有消息。

- 会话 `65568709968`（提醒推送小助手）在 `tbconversation` 中存在，但：
  - `lastMid = 0`
  - `lastModify = 2025-03-11`（远早于 APP 中可见的新消息时间）
  - 所有 128 张分表 `tbmsg_000` ~ `tbmsg_127` 中均无该 cid 的消息
  - `tblastmsg` 中亦无该 cid 记录
- 整个 `dingtalk.db` 所有分表合计仅约 26 条消息，分布稀疏，且多为很早的历史数据。
- 同一账号、同一台机器上，微信/企业微信本地库的消息完整性明显好于钉钉。

## 已检查项

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| 原始加密 `dingtalk.db` | 存在 | `C:\Users\hl\AppData\Roaming\DingTalk\edb0646a4ee08ab16913_v3\DBFiles\dingtalk.db` |
| WAL 文件 `dingtalk.db-wal` | 约 2 MB | 已用 UTF-8 字节逐字搜索 `helo`、`你好`，无匹配 |
| SHM 文件 | 存在 | 无可见明文消息 |
| 解密是否正确 | 正确 | 解密后文件头为 `SQLite format 3\x00`，与工作库一致 |
| 重新解密原始文件 | 相同结果 | 重新生成 `dingtalk_original_decrypted.db`，消息数与现有解密库一致 |
| 所有消息相关表 | 已枚举 | 仅 128 张 `tbmsg_*` 分表 + `tblastmsg`，未发现其它消息表 |
| 联系人/会话表 | 正常 | `tbconversation`、`tbuser_profile_v2` 等数据存在 |

## 关键疑点

1. **APP 中可见的消息在本地任何文件中都不存在**
   - 不仅是解密后的数据库没有，连原始加密的 DB 和 WAL 中也没有对应文本的字节序列。
   - 这与“本地只保留部分消息，其余在云端”的假设不完全吻合：即使是云端消息，通常也会在本地有占位、索引或缓存。

2. **`lastModify` 与 APP 实际状态严重不符**
   - `tbconversation.lastModify` 停留在 2025-03-11，说明本地库自那以后几乎没有被钉钉写入新的会话状态。
   - 但 APP 中近期（2026-06-29/30）仍在收发消息。

3. **消息总数异常少**
   - 对于一个经常使用的账号，本地 `tbmsg_*` 合计仅 26 条消息不合理。
   - 可能存在：
     - 钉钉把消息写入到了另一个未被发现的本地存储（内存、临时文件、LevelDB、其它 DB 路径）
     - WAL 未 checkpoint 到主库，但 WAL 中也找不到明文
     - 钉钉新版本改变了本地落盘策略，默认不再本地保存消息正文

## 可能原因（待进一步验证）

1. **钉钉使用新的本地存储位置或格式**
   - 可能在 `%LOCALAPPDATA%\DingTalk`、应用安装目录、或每个会话的独立缓存中。
2. **WAL/SHM 数据已加密或压缩**
   - 虽然能看到 WAL 文件，但消息可能以压缩/加密/二进制形式写入，导致简单字符串搜索失效。
3. **钉钉 7.x / 新架构把消息完全放在云端/内存**
   - 只在首次打开会话时拉取，关闭后不保留。
4. **当前解密的目标 DB 并非“主消息库”**
   - `DBFiles\dingtalk.db` 可能只是会话/联系人索引库，真正的消息库可能在其它目录或文件名中。

## 建议下一步排查

- [ ] 全盘搜索 `DingTalk` 目录下所有 `.db`、`.sqlite`、`-wal`、`-shm` 文件，列出大小和修改时间。
- [ ] 使用进程监控工具（如 Process Monitor）观察钉钉在打开某个会话、收发消息时写入/读取哪些文件。
- [ ] 对 `%LOCALAPPDATA%\DingTalk` 和 `%APPDATA%\DingTalk` 做全盘字符串搜索（原始字节）。
- [ ] 抓取钉钉网络请求，确认消息是否只在网络层，未落本地。
- [ ] 对比另一台已同步大量钉钉数据的机器，看本地库消息数是否正常。

## 修复结果

- 已更新 `core-dingtalk/decrypt_uid.py`：
  - 解密主库的同时解密 `-wal` 文件。
  - 按 SQLite WAL 校验和算法重新计算每一帧的校验和。
  - 通过 `PRAGMA wal_checkpoint` 把 WAL 合并进主库，输出单个自包含的 `dingtalk.db`。
- 重新解密后数据量：
  - `tbmsg_*` 消息总数从 **26 条**增加到 **65 条**。
  - 会话 `65568709968`（提醒推送小助手）从 **0 条**增加到 **3 条**，包含 `helo`、`好，你好` 和系统提示。
- 后端服务已重启，前端网页现在能看到完整消息。

## 相关文件/命令

- 解密脚本：`D:\4_Code\0_Github_Project\wechat-analysis\core-dingtalk\decrypt_uid.py`
- 钉钉平台读取：`D:\4_Code\0_Github_Project\wechat-analysis\core-dingtalk\chat_platform.py`
- 当前解密输出：`D:\4_Code\0_Github_Project\wechat-analysis\export_parse_result\decrypted_dingtalk\dingtalk.db`
- 原始加密源：`C:\Users\hl\AppData\Roaming\DingTalk\edb0646a4ee08ab16913_v3\DBFiles\dingtalk.db`

---

记录时间：2026-06-30

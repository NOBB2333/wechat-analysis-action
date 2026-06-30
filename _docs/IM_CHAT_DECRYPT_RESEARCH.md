# 企业微信 / 钉钉 / 飞书 聊天记录解密开源项目调研

> 调研日期：2026-06-27
> 目标：找到能实现类似微信分析项目（解密 → 查询 → 报告）的开源方案

---

## 一、调研总览

| 平台 | 本地数据库解密 | 开源项目成熟度 | 与当前项目集成难度 | 推荐方案 |
|------|---------------|---------------|-------------------|---------|
| **企业微信** | ✅ 已有方案 | ⭐⭐⭐⭐ 高 | 低（我们已在用的 wechat-decrypt 已支持） | 直接集成 |
| **钉钉** | ✅ 已有方案 | ⭐⭐⭐ 中 | 中（需适配解密逻辑） | 可集成 |
| **飞书** | ⚠️ 仅 Android 有逆向分析 | ⭐ 低 | 高（桌面端无现成工具） | 暂无可用方案 |

---

## 二、企业微信（WeCom / WXWork）

### 2.1 现有支持

**好消息：当前项目已经部分支持企业微信！**

在 `wechat.py:217-222` 已有配置：
```python
"wxwork_db_dir": "",
"wxwork_keys_file": os.path.join(EXPORT_DIR, "wxwork_keys.json"),
"wxwork_decrypted_dir": os.path.join(EXPORT_DIR, "wxwork_decrypted"),
"wxwork_export_dir": os.path.join(EXPORT_DIR, "wxwork_export"),
"wxwork_process": "WXWork.exe",
```

### 2.2 核心开源项目

#### 1. ylytdeng/wechat-decrypt（我们已在用的项目）
- **地址**: https://github.com/ylytdeng/wechat-decrypt
- **Stars**: 2,207+
- **状态**: 活跃维护
- **企业微信支持**: 实验性（Windows 5.x 实测可用）
- **功能**:
  - `find_wxwork_keys.py` — 从 WXWork 进程内存提取密钥
  - `decrypt_wxwork_db.py` — 解密企微数据库到 `wxwork_decrypted/`
  - `export_wxwork_messages.py` — 导出聊天记录
- **使用方式**:
  ```bash
  # 1. 启动企业微信并登录
  # 2. 提取企微 keys + 解密
  python find_wxwork_keys.py     # 自动检测 Documents\WXWork\\Data
  python decrypt_wxwork_db.py    # 解密到 wxwork_decrypted/
  # 3. (可选) 导出聊天记录
  python export_wxwork_messages.py
  ```
- **数据库位置**: `Documents\WXWork\{uid}\Data`
- **加密方式**: SQLCipher 4（与微信 4.0 相同）
- **结论**: **可直接使用，与当前项目架构完全兼容**

#### 2. aa24615/wework-msgaudit（Java SDK）
- **地址**: https://github.com/aa24615/wework-msgaudit
- **功能**: 企业微信会话内容存档 SDK（Java 版）
- **限制**: 这是官方 API 方式，需要企业管理员开通「会话内容存档」权限
- **不适合我们**: 需要企业合规配置，非本地逆向解密

#### 3. aa24615/wework-msgaudit-php（PHP SDK）
- **地址**: https://github.com/aa24615/wework-msgaudit-php
- **同上**: 官方 API 方式，不适合本地解密场景

#### 4. chinayin/WeworkChatSDK
- **地址**: https://github.com/chinayin/WeworkChatSDK
- **功能**: 企业微信会话存档 Java SDK 一键接入
- **限制**: 同样依赖官方 API 权限

### 2.3 企业微信数据目录结构

```
C:\Users\{用户名}\Documents\WXWork\
├── {uid}\
│   ├── {version}\
│   │   └── Data\
│   │       ├── message\       # 聊天记录数据库
│   │       ├── contact\       # 联系人数据库
│   │       ├── group\         # 群组数据库
│   │       └── ...
│   └── ...
```

### 2.4 推荐方案

**直接使用 `wechat-decrypt` 的企微支持**，我们项目已经通过 git submodule 引用了它。需要：
1. 完善 `wechat.py` 中 `cmd_setup` 对企微数据库目录的检测
2. 添加企微的 `query.py` 适配（企微数据库结构与微信类似但有差异）
3. 测试企微 SQLCipher 4 解密流程

---

## 三、钉钉（DingTalk）

### 3.1 核心开源项目

#### 1. p1g3/dingwave（推荐 ⭐）
- **地址**: https://github.com/p1g3/dingwave
- **Stars**: 80
- **语言**: Go + Vue（Web UI）
- **版本**: 仅支持 V2
- **功能**:
  - 钉钉数据库解密（V2 版本）
  - Web UI 可视化展示聊天记录
  - 会话列表（置顶/单聊/群聊）
  - 全局搜索聊天记录
  - 联系人列表查看
  - 消息类型解析（文本、图片、文件等）
- **解密原理**:
  - 数据库: `C:\Users\{用户名}\AppData\Roaming\DingTalk\{uid}_{version}\dingtalk.db`
  - 加密方式: AES-128-ECB，按 4096 字节页加密
  - V2 密钥: `MD5(uid).hex[:16]`（uid 为用户数字 ID）
- **使用方式**:
  ```bash
  # 解密后的数据库
  ./dingwave -d dingtalk.db
  # 加密的数据库
  ./dingwave -d dingtalk_encrypt.db -k 666165872
  # 保存解密后的数据库
  ./dingwave -d dingtalk_encrypt.db -k 666165872 -o dingtalk.db
  ```
- **局限**: 仅 V2，不支持最新 V3 版本

#### 2. E2ern1ty/dingwave-V3（推荐 ⭐⭐）
- **地址**: https://github.com/E2ern1ty/dingwave-V3
- **Stars**: 3（较新）
- **语言**: Python（纯 Python 解密）
- **版本**: 支持 V2 + V3
- **功能**:
  - 纯 Python 解密 V2 + V3 数据库
  - Web 界面浏览会话和消息
  - 20+ 种消息类型解析
  - 图片预览、附件导出、ZIP 打包下载
  - 导出 JSON 含 AI 友好的 `content` 字段
  - 每 4 小时自动增量同步
  - 完全离线
- **V3 解密原理**:
  - 加密方式: AES-128-ECB，按 4096 字节页加密
  - V3 密钥推导:
    ```
    1. 读取 {data_dir}/user_config → Base64 解码 → JSON → 取 salt 字段
    2. password = uid + salt
    3. PKCS5_PBKDF2_HMAC_SHA1(password, "666DingT", iterations=1000, dklen=32)
    4. MD5(32字节).hex()[:16] → 即为 AES-128 密钥
    ```
  - V3 的 uid: 9-10 位短数字 ID（从 `globalStorage/storage.db` 解密后查询）
- **项目结构**:
  ```
  ├── main.py            # 入口（uvicorn 服务器）
  ├── config.py          # 配置（自动检测 V2/V3）
  ├── decrypt.py         # 解密核心
  ├── parser.py          # 消息解析（128 个分片表 tbmsg_000–tbmsg_127）
  ├── exporter.py        # 导出 JSON + 附件打包
  └── web/               # FastAPI Web UI
  ```
- **使用方式**:
  ```bash
  git clone git@github.com:E2ern1ty/dingwave-V3.git
  cd dingwave-V3
  pip install -r requirements.txt
  python main.py
  # 浏览器访问 http://localhost:8090
  ```
- **局限**: 需要自行获取 uid（从 `globalStorage/storage.db` 或环境变量）

#### 3. 看雪论坛逆向分析帖
- **地址**: https://bbs.kanxue.com/thread-255356.htm
- **内容**: 钉钉 PC 版数据库解密算法分析
- **关键发现**: 密钥从 `mainframe.dll` 中的 `openDatabase` 函数获取
- **价值**: 提供了逆向分析思路，可作为补充参考

### 3.2 钉钉数据目录结构

```
C:\Users\{用户名}\AppData\Roaming\DingTalk\
├── {uid}_{version}\
│   ├── dingtalk.db          # 主数据库（加密）
│   ├── user_config          # 用户配置（含 salt）
│   └── ...
├── globalStorage\
│   └── storage.db           # 全局存储（含 uid 映射）
```

### 3.3 推荐方案

**使用 `dingwave-V3`**（纯 Python，支持 V2+V3），需要：
1. 将 `decrypt.py` 中的解密逻辑提取到我们项目的 `src/` 下
2. 适配 `query.py` 钉钉数据库的表结构（`tbmsg_000–tbmsg_127` 分片）
3. 添加钉钉专用的 `cmd_setup` 检测逻辑

---

## 四、飞书（Feishu / Lark）

### 4.1 现状分析

**飞书目前没有可用的本地数据库解密开源项目。**

搜索结果：
- 飞书桌面端使用 SQLCipher 加密本地数据库
- 仅有一篇掘金文章分析了 **Android 版**飞书的数据库 KEY（`messages.db`）
- 飞书官方提供了 `lark-cli`（API 方式），但不是本地逆向解密
- 没有任何开源项目实现了飞书桌面端数据库解密

### 4.2 已知技术信息

#### 掘金文章：Android 逆向分析
- **地址**: https://juejin.cn/post/7281162206946328613
- **数据库位置**: `databases/sdk_storage/{UID-MD5}/messages.db`
- **加密方式**: SQLCipher
- **调用栈**: 来自 `liblark.so` 的 Native 层调用
- **密钥发现**: 通过 Hook `memcpy` 函数，发现密钥与 `libsqlcipher.so` 相关
- **结论**: Android 端可以 Hook 获取密钥，但桌面端（Windows/macOS）无类似分析

#### 飞书桌面端推测
- 数据库位置可能在: `C:\Users\{用户名}\AppData\Roaming\Lark\` 或类似路径
- 加密方式: 大概率使用 SQLCipher（与 Android 端一致）
- 密钥来源: 可能从进程内存中动态生成（类似微信的方案）
- **逆向难度**: 高（需要分析 Electron/C++ 混合架构）

### 4.3 可能的替代方案

1. **lark-cli（官方 API）**
   - 地址: https://github.com/larksuite/cli
   - 功能: 200+ 命令覆盖消息、文档、日历等
   - 限制: 需要飞书开放平台应用权限，不是本地逆向

2. **手动逆向（如果需要）**
   - 参考微信的 `wx_key` 提取思路
   - 需要分析飞书桌面端的内存结构
   - 需要定位 SQLCipher 密钥的生成位置
   - 工具: x64dbg、IDA Pro、Frida

### 4.4 实际逆向分析结果（2026-06-27）

**重要发现：我们已定位飞书数据库并尝试解密！**

#### 数据库位置确认
```
C:\Users\hl\AppData\Roaming\LarkShell\sdk_storage\b0053a4db437a4e478a51902d307b471\
├── messages.db          # 聊天记录（4096 字节，加密）
├── im.db                # IM 相关（加密）
├── contact.db           # 联系人（加密）
├── settings.db          # 设置（2.9MB，加密）
├── calendar.db          # 日历（加密）
└── ...
```

#### 加密确认
- **所有数据库都是 SQLCipher 加密的**（在 liblark.dll 中确认）
- liblark.dll 包含 SQLCipher 配置：`cipher_page_size = 4096`、`cipher_hmac_algorithm`、`cipher_kdf_algorithm`
- 从进程内存中提取到密钥：`9F53A0261214FC365156E785004CF095A8F111CB5500B87B30945A9F79CF0C83`
- **但该密钥无法解密数据库**（HMAC 验证失败）

#### 可能的原因
1. 密钥可能用于其他数据库（非 sdk_storage）
2. SQLCipher 配置可能与标准不同（自定义 HMAC/KDF 算法）
3. 需要额外的 salt 或 IV
4. 数据库可能使用自定义加密方案

#### 详细进度
见 `feishu_parse/PROGRESS.md`

### 4.5 推荐方案

**飞书本地解密目前遇到技术瓶颈**。建议：
1. **优先完成企业微信和钉钉的集成**（有成熟方案）
2. **飞书后续路径**：
   - 使用 Frida Hook `sqlite3_key` 函数捕获实际密钥
   - 逆向分析 `liblark.dll` 中的密钥生成逻辑
   - 使用飞书开放平台 API 获取聊天记录（需要管理员权限）
   - 关注社区动态，看是否有新的开源项目出现

---

## 五、与当前项目的集成路径

### 5.1 企业微信（最优先）

**集成难度: ⭐ 低**

我们已经在用 `wechat-decrypt`，它已支持企微。需要：

1. **完善检测逻辑**（`wechat.py`）:
   ```python
   def detect_wxwork_db_dir():
       """检测企业微信数据库目录"""
       documents = os.path.join(os.environ.get("USERPROFILE", ""), "Documents", "WXWork")
       # 遍历 WXWork 目录找到最新的 Data 目录
       ...
   ```

2. **添加企微查询适配**（`src/query.py`）:
   - 企微数据库表结构与微信有差异
   - 需要适配 contact、message 等表的字段名

3. **更新 CLI 命令**:
   ```bash
   python wechat.py setup --platform wxwork --raw-key <key>
   python wechat.py decrypt --platform wxwork
   python wechat.py report --platform wxwork --groups <群名>
   ```

### 5.2 钉钉（次优先）

**集成难度: ⭐⭐ 中**

需要从 `dingwave-V3` 提取核心解密逻辑：

1. **提取解密模块**:
   - 从 `E2ern1ty/dingwave-V3/decrypt.py` 提取 AES-ECB 解密逻辑
   - 适配 V2 和 V3 两种密钥推导方式

2. **添加钉钉查询模块**:
   - 钉钉使用分片表 `tbmsg_000–tbmsg_127`
   - 需要实现跨表查询逻辑

3. **添加 uid 获取逻辑**:
   - 从 `globalStorage/storage.db` 解密获取 uid
   - 或提示用户手动输入

### 5.3 飞书（暂缓）

**集成难度: ⭐⭐⭐⭐ 高**

目前没有可用方案，建议：
- 使用飞书开放平台 API 获取聊天记录（需要企业管理员权限）
- 或等待社区出现新的逆向分析项目

---

## 六、搜索过程记录

### 6.1 搜索关键词与来源

| 搜索关键词 | 来源 | 主要发现 |
|-----------|------|---------|
| `企业微信 聊天记录 解密 开源 github` | DuckDuckGo (cn-zh) | wechat-decrypt 已支持企微；wework-msgaudit 是官方 API |
| `钉钉 聊天记录 解密 开源 github` | DuckDuckGo (cn-zh) | dingwave (V2)、dingwave-V3 (V2+V3)；看雪逆向帖 |
| `飞书 lark 聊天记录 解密 开源 导出` | DuckDuckGo (cn-zh) | 无本地解密工具；仅有 lark-cli (API) |
| `wechat-decrypt wxwork enterprise wechat` | DuckDuckGo (worldwide) | 确认 wechat-decrypt 支持企微实验性功能 |
| `dingwave 钉钉数据库解密 github p1g3` | DuckDuckGo (cn-zh) | dingwave 详细信息；dingwave-V3 补充 V3 支持 |
| `飞书 lark 桌面端 数据库 sqlite encrypted 本地聊天记录 逆向` | DuckDuckGo (cn-zh) | 仅 Android 逆向分析文章；桌面端无方案 |
| `gndlwch2w/wdecipher PyWxDump` | DuckDuckGo (worldwide) | WDecipher 是 PyWxDump 的压缩版 |
| `chatlog sjzar` | DuckDuckGo (worldwide) | 项目已被移除（收到微信官方函件） |

### 6.2 网页抓取记录

| URL | 内容摘要 |
|-----|---------|
| https://github.com/ylytdeng/wechat-decrypt | 确认企微支持：find_wxwork_keys.py + decrypt_wxwork_db.py |
| https://github.com/p1g3/dingwave | Go+Vue，V2 解密，Web UI，80 stars |
| https://github.com/E2ern1ty/dingwave-V3 | Python，V2+V3 解密，Web UI，纯 Python 实现 |
| https://github.com/sjzar/chatlog | 已被移除（合规风险），9.2k stars |
| https://juejin.cn/post/7281162206946328613 | 飞书 Android 逆向：SQLCipher，liblark.so |

### 6.3 排除的项目

| 项目 | 排除原因 |
|------|---------|
| aa24615/wework-msgaudit | 官方 API 方式，需企业管理员权限 |
| chinayin/WeworkChatSDK | 同上 |
| larksuite/cli | 官方 API 工具，非本地逆向解密 |
| sjzar/chatlog | 已被移除（合规风险） |

---

## 七、总结与下一步

### 可行性结论

| 平台 | 可行性 | 预计工作量 | 优先级 |
|------|--------|-----------|--------|
| 企业微信 | ✅ 高 | 1-2 天 | P0 |
| 钉钉 | ✅ 中 | 3-5 天 | P1 |
| 飞书 | ❌ 低 | 未知（需逆向） | P2（暂缓） |

### 下一步行动

1. **立即可做**:
   - 完善 `wechat.py` 对企微数据库的自动检测
   - 测试 `wechat-decrypt` 的企微解密流程
   - 适配企微数据库的 `query.py`

2. **短期（1-2 周）**:
   - 集成 `dingwave-V3` 的解密逻辑
   - 实现钉钉数据库的查询模块

3. **长期**:
   - 关注飞书逆向社区动态
   - 考虑是否需要自行逆向飞书桌面端

---

*文档生成时间: 2026-06-27T23:30:00+08:00*

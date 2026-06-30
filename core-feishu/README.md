# core-feishu — 飞书聊天记录解密

## 状态: ❌ 暂不可行

## 加密方案分析

通过逆向分析 `liblark.dll`（157MB），确认飞书使用 **SQLCipher** 加密本地数据库。

### 发现过程

1. **定位数据目录**: `%APPDATA%\LarkShell\sdk_storage\{uid_hash}\`
2. **确认加密**: 所有 `.db` 文件 header 均非 SQLite 格式
3. **确认 SQLCipher**: 在 liblark.dll 中搜索到 185 处 SQLCipher 相关字符串
4. **提取配置**: 从 DLL 中的 PRAGMA 语句提取加密参数
5. **尝试解密**: 多种密钥组合均失败
6. **发现障碍**: DLL 中发现密钥推导需要 `app_secret`（服务器端密钥）

### 加密参数（从 DLL 提取）

| 参数 | 值 | 来源 |
|------|-----|------|
| 加密库 | SQLCipher | DLL 中 185 处 SQLCipher 字符串 |
| cipher_compatibility | 4 | DLL 中 `PRAGMA cipher_compatibility = 4` |
| cipher_page_size | 4096 | DLL 中 `PRAGMA cipher_page_size = 4096` |
| cipher_use_hmac | OFF | DLL 中 `PRAGMA cipher_use_hmac = OFF` |
| kdf_iter | 4000 | DLL 中 `PRAGMA kdf_iter = 4000` |

### 密钥推导障碍

在 `liblark.dll` 中发现的密钥推导逻辑（`init_key_check.rs`）：

```
app_secret (服务器端密钥，登录后获取)
    ↓
device_factor (设备因子)
    ↓
SQLCipher 密钥
```

**关键问题**: `app_secret` 是飞书服务器在用户登录后下发的密钥，本地无法获取。DLL 中有 `app secret not init` 错误信息，证实该值在本地不存在。

## 数据目录

```
%APPDATA%\LarkShell\sdk_storage\{uid_hash}\
├── messages.db          # 消息（加密）
├── im.db                # IM 相关（加密）
├── contact.db           # 联系人（加密）
├── settings.db          # 设置（加密）
├── cipher.db            # 加密配置（加密）
├── calendar.db          # 日历（加密）
├── todo.db              # 待办（加密）
├── resource.db          # 资源（加密）
├── whisper_keys.dat     # 语音密钥（101字节）
└── ...
```

**uid_hash**: `b0053a4db437a4e478a51902d307b471`（用户目录名）

## 已尝试的解密方法

| 方法 | 结果 | 原因 |
|------|------|------|
| 标准 SQLCipher 4 | HMAC 验证失败 | 密钥不正确 |
| HMAC OFF 配置 | 仍然失败 | 密钥推导需要额外参数 |
| 内存中的密钥 `9F53A0...` | 无法解密 | 该密钥用于其他数据库 |
| device_id 推导 | 全部失败 | 不是密钥来源 |
| PBKDF2 各种组合 | 全部失败 | 缺少 app_secret |
| Frida hook sqlite3_key | 未捕获 | 数据库初始化后不再调用 |
| DLL 分析 | 发现需要 app_secret | 本地无法获取 |

## 替代方案

| 方案 | 说明 | 限制 |
|------|------|------|
| 飞书开放平台 API | 通过 API 获取聊天记录 | 需要企业管理员权限 |
| lark-cli | 飞书官方 CLI 工具 | 需要开放平台应用权限 |
| 等待社区逆向 | 关注看雪/GitHub | 时间不确定 |

## 文件说明

| 文件 | 职责 |
|------|------|
| `__init__.py` | 包初始化（占位） |

## 未来可能的突破方向

1. Frida 精确 hook `sqlcipher_codec_ctx_init` 函数
2. 分析 `init_key_check.rs` 的完整逻辑
3. 找到 `app_secret` 的本地存储位置
4. 飞书版本更新后重新分析

## 参考资料

- [掘金：Android 逆向飞书数据库 KEY](https://juejin.cn/post/7281162206946328613)
- 本项目逆向分析记录: `feishu_parse/docs/README.md`

"""
WeChat 4.1 聊天记录查询库 — 直接查询解密后的 SQLite 数据库
"""
import html
import os, hashlib, json, re, sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

try:
    import zstandard
except ImportError:
    zstandard = None

try:
    from paths import DECRYPTED_DIR
except ImportError:
    from .paths import DECRYPTED_DIR

def md5(s):
    return hashlib.md5(s.encode()).hexdigest()


# ── protobuf helper for chat_room.ext_buffer (group nicknames) ────────
def _decode_varint(data, pos):
    result = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def _parse_member_ext(data):
    """解析 chat_room.ext_buffer 中单个成员子消息。"""
    pos = 0
    wxid = None
    display = None
    while pos < len(data):
        tag, pos = _decode_varint(data, pos)
        field = tag >> 3
        wire = tag & 0x7
        if wire == 2:  # length-delimited
            length, pos = _decode_varint(data, pos)
            value = data[pos:pos + length]
            pos += length
            if field == 1:
                wxid = value.decode("utf-8", errors="ignore")
            elif field == 2:
                display = value.decode("utf-8", errors="ignore")
        elif wire == 0:  # varint
            _, pos = _decode_varint(data, pos)
        else:
            break
    return wxid, display


def _parse_chat_room_ext(buf):
    """解析 chat_room.ext_buffer，返回 {wxid: group_nickname}。"""
    pos = 0
    members = {}
    while pos < len(buf):
        tag, pos = _decode_varint(buf, pos)
        field = tag >> 3
        wire = tag & 0x7
        if field == 1 and wire == 2:  # repeated Member members
            length, pos = _decode_varint(buf, pos)
            member_data = buf[pos:pos + length]
            pos += length
            wxid, display = _parse_member_ext(member_data)
            if wxid:
                members[wxid] = display
        else:
            break
    return members


def _decompress_zstd(data):
    """如果数据是 zstd 压缩的，尝试解压；否则原样返回。"""
    if zstandard is None:
        return data
    if len(data) >= 4 and data[:4] == b'(\xb5/\xfd':
        try:
            return zstandard.ZstdDecompressor().decompress(data)
        except zstandard.ZstdError:
            pass
    return data


class WeChatDB:
    def __init__(self, decrypted_dir=None, self_wxid=None, self_name=None,
                 display_name_mode=None, display_name_priority=None):
        self.dir = decrypted_dir or DECRYPTED_DIR
        self._msg_conns = {}  # lazy-load per-DB connections
        self._contact_conn = None
        self._session_conn = None
        self._sender_cache = {}
        self._name2id_cache = {}
        self._global_name2id = None  # 跨 DB 的全局 Name2Id 缓存
        self._group_nick_cache = {}  # (chatroom, wxid) → 群昵称
        self._self_wxid = self_wxid
        self.self_name = self_name or "我"

        # 新版：优先级列表；旧版 display_name_mode 兼容
        if display_name_priority:
            self._name_priority = display_name_priority
        elif display_name_mode == "nickname":
            self._name_priority = ["nickname", "remark"]
        elif display_name_mode == "group_nickname":
            self._name_priority = ["group_nickname", "nickname", "remark"]
        else:
            self._name_priority = ["group_nickname", "nickname", "remark"]
        self.display_name_mode = display_name_mode  # 保留兼容

    @property
    def self_wxid(self):
        """检测当前设备主人的 wxid

        启发式方法: 在 contact.db 中找 remark 以 'HOME' 开头且有中文名缩写的联系人。
        'HOME  b1'、'HOME  m1' 等是亲属代号，'HOME  王c' 这种姓名缩写才是自己。
        """
        if self._self_wxid:
            return self._self_wxid
        if self.contact:
            rows = self.contact.execute(
                "SELECT username, remark FROM contact WHERE remark LIKE 'HOME%' AND username LIKE 'wxid_%'"
            ).fetchall()
            # 优先匹配中文姓名缩写模式 (姓+单字，如 'HOME  王c')
            for wxid, remark in rows:
                # 匹配: HOME + 空格 + 中文字符 + 单字母缩写
                if re.search(r'HOME\s+[一-鿿]+[a-z]', remark):
                    self._self_wxid = wxid
                    return self._self_wxid
            # 次选: 任何 HOME 联系人
            if rows:
                self._self_wxid = rows[0][0]
                return self._self_wxid
        self._self_wxid = "?"
        return self._self_wxid

    # ── connections ──────────────────────────────────────────────
    def _get_msg_dbs(self):
        """返回所有消息数据库路径列表 (按文件名排序)"""
        msg_dir = os.path.join(self.dir, "message")
        dbs = []
        for f in sorted(os.listdir(msg_dir)):
            if f.endswith(".db") and f.startswith("message_"):
                dbs.append(os.path.join(msg_dir, f))
        return dbs

    def _get_msg_conn(self, db_path):
        if db_path not in self._msg_conns:
            self._msg_conns[db_path] = sqlite3.connect(db_path)
        return self._msg_conns[db_path]

    def _load_name2id(self, db_path):
        """读取消息库中的 Name2Id 映射，用 real_sender_id 还原发送者。"""
        if db_path in self._name2id_cache:
            return self._name2id_cache[db_path]

        mapping = {}
        try:
            conn = self._get_msg_conn(db_path)
            rows = conn.execute("SELECT rowid, user_name FROM Name2Id").fetchall()
            mapping = {rowid: user_name for rowid, user_name in rows if user_name}
        except sqlite3.Error:
            mapping = {}

        self._name2id_cache[db_path] = mapping
        return mapping

    def _load_global_name2id(self):
        """跨所有消息库加载 Name2Id 映射，用于 sender 解析的兜底。"""
        if self._global_name2id is not None:
            return self._global_name2id
        mapping = {}
        for db_path in self._get_msg_dbs():
            try:
                conn = self._get_msg_conn(db_path)
                rows = conn.execute("SELECT rowid, user_name FROM Name2Id").fetchall()
                for rowid, user_name in rows:
                    if user_name and rowid not in mapping:
                        mapping[rowid] = user_name
            except sqlite3.Error:
                pass
        self._global_name2id = mapping
        return mapping

    @property
    def contact(self):
        if self._contact_conn is None:
            p = os.path.join(self.dir, "contact", "contact.db")
            if os.path.exists(p):
                self._contact_conn = sqlite3.connect(p)
        return self._contact_conn

    @property
    def session(self):
        if self._session_conn is None:
            p = os.path.join(self.dir, "session", "session.db")
            if os.path.exists(p):
                self._session_conn = sqlite3.connect(p)
        return self._session_conn

    def close(self):
        for c in self._msg_conns.values():
            c.close()
        if self._contact_conn:
            self._contact_conn.close()
        if self._session_conn:
            self._session_conn.close()

    # ── table resolution ─────────────────────────────────────────
    def find_msg_table(self, username):
        """在全部 message DB 中查找 username 对应的 Msg_<hash> 表"""
        table_name = f"Msg_{md5(username)}"
        for db_path in self._get_msg_dbs():
            conn = self._get_msg_conn(db_path)
            r = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            ).fetchone()
            if r:
                return db_path, table_name
        return None, None

    # ── sender display name ──────────────────────────────────────
    def _get_group_nickname(self, wxid, chatroom):
        """查询成员在某个群里的群昵称（缓存）。

        群昵称存储在 contact.db 的 chat_room.ext_buffer 字段中，
        是 protobuf 编码的成员列表；这里用最小解析器提取。
        """
        if not self.contact or not chatroom:
            return None
        key = (chatroom, wxid)
        if key in self._group_nick_cache:
            return self._group_nick_cache[key]

        nick = None
        try:
            row = self.contact.execute(
                "SELECT ext_buffer FROM chat_room WHERE username=?",
                (chatroom,),
            ).fetchone()
            if row and row[0]:
                members = _parse_chat_room_ext(row[0])
                nick = members.get(wxid)
        except sqlite3.Error:
            nick = None

        self._group_nick_cache[key] = nick
        return nick

    def get_display_name(self, wxid, chatroom=None):
        """通过 wxid 查显示名（带缓存）。

        按 self._name_priority 列表顺序依次尝试，
        前面的来源找不到就尝试下一个。
        默认优先级: group_nickname → nickname → remark。
        """
        if wxid in self._sender_cache:
            return self._sender_cache[wxid]

        if not self.contact:
            self._sender_cache[wxid] = wxid
            return wxid

        row = self.contact.execute(
            "SELECT nick_name, remark FROM contact WHERE username=?",
            (wxid,)
        ).fetchone()
        if not row:
            self._sender_cache[wxid] = wxid
            return wxid

        nick_name, remark = row
        group_nick = self._get_group_nickname(wxid, chatroom) if chatroom else None

        name = None
        for source in self._name_priority:
            if source == "group_nickname" and group_nick:
                name = group_nick
                break
            elif source == "nickname" and nick_name:
                name = nick_name
                break
            elif source == "remark" and remark:
                name = remark
                break

        if not name:
            name = group_nick or nick_name or remark or wxid
        self._sender_cache[wxid] = name
        return name

    # ── chatroom metadata ────────────────────────────────────────
    def get_chatroom_name(self, username):
        """获取群聊的显示名称 (来自 contact.db 的 nick_name/remark)"""
        if not self.contact:
            return username
        row = self.contact.execute(
            "SELECT nick_name, remark FROM contact WHERE username=?",
            (username,)
        ).fetchone()
        if row:
            return row[1] or row[0] or username
        return username

    # ── message query ────────────────────────────────────────────
    def query_messages(self, username, start_time=None, end_time=None, limit=500):
        """
        查询指定会话的消息。
        start_time, end_time: datetime 对象或时间戳(秒)
        返回: list[dict]
        """
        db_path, table = self.find_msg_table(username)
        if not table:
            return []

        conn = self._get_msg_conn(db_path)
        cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{table}")')]
        has_packed = "packed_info_data" in cols

        if start_time and isinstance(start_time, datetime):
            start_time = int(start_time.timestamp())
        if end_time and isinstance(end_time, datetime):
            end_time = int(end_time.timestamp())

        sql = f'SELECT * FROM "{table}"'
        conditions = []
        params = []
        if start_time:
            conditions.append("create_time >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("create_time < ?")
            params.append(end_time)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY create_time DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()

        # 解析消息
        messages = []
        for row in rows:
            m = dict(zip(cols, row))
            m["_db_path"] = db_path
            m["content_text"] = self._parse_content(m, chatroom=username)
            messages.append(m)
        return messages

    def _try_decode(self, data):
        """尝试将 bytes 解码为 UTF-8 文本"""
        if isinstance(data, str):
            return data
        if isinstance(data, bytes):
            # 先解压 zstd（微信 4.x 部分消息用 zstd 压缩 protobuf）
            data = _decompress_zstd(data)

            # 优先提取外层 XML：找到第一个 XML 标记，再往前找最近的 :\n。
            # 这能避免把 refermsg/content 里被引用的 wxid_:\n 或内嵌 XML 误当主消息。
            xml_start = -1
            for tag in (b'<?xml', b'<msg>', b'<msg ', b'<appmsg', b'<sysmsg',
                        b'<emoji ', b'<gameext', b'<hardlink',
                        b'<favitem', b'<mmreader'):
                pos = data.find(tag)
                if pos >= 0 and (xml_start < 0 or pos < xml_start):
                    xml_start = pos
            if xml_start > 0:
                # 找 XML 标记之前、且离标记不太远的 :\n 分隔符
                sep = data.rfind(b':\n', 0, xml_start)
                if sep >= 0 and xml_start - sep < 200:
                    text = data[sep + 2:]
                    decoded = self._safe_decode(text)
                    if decoded and decoded.strip().startswith('<'):
                        return self._strip_binary(decoded)

            # zstd 解压后或 protobuf 中可能出现纯 XML，没有 sender 前缀
            if xml_start == 0:
                decoded = self._safe_decode(data)
                if decoded and decoded.strip().startswith('<'):
                    return self._strip_binary(decoded)

            # protobuf 编码的消息: 先找 wxid:\n 分隔符
            if len(data) > 2 and data[:2] == b'(\xb5':
                sep = data.find(b':\n')
                if sep >= 0 and sep < 100:
                    text = data[sep+2:]
                    decoded = self._safe_decode(text)
                    if decoded:
                        return self._strip_binary(decoded)
                # 没有 :\n 分隔符 → 尝试在 protobuf 中提取 XML
                if xml_start > 0 and xml_start < len(data) - 20:
                    decoded = data[xml_start:].decode("utf-8", errors="ignore")
                    if decoded.strip().startswith('<') and len(decoded.strip()) > 10:
                        return self._strip_binary(decoded)
                return None

            # 无 (\xb5 前缀：完整 protobuf 消息或其他编码 → 搜索 wxid_ 模式
            wxid_pos = data.find(b'wxid_')
            if wxid_pos >= 0:
                sep = data.find(b':\n', wxid_pos)
                if sep >= 0 and sep - wxid_pos < 80:
                    text = data[sep+2:]
                    decoded = self._safe_decode(text)
                    if decoded:
                        return self._strip_binary(decoded)

            # 兜底：直接 UTF-8 解码
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return None
        return None

    def _safe_decode(self, data):
        """解码 bytes 并判断是否为可读文本（而非压缩数据乱码）。

        用宽松 UTF-8 解码以容忍微信消息中的少量非 UTF-8 字节（如
        protobuf 包装），然后通过多个条件判断是否为真实文本。
        压缩数据的随机字节几乎都不是合法 UTF-8，会被 errors="ignore"
        大量丢弃，导致解码后字符数远小于原始字节数。真实文本则相反。
        """
        if isinstance(data, str):
            return data
        decoded = data.decode("utf-8", errors="ignore")
        if not decoded.strip():
            return None
        total = len(decoded)
        # 字节有效率：真实文本 > 15%，压缩数据远低于此
        raw_len = len(data)
        if raw_len > 0 and total / raw_len < 0.15:
            return None
        # CJK 字符计数 — 压缩数据几乎不会产生 CJK
        cjk = sum(1 for c in decoded if '一' <= c <= '鿿')
        if cjk >= 1:
            return self._strip_binary(decoded)
        # XML 检测
        if decoded.strip().startswith('<') and total > 10:
            return self._strip_binary(decoded)
        # 纯 ASCII/英文：要求可打印字符占比高
        if total > 5:
            printable = sum(1 for c in decoded if c in '\n\r\t ' or
                           (' ' <= c <= '~') or
                           ('一' <= c <= '鿿') or
                           ('　' <= c <= '〿') or
                           ('＀' <= c <= '￯'))
            if printable / total >= 0.85:
                return self._strip_binary(decoded)
        # 短文本：全部可打印就接受
        if total <= 5 and all(c in '\n\r\t ' or ' ' <= c <= '~' for c in decoded):
            return decoded
        return None

    def _strip_binary(self, text):
        """去除文本末尾的二进制垃圾（控制字符、非可读字节）"""
        # 截断在第一个连续的控制字符序列处
        result = []
        consecutive_ctrl = 0
        for ch in text:
            cp = ord(ch)
            # 允许: 换行、回车、tab、CJK、ASCII可打印、常见 Unicode 标点
            if ch in '\n\r\t' or (32 <= cp <= 126) or (0x4E00 <= cp <= 0x9FFF) or \
               (0x3000 <= cp <= 0x303F) or (0xFF00 <= cp <= 0xFFEF) or \
               (0x2000 <= cp <= 0x206F):
                result.append(ch)
                consecutive_ctrl = 0
            elif cp < 32 or (0x7F <= cp <= 0x9F):
                # C0/C1 控制字符
                consecutive_ctrl += 1
                if consecutive_ctrl >= 3:
                    break  # 连续控制字符 → 二进制垃圾，截断
            else:
                # emoji 和其他符号
                result.append(ch)
                consecutive_ctrl = 0
        return ''.join(result).rstrip()

    def _split_msg_type(self, t):
        """微信会把 app 子类型打包进高 32 位，低 32 位才是基础消息类型。"""
        try:
            t = int(t)
        except (TypeError, ValueError):
            return 0, 0
        if t > 0xFFFFFFFF:
            return t & 0xFFFFFFFF, t >> 32
        return t, 0

    def _parse_xml_root(self, text):
        if not text:
            return None
        try:
            return ET.fromstring(text)
        except ET.ParseError:
            try:
                return ET.fromstring(html.unescape(text))
            except ET.ParseError:
                return None

    def _xml_text(self, node, path):
        if node is None:
            return ""
        text = node.findtext(path) or ""
        return re.sub(r"\s+", " ", text).strip()

    def _summarize_refer_content(self, refer_type, content, max_len=160):
        labels = {
            "3": "图片", "34": "语音", "42": "名片", "43": "视频",
            "47": "动画表情", "48": "位置", "50": "通话",
        }
        refer_type = str(refer_type or "").strip()
        content = html.unescape(content or "")

        if refer_type == "1":
            text = re.sub(r"\s+", " ", content).strip()
            return text[:max_len] + "..." if len(text) > max_len else text

        if refer_type == "49":
            root = self._parse_xml_root(content)
            appmsg = root.find(".//appmsg") if root is not None else None
            app_type = self._xml_text(appmsg, "type")
            title = self._xml_text(appmsg, "title")
            nested_labels = {
                "5": "链接", "6": "文件", "19": "聊天记录",
                "33": "小程序", "36": "小程序", "57": "引用消息",
                "2000": "转账", "2001": "红包",
            }
            label = nested_labels.get(app_type, "卡片")
            return f"[{label}] {title}" if title else f"[{label}]"

        if refer_type in labels:
            return f"[{labels[refer_type]}]"
        return f"[type={refer_type}]" if refer_type else "[引用消息]"

    def _format_refer_message(self, content, chatroom=None):
        """渲染 appmsg type=57 的引用回复。

        格式: 回复正文 {{引用消息 HH:MM 发送者 发送内容：被引用内容摘要}}
        """
        root = self._parse_xml_root(content)
        appmsg = root.find(".//appmsg") if root is not None else None
        if appmsg is None:
            return None

        app_type = self._xml_text(appmsg, "type")
        if app_type != "57":
            return None

        reply_text = self._xml_text(appmsg, "title") or ""
        refer = appmsg.find("refermsg")
        if refer is None:
            return reply_text if reply_text else None

        refer_type = self._xml_text(refer, "type")
        refer_content = refer.findtext("content") or ""
        summary = self._summarize_refer_content(refer_type, refer_content)

        # 被引用消息的发送者和时间
        # fromusr 是群聊 id，chatusr 才是被引用人的 wxid
        sender_wxid = self._xml_text(refer, "chatusr")
        display = self._xml_text(refer, "displayname")
        sender_label = self.get_display_name(sender_wxid, chatroom=chatroom) if sender_wxid else display
        if not sender_label:
            sender_label = display

        refer_time = ""
        try:
            ct = int(self._xml_text(refer, "createtime"))
            refer_time = datetime.fromtimestamp(ct).strftime("%H:%M")
        except (ValueError, OSError):
            pass

        # 组装成 {{引用消息 HH:MM 发送者 发送内容：摘要}}
        meta_parts = "引用消息"
        if refer_time:
            meta_parts += f" {refer_time}"
        if sender_label:
            meta_parts += f" {sender_label}"
        meta_parts += f" 发送内容：{summary}"
        ref_tag = "{{" + meta_parts + "}}"

        if reply_text:
            return f"{reply_text} {ref_tag}"
        return ref_tag

    def _format_app_message(self, content):
        """渲染普通 appmsg（链接、文件、小程序等），非引用回复。"""
        root = self._parse_xml_root(content)
        appmsg = root.find(".//appmsg") if root is not None else None
        if appmsg is None:
            return None

        app_type = self._xml_text(appmsg, "type")
        title = self._xml_text(appmsg, "title")
        url = self._xml_text(appmsg, "url")
        des = self._xml_text(appmsg, "des")

        labels = {
            "5": "链接", "6": "文件", "19": "聊天记录",
            "33": "小程序", "36": "小程序", "57": "引用消息",
            "2000": "转账", "2001": "红包",
        }
        label = labels.get(app_type, "卡片")

        if app_type == "5" and title:
            if url:
                return f"[{label}] {title} {url}"
            return f"[{label}] {title}"
        if app_type == "6" and title:
            return f"[{label}] {title}"
        if title:
            return f"[{label}] {title}"
        if des:
            return f"[{label}] {des}"
        return f"[{label}]"

    def _parse_content(self, m, chatroom=None):
        """从 message_content 中提取可读文本"""
        content = m.get("message_content")
        local_type = m.get("local_type", 0)
        base_type, _ = self._split_msg_type(local_type)
        if not content:
            return "" if base_type == 1 else self._type_label(local_type)

        # 已知的纯二进制媒体类型 — 跳过 _try_decode，直接返回标签。
        # 避免 protobuf 中的 0x3C 等字节被误判为可读文本。
        _BINARY_MEDIA_TYPES = {3, 34, 42, 43, 47, 48, 50, 62}
        if isinstance(content, bytes) and base_type in _BINARY_MEDIA_TYPES:
            if len(content) > 2 and content[:2] == b'(\xb5':
                return self._type_label(local_type)

        # 对于可读文本类型，尝试解析
        if isinstance(content, bytes):
            text = self._try_decode(content)
            if text is None:
                return self._type_label(local_type)
            content = text

        # 文本类型 (type=1 或 type=47)
        # 格式可能是: "sender_wxid:\ntext" 或纯文本
        if ":\n" in content and not content.startswith("<") and not content.startswith("<?xml"):
            parts = content.split(":\n", 1)
            if len(parts) == 2 and len(parts[0]) < 80 and "\n" not in parts[0]:
                content = parts[1]

        if base_type == 49:
            refer = self._format_refer_message(content, chatroom=chatroom)
            if refer:
                return refer
            app = self._format_app_message(content)
            if app:
                return app
        return content

    def _type_label(self, local_type):
        """根据 local_type 返回消息类型标签"""
        labels = {
            1: "[文本]",
            3: "[图片]", 34: "[语音]", 42: "[名片]", 43: "[音视频通话]",
            47: "[表情]", 48: "[位置]", 49: "[分享/链接]",
            50: "[音视频通话]", 62: "[小视频]", 66: "[第三方链接]",
            268435456: "[红包]", 10000: "[系统消息]", 10002: "[系统消息]",
        }
        if local_type in labels:
            return labels[local_type]
        # 带子类型的大数字 — 拆分 base_type 和 sub_type
        if local_type > 1000000:
            base_type, sub_type = self._split_msg_type(local_type)
            sub_labels = {
                57: "[引用消息]",
                5: "[链接]",
                6: "[文件]",
                33: "[小程序]",
                36: "[小程序]",
                62: "[系统消息]",
                2000: "[转账]",
                2001: "[红包]",
            }
            if sub_type in sub_labels:
                return sub_labels[sub_type]
            if base_type in labels:
                return labels[base_type]
            return "[富媒体消息]"
        return f"[消息类型 {local_type}]"

    def _parse_sender(self, m):
        """从消息中提取发送者 wxid"""
        content = m.get("message_content")
        db_path = m.get("_db_path")

        # 先查当前 DB 的 Name2Id，找不到再查全局
        real_sender_id = m.get("real_sender_id")
        if real_sender_id is not None:
            if db_path:
                sender = self._load_name2id(db_path).get(real_sender_id)
                if sender:
                    return sender
            sender = self._load_global_name2id().get(real_sender_id)
            if sender:
                return sender

        # 先处理 protobuf 包装的 bytes 内容 — 从 wxid_ 前缀提取
        if isinstance(content, bytes) and content[:2] == b'(\xb5':
            wxid_start = content.find(b'wxid_')
            if wxid_start >= 0:
                sep = content.find(b':\n', wxid_start)
                if sep >= 0 and sep - wxid_start < 80:
                    try:
                        wxid = content[wxid_start:sep].decode("utf-8")
                        if '\n' not in wxid:
                            return wxid
                    except UnicodeDecodeError:
                        pass
            return None

        text = self._try_decode(content) if isinstance(content, bytes) else content

        if text and ":\n" in text and not text.startswith("<") and not text.startswith("<?xml"):
            parts = text.split(":\n", 1)
            if len(parts) == 2 and len(parts[0]) < 80 and "\n" not in parts[0]:
                return parts[0]

        # 从 source 列尝试提取 (二进制 protobuf 中可能包含 sender)
        source = m.get("source")
        if source and isinstance(source, bytes):
            src_text = self._try_decode(source)
            if src_text and ":\n" in src_text:
                parts = src_text.split(":\n", 1)
                if len(parts) == 2 and len(parts[0]) < 80:
                    return parts[0]

        return None

    def format_messages(self, messages, include_system=False, chatroom=None):
        """将消息列表格式化为 LLM 可读文本

        chatroom: 群聊的 wxid/username，用于 group_nickname 模式查群昵称。
        """
        lines = []
        for m in reversed(messages):  # 正序输出
            local_type = m.get("local_type", 0)
            text = m.get("content_text", "")

            # 跳过空消息和太短的非文本消息
            if not text and local_type != 1:
                continue
            if not include_system and local_type != 1:
                # 非文本消息只在有标签时显示
                if not text.startswith("["):
                    continue

            ts = m.get("create_time", 0)
            dt = datetime.fromtimestamp(ts).strftime("%H:%M") if ts else "??"
            sender = self._parse_sender(m)
            if sender:
                display = self.get_display_name(sender, chatroom=chatroom)
            elif m.get("real_sender_id") == 2:
                display = self.self_name
            else:
                display = "?"
            lines.append(f"[{dt}] {display}: {text}")
        return "\n".join(lines)

    def normalize_messages(self, messages, include_system=False, chatroom=None):
        """返回带 sender/time/text 的标准消息列表，供统计和报告使用。

        chatroom: 群聊的 wxid/username，用于 group_nickname 模式查群昵称。
        """
        normalized = []
        for m in reversed(messages):
            local_type = m.get("local_type", 0)
            text = m.get("content_text", "")
            if not text and local_type != 1:
                continue
            # 默认过滤掉纯系统消息；其他非文本消息只要解析出可读文本就保留
            # （引用回复、带标签的图片/语音等都会保留）。
            if not include_system and local_type in (10000, 10002):
                continue

            ts = m.get("create_time", 0)
            dt = datetime.fromtimestamp(ts) if ts else None
            sender = self._parse_sender(m)
            if sender:
                display = self.get_display_name(sender, chatroom=chatroom)
                sender_id = sender
            elif m.get("real_sender_id") == 2:
                display = self.self_name
                sender_id = self._self_wxid or "self"
            else:
                display = "?"
                sender_id = "unknown"
            normalized.append({
                "time": dt,
                "time_text": dt.strftime("%H:%M") if dt else "??",
                "hour": dt.hour if dt else None,
                "sender": display,
                "sender_id": sender_id,
                "text": text,
                "local_type": local_type,
            })
        return normalized

    # ── session listing ──────────────────────────────────────────
    def list_sessions(self, name_filter=None):
        """列出所有会话 (按最近活动排序)"""
        if not self.session:
            return []
        sql = "SELECT username, type, summary, last_timestamp, unread_count FROM SessionTable"
        params = []
        if name_filter:
            sql += " WHERE (username LIKE ? OR summary LIKE ?)"
            params = [f"%{name_filter}%", f"%{name_filter}%"]
        sql += " ORDER BY sort_timestamp DESC LIMIT 100"
        rows = self.session.execute(sql, params).fetchall()
        results = []
        for row in rows:
            username, stype, summary, ts, unread = row
            # timestamp is in seconds
            try:
                dt = datetime.fromtimestamp(ts) if ts else None
            except (OSError, ValueError):
                dt = None
            name = self.get_chatroom_name(username) if "@chatroom" in username else username
            results.append({
                "username": username,
                "display_name": name,
                "type": stype,
                "summary": (summary or "").replace("\n", " "),
                "last_time": dt.strftime("%Y-%m-%d %H:%M") if dt else "N/A",
                "unread": unread,
            })
        return results


# ── convenience ──────────────────────────────────────────────────
def load_config():
    """从 all_keys.json 加载配置"""
    keys_file = os.path.join(os.path.dirname(__file__), "all_keys.json")
    if not os.path.exists(keys_file):
        # fallback: look in current dir
        keys_file = "all_keys.json"
    with open(keys_file) as f:
        return json.load(f)

"""DingTalk platform - reads from pre-decrypted database."""
import os
import sqlite3
import json
from datetime import datetime
from typing import List, Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.platform_base import BasePlatform, ChatMessage, ChatSession, Contact

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECRYPTED_DB = os.path.join(_PROJECT_ROOT, "export_parse_result", "decrypted_dingtalk", "dingtalk.db")


def _parse_json_field(value):
    """Safely parse a JSON field."""
    if not value:
        return {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


def _extract_display_name(title, extension):
    """Extract a human-readable display name from conversation metadata."""
    ext = _parse_json_field(extension)
    u_name_locale = ext.get("u_name_locale") or {}
    if isinstance(u_name_locale, str):
        u_name_locale = _parse_json_field(u_name_locale)
    if isinstance(u_name_locale, dict):
        for key in ("zh_CN", "zh_TW", "en_US"):
            name = u_name_locale.get(key)
            if name:
                return name
    name = ext.get("name") or title
    return name or ""


def _extract_text_from_content(content, extension):
    """Extract display text from a DingTalk message content/extension blob."""
    c = _parse_json_field(content)
    if "text" in c:
        return str(c["text"])

    # Card / interactive messages
    ext = _parse_json_field(extension)
    card_text = (
        ext.get("interactiveCardLastMessage")
        or (ext.get("attachments") or [{}])[0].get("extension", {}).get("interactiveCardLastMessage")
    )
    if card_text:
        return str(card_text)

    # Rich content fallback
    if c:
        return str(c)
    return ""


def _format_time(ts_ms: int) -> str:
    """Format millisecond timestamp to a readable string."""
    if not ts_ms:
        return ""
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


class DingTalkPlatform(BasePlatform):
    name = "dingtalk"
    display_name = "钉钉"

    def __init__(self, data_dir: str = None, **kwargs):
        super().__init__(data_dir=data_dir, **kwargs)
        self._conn = None
        self._contacts_cache = {}
        self._self_uid = None

    def detect_data_dir(self) -> Optional[str]:
        if os.path.exists(DECRYPTED_DB):
            return DECRYPTED_DB
        appdata = os.environ.get("APPDATA", "")
        dt_dir = os.path.join(appdata, "DingTalk")
        if not os.path.isdir(dt_dir):
            return None
        for entry in os.listdir(dt_dir):
            entry_path = os.path.join(dt_dir, entry)
            if os.path.isdir(entry_path):
                db_path = os.path.join(entry_path, "DBFiles", "dingtalk.db")
                if os.path.exists(db_path):
                    return db_path
        return None

    def _get_conn(self):
        if self._conn:
            return self._conn
        db = self.data_dir or DECRYPTED_DB
        if not os.path.exists(db):
            return None
        try:
            self._conn = sqlite3.connect(db)
            self._conn.execute("SELECT count(*) FROM sqlite_master")
            return self._conn
        except Exception:
            return None

    def _infer_self_uid(self):
        """Infer current user UID from conversation cids."""
        if self._self_uid is not None:
            return self._self_uid
        conn = self._get_conn()
        if not conn:
            return None
        try:
            from collections import Counter
            cids = conn.execute("SELECT cid FROM tbconversation").fetchall()
            counter = Counter()
            for (cid,) in cids:
                if not cid:
                    continue
                for part in str(cid).split(":"):
                    if part.isdigit():
                        counter[int(part)] += 1
            if counter:
                self._self_uid = counter.most_common(1)[0][0]
        except Exception:
            pass
        return self._self_uid

    def _load_contacts(self):
        """Preload contacts into cache for name resolution."""
        if self._contacts_cache:
            return
        conn = self._get_conn()
        if not conn:
            return
        try:
            rows = conn.execute(
                "SELECT uid, nick, alias, mobile FROM tbuser_profile_v2 LIMIT 5000"
            ).fetchall()
            for uid, nick, alias, mobile in rows:
                self._contacts_cache[str(uid)] = Contact(
                    user_id=str(uid),
                    nickname=str(nick or ""),
                    remark=str(alias or ""),
                )
        except Exception:
            pass

    def _count_messages(self, cids: List[str]) -> dict:
        """Count actual messages per conversation by scanning tbmsg_* tables."""
        conn = self._get_conn()
        if not conn or not cids:
            return {}
        counts = {}
        try:
            placeholders = ",".join("?" * len(cids))
            for i in range(128):
                table = f"tbmsg_{i:03d}"
                try:
                    rows = conn.execute(
                        f'SELECT cid, COUNT(*) FROM "{table}" WHERE cid IN ({placeholders}) GROUP BY cid',
                        tuple(cids),
                    ).fetchall()
                    for cid, c in rows:
                        counts[str(cid)] = counts.get(str(cid), 0) + c
                except Exception:
                    continue
        except Exception:
            pass
        return counts

    def _get_last_messages(self, cids: List[str]) -> dict:
        """Fetch last messages for given conversation IDs from tblastmsg."""
        conn = self._get_conn()
        if not conn or not cids:
            return {}
        result = {}
        try:
            placeholders = ",".join("?" * len(cids))
            rows = conn.execute(
                f"SELECT cid, senderId, createdAt, content, extension FROM tblastmsg WHERE cid IN ({placeholders})",
                tuple(cids),
            ).fetchall()
            for cid, sender_id, created_at, content, extension in rows:
                text = _extract_text_from_content(content, extension)
                sid = str(sender_id or "")
                is_self = sid and self._self_uid is not None and int(sid) == self._self_uid
                if is_self and not text:
                    text = "[你发送了一条消息]"
                result[str(cid)] = {
                    "sender_id": sid,
                    "created_at": created_at or 0,
                    "text": text,
                }
        except Exception:
            pass
        return result

    def list_sessions(self, limit: int = 100) -> List[ChatSession]:
        conn = self._get_conn()
        if not conn:
            return []
        result = []
        try:
            self._load_contacts()
            self._infer_self_uid()
            rows = conn.execute(
                "SELECT cid, title, type, lastMid, unreadCount, lastModify, extension FROM tbconversation "
                "ORDER BY lastModify DESC LIMIT ?", (limit,)
            ).fetchall()

            cids = [str(r[0]) for r in rows]
            last_msgs = self._get_last_messages(cids)
            msg_counts = self._count_messages(cids)

            for cid, title, ctype, last_mid, unread, last_modify, extension in rows:
                cid_str = str(cid)
                last_msg = last_msgs.get(cid_str, {})
                display_name = _extract_display_name(title, extension)
                last_text = last_msg.get("text", "")
                sender_id = last_msg.get("sender_id", "")
                sender_name = self.get_contact_name(sender_id) if sender_id else ""
                summary_prefix = f"{sender_name}: " if sender_name and last_text else ""
                summary = summary_prefix + last_text
                last_time = _format_time(last_msg.get("created_at") or last_modify)

                result.append(ChatSession(
                    username=cid_str,
                    display_name=display_name,
                    session_type=ctype or 0,
                    summary=summary,
                    last_time=last_time,
                    unread=unread or 0,
                    msg_count=msg_counts.get(cid_str, 0),
                ))
        except Exception:
            pass
        return result

    def query_messages(self, session_id: str, start_time: datetime = None,
                       end_time: datetime = None, limit: int = 500) -> List[ChatMessage]:
        conn = self._get_conn()
        if not conn:
            return []
        self._load_contacts()
        self._infer_self_uid()
        result = []
        try:
            for i in range(128):
                table = f"tbmsg_{i:03d}"
                try:
                    rows = conn.execute(
                        f'SELECT * FROM "{table}" WHERE cid = ? ORDER BY createdAt DESC LIMIT ?',
                        (session_id, limit)
                    ).fetchall()
                    cols = [d[0] for d in conn.execute(
                        f'SELECT * FROM "{table}" LIMIT 1'
                    ).description]

                    for row in rows:
                        m = dict(zip(cols, row))
                        raw_content = m.get("content", "")
                        msg_extension = m.get("extension", "")
                        content_text = _extract_text_from_content(raw_content, msg_extension)

                        ts = m.get("createdAt", 0)
                        if ts:
                            dt = datetime.fromtimestamp(ts / 1000)
                        else:
                            dt = None

                        sender_id = str(m.get("senderId", ""))
                        is_self = sender_id and self._self_uid is not None and int(sender_id) == self._self_uid
                        sender_name = "我" if is_self else self.get_contact_name(sender_id)
                        if is_self and not content_text:
                            content_text = "[你发送了一条消息]"

                        msg = ChatMessage(
                            time=dt,
                            time_text=dt.strftime("%H:%M") if dt else "",
                            hour=dt.hour if dt else None,
                            sender=sender_name,
                            sender_id=sender_id,
                            text=content_text,
                            msg_type=m.get("type", 0),
                            chatroom=session_id,
                            raw=m,
                        )
                        result.append(msg)
                except Exception:
                    continue
        except Exception:
            pass
        return result[:limit]

    def get_contacts(self) -> List[Contact]:
        conn = self._get_conn()
        if not conn:
            return []
        self._load_contacts()
        return list(self._contacts_cache.values())

    def get_contact_name(self, user_id: str, session_id: str = None) -> str:
        if not user_id:
            return ""
        c = self._contacts_cache.get(user_id)
        if c:
            return c.remark or c.nickname or user_id
        conn = self._get_conn()
        if conn:
            try:
                row = conn.execute(
                    "SELECT nick, alias FROM tbuser_profile_v2 WHERE uid = ?",
                    (int(user_id) if user_id.isdigit() else user_id,)
                ).fetchone()
                if row:
                    name = row[1] or row[0] or user_id
                    self._contacts_cache[user_id] = Contact(
                        user_id=user_id, nickname=str(row[0] or ""), remark=str(row[1] or "")
                    )
                    return name
            except Exception:
                pass
        return user_id

    def close(self):
        if self._conn:
            self._conn.close()

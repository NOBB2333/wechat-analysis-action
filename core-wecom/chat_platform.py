"""WeCom (Enterprise WeChat) platform implementation."""
import os
import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from collections import defaultdict

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.platform_base import BasePlatform, ChatMessage, ChatSession, Contact


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECRYPTED_DIR = os.path.join(_PROJECT_ROOT, "export", "wxwork_decrypted")


def _looks_like_encrypted_dir(data_dir: str) -> bool:
    """Check whether the WeCom data directory still contains encrypted databases."""
    if not data_dir or not os.path.isdir(data_dir):
        return False
    for name in ("message.db", "session.db", "user.db"):
        path = os.path.join(data_dir, name)
        if os.path.exists(path):
            with open(path, "rb") as f:
                header = f.read(16)
            if header == b"SQLite format 3\x00":
                return False
            return True
    return False


class WeComPlatform(BasePlatform):
    name = "wecom"
    display_name = "企业微信"

    def __init__(self, data_dir: str = None, **kwargs):
        super().__init__(data_dir=data_dir, **kwargs)
        self._decrypted_dir = DECRYPTED_DIR
        self._conn = {}
        self._contacts_cache = {}
        self._user_map = {}
        if self.data_dir is None:
            self.data_dir = self.detect_data_dir()

    def detect_data_dir(self) -> Optional[str]:
        """Auto-detect WeCom data directory.

        Prefer already-decrypted directory; fall back to the original encrypted
        directory so the UI can show that data was detected but not yet decrypted.
        """
        if os.path.isdir(self._decrypted_dir):
            # If decrypted DBs exist and are plaintext, use them.
            msg_db = os.path.join(self._decrypted_dir, "message.db")
            if os.path.exists(msg_db):
                with open(msg_db, "rb") as f:
                    if f.read(16) == b"SQLite format 3\x00":
                        return self._decrypted_dir

        # Fallback: original encrypted directory
        user_profile = os.environ.get("USERPROFILE", "")
        documents = os.path.join(user_profile, "Documents", "WXWork")
        if not os.path.isdir(documents):
            return None

        candidates = []
        for uid_dir in os.listdir(documents):
            uid_path = os.path.join(documents, uid_dir)
            if not os.path.isdir(uid_path):
                continue
            data_dir = os.path.join(uid_path, "Data")
            if os.path.isdir(data_dir) and os.path.exists(os.path.join(data_dir, "message.db")):
                candidates.append(data_dir)
            for version_dir in os.listdir(uid_path):
                vpath = os.path.join(uid_path, version_dir)
                if os.path.isdir(vpath):
                    data_dir = os.path.join(vpath, "Data")
                    if os.path.isdir(data_dir) and os.path.exists(os.path.join(data_dir, "message.db")):
                        candidates.append(data_dir)

        if candidates:
            candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return candidates[0]
        return None

    def _open_db(self, name: str):
        if name in self._conn:
            return self._conn[name]
        db_path = os.path.join(self._decrypted_dir, name)
        if not os.path.exists(db_path):
            return None
        self._conn[name] = sqlite3.connect(db_path)
        return self._conn[name]

    def _table_exists(self, conn, table: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return row is not None

    def _load_user_map(self):
        if self._user_map:
            return
        conn = self._open_db("user.db")
        if not conn:
            return
        try:
            if self._table_exists(conn, "user_table"):
                for row in conn.execute(
                    "SELECT id, name, real_name, account FROM user_table"
                ).fetchall():
                    uid, name, real_name, account = row
                    display = real_name or name or account or ""
                    if display:
                        self._user_map[int(uid)] = display
            if self._table_exists(conn, "external_user_relation_v3"):
                for row in conn.execute(
                    "SELECT user_id, remarks, real_remarks, corp_remark FROM external_user_relation_v3"
                ).fetchall():
                    uid, remarks, real_remarks, corp_remark = row
                    display = real_remarks or remarks or corp_remark or ""
                    if display:
                        self._user_map[int(uid)] = display
        except Exception:
            pass

    def _name_from_conversation_id(self, conversation_id: str) -> str:
        if not conversation_id:
            return ""
        if conversation_id.startswith("S:"):
            ids = []
            for value in conversation_id[2:].split("_"):
                if value.isdigit():
                    ids.append(int(value))
            other_ids = [uid for uid in ids if uid != self._self_id]
            for uid in other_ids or ids:
                if uid in self._user_map:
                    return self._user_map[uid]
        if ":" in conversation_id:
            tail = conversation_id.split(":", 1)[1]
            if tail.isdigit() and int(tail) in self._user_map:
                return self._user_map[int(tail)]
        return conversation_id

    def _message_counts_and_last_times(self):
        counts = defaultdict(int)
        last_times = defaultdict(int)
        conn = self._open_db("message.db")
        if not conn:
            return counts, last_times
        try:
            for table in ("message_table", "message_small_table", "kf_message_tableV1"):
                if not self._table_exists(conn, table):
                    continue
                rows = conn.execute(
                    f'SELECT conversation_id, COUNT(*) AS c, MAX(send_time) AS t FROM "{table}" GROUP BY conversation_id'
                ).fetchall()
                for cid, c, t in rows:
                    if not cid:
                        continue
                    counts[cid] += int(c or 0)
                    last_times[cid] = max(last_times[cid], int(t or 0))
        except Exception:
            pass
        return counts, last_times

    @property
    def _self_id(self) -> Optional[int]:
        if not self.data_dir:
            return None
        parts = os.path.normpath(self.data_dir).split(os.sep)
        for part in reversed(parts):
            if part.isdigit() and len(part) >= 10:
                return int(part)
        return None

    def list_sessions(self, limit: int = 100) -> List[ChatSession]:
        """List WeCom chat sessions from decrypted databases."""
        result = []

        # If the detected directory is still encrypted, show a helpful placeholder.
        if _looks_like_encrypted_dir(self.data_dir):
            result.append(ChatSession(
                username="__need_decrypt__",
                display_name="企业微信数据尚未解密",
                summary="请先运行解密工具：python tools/wechat-decrypt/decrypt_wxwork_db.py --key <key>",
                last_time="",
                session_type=0,
            ))
            return result

        self._load_user_map()
        counts, message_last_times = self._message_counts_and_last_times()

        conversations = {}
        session_db = self._open_db("session.db")
        if session_db:
            try:
                if self._table_exists(session_db, "conversation_table"):
                    rows = session_db.execute(
                        "SELECT id, name, roomname_remark, last_message_time, last_message_id FROM conversation_table"
                    ).fetchall()
                    for cid, name, roomname_remark, last_msg_time, last_msg_id in rows:
                        if not cid:
                            continue
                        display = roomname_remark or name or self._name_from_conversation_id(cid)
                        last_time = max(int(last_msg_time or 0), message_last_times.get(cid, 0))
                        conversations[cid] = ChatSession(
                            username=cid,
                            display_name=display,
                            session_type=2 if cid.startswith("R:") else 1,
                            msg_count=counts.get(cid, 0),
                            last_time=datetime.fromtimestamp(last_time).strftime("%Y-%m-%d %H:%M") if last_time else "",
                            summary="",
                        )
            except Exception:
                pass

        # Merge any conversations that only appear in message counts.
        for cid, count in counts.items():
            if cid in conversations:
                sessions = conversations[cid]
                sessions.msg_count = count
                t = message_last_times.get(cid, 0)
                if t and not sessions.last_time:
                    sessions.last_time = datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")
                continue
            display = self._name_from_conversation_id(cid)
            last_time = message_last_times.get(cid, 0)
            conversations[cid] = ChatSession(
                username=cid,
                display_name=display,
                session_type=2 if cid.startswith("R:") else 1,
                msg_count=count,
                last_time=datetime.fromtimestamp(last_time).strftime("%Y-%m-%d %H:%M") if last_time else "",
                summary="",
            )

        result = [c for c in conversations.values() if c.msg_count > 0]
        result.sort(key=lambda c: c.last_time, reverse=True)
        return result[:limit]

    def query_messages(self, session_id: str, start_time: datetime = None,
                       end_time: datetime = None, limit: int = 500) -> List[ChatMessage]:
        """Query WeCom messages for a conversation."""
        result = []
        conn = self._open_db("message.db")
        if not conn:
            return result

        self._load_user_map()
        try:
            for table in ("message_table", "message_small_table", "kf_message_tableV1"):
                if not self._table_exists(conn, table):
                    continue
                cols = [d[0] for d in conn.execute(f'SELECT * FROM "{table}" LIMIT 1').description]
                query = f'SELECT * FROM "{table}" WHERE conversation_id = ?'
                params = [session_id]
                if start_time:
                    query += " AND send_time >= ?"
                    params.append(int(start_time.timestamp()))
                if end_time:
                    query += " AND send_time <= ?"
                    params.append(int(end_time.timestamp()))
                query += " ORDER BY send_time DESC LIMIT ?"
                params.append(limit)

                rows = conn.execute(query, tuple(params)).fetchall()
                for row in rows:
                    m = dict(zip(cols, row))
                    ts = m.get("send_time")
                    dt = datetime.fromtimestamp(ts) if ts else None
                    sender_id = m.get("sender", "")
                    sender = self._user_map.get(int(sender_id), str(sender_id)) if isinstance(sender_id, int) or (isinstance(sender_id, str) and sender_id.isdigit()) else str(sender_id)
                    result.append(ChatMessage(
                        time=dt,
                        time_text=dt.strftime("%H:%M") if dt else "",
                        hour=dt.hour if dt else None,
                        sender=sender,
                        sender_id=str(sender_id),
                        text=str(m.get("content", "")),
                        msg_type=m.get("msg_type", 0),
                        chatroom=session_id,
                        raw=m,
                    ))
        except Exception:
            pass

        result.sort(key=lambda m: m.time or datetime.min, reverse=True)
        return result[:limit]

    def get_contacts(self) -> List[Contact]:
        """Get WeCom contacts."""
        result = []
        self._load_user_map()
        for uid, name in self._user_map.items():
            result.append(Contact(user_id=str(uid), nickname=name, remark=""))
        return result

    def get_contact_name(self, user_id: str, session_id: str = None) -> str:
        if not user_id:
            return ""
        self._load_user_map()
        if user_id.isdigit() and int(user_id) in self._user_map:
            return self._user_map[int(user_id)]
        return user_id

    def close(self):
        for conn in self._conn.values():
            conn.close()
        self._conn.clear()

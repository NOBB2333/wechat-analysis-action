"""WeChat platform implementation - wraps existing WeChatDB."""
import os
from datetime import datetime
from typing import List, Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.platform_base import BasePlatform, ChatMessage, ChatSession, Contact

# Import paths from this same directory (core-wechat/)
_this_dir = os.path.dirname(os.path.abspath(__file__))
from importlib.util import spec_from_file_location, module_from_spec
_spec = spec_from_file_location("wechat_paths", os.path.join(_this_dir, "paths.py"))
_mod = module_from_spec(_spec)
_spec.loader.exec_module(_mod)
DECRYPTED_DIR = _mod.DECRYPTED_DIR


class WeChatPlatform(BasePlatform):
    name = "wechat"
    display_name = "微信"

    def __init__(self, data_dir: str = None, self_wxid: str = None,
                 self_name: str = "我", display_name_priority: list = None, **kwargs):
        super().__init__(data_dir=data_dir or DECRYPTED_DIR, **kwargs)
        self._self_wxid = self_wxid
        self._self_name = self_name
        self._name_priority = display_name_priority or ["group_nickname", "nickname", "remark"]
        self._db = None

    def _get_db(self):
        if self._db is None:
            # Ensure core-wechat is on sys.path for query.py's import
            if _this_dir not in sys.path:
                sys.path.insert(0, _this_dir)
            from query import WeChatDB
            self._db = WeChatDB(
                decrypted_dir=self.data_dir,
                self_wxid=self._self_wxid,
                self_name=self._self_name,
                display_name_priority=self._name_priority,
            )
        return self._db

    def detect_data_dir(self) -> Optional[str]:
        if os.path.exists(self.data_dir):
            return self.data_dir
        return None

    def list_sessions(self, limit: int = 100) -> List[ChatSession]:
        db = self._get_db()
        sessions = db.list_sessions()
        result = []
        for s in sessions[:limit]:
            result.append(ChatSession(
                username=s["username"],
                display_name=s["display_name"],
                session_type=s["type"],
                summary=s["summary"],
                last_time=s["last_time"],
                unread=s["unread"],
            ))
        return result

    def query_messages(self, session_id: str, start_time: datetime = None,
                       end_time: datetime = None, limit: int = 500) -> List[ChatMessage]:
        db = self._get_db()
        messages = db.query_messages(session_id, start_time=start_time,
                                     end_time=end_time, limit=limit)
        normalized = db.normalize_messages(messages, chatroom=session_id)
        result = []
        for m in normalized:
            result.append(ChatMessage(
                time=m.get("time"),
                time_text=m.get("time_text", ""),
                hour=m.get("hour"),
                sender=m.get("sender", ""),
                sender_id=m.get("sender_id", ""),
                text=m.get("text", ""),
                msg_type=m.get("local_type", 0),
                chatroom=session_id,
            ))
        return result

    def get_contacts(self) -> List[Contact]:
        db = self._get_db()
        if not db.contact:
            return []
        rows = db.contact.execute(
            "SELECT username, nick_name, remark FROM contact"
        ).fetchall()
        result = []
        for uid, nick, remark in rows:
            c = Contact(user_id=uid, nickname=nick or "", remark=remark or "")
            self._contacts_cache[uid] = c
            result.append(c)
        return result

    def get_chatroom_name(self, username: str) -> str:
        db = self._get_db()
        return db.get_chatroom_name(username)

    def find_group(self, name: str) -> Optional[str]:
        db = self._get_db()
        return db.find_msg_table(name)

    def close(self):
        if self._db:
            self._db.close()

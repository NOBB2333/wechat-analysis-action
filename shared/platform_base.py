"""Base platform abstraction for IM chat record analysis."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class ChatMessage:
    time: Optional[datetime] = None
    time_text: str = ""
    hour: Optional[int] = None
    sender: str = ""
    sender_id: str = ""
    text: str = ""
    msg_type: int = 0
    msg_type_label: str = ""
    chatroom: str = ""
    raw: Any = None


@dataclass
class ChatSession:
    username: str = ""
    display_name: str = ""
    session_type: int = 0
    summary: str = ""
    last_time: str = ""
    unread: int = 0
    msg_count: int = 0


@dataclass
class Contact:
    user_id: str = ""
    nickname: str = ""
    remark: str = ""
    avatar: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


class BasePlatform(ABC):
    """Abstract base class for all IM platforms."""

    name: str = "base"
    display_name: str = "Base Platform"

    def __init__(self, data_dir: str = None, **kwargs):
        self.data_dir = data_dir
        self._contacts_cache: Dict[str, Contact] = {}

    @abstractmethod
    def detect_data_dir(self) -> Optional[str]:
        """Auto-detect the data directory for this platform."""
        ...

    @abstractmethod
    def list_sessions(self, limit: int = 100) -> List[ChatSession]:
        """List all chat sessions."""
        ...

    @abstractmethod
    def query_messages(self, session_id: str, start_time: datetime = None,
                       end_time: datetime = None, limit: int = 500) -> List[ChatMessage]:
        """Query messages for a specific session."""
        ...

    @abstractmethod
    def get_contacts(self) -> List[Contact]:
        """Get all contacts."""
        ...

    def get_contact_name(self, user_id: str, session_id: str = None) -> str:
        """Get display name for a user."""
        c = self._contacts_cache.get(user_id)
        if c:
            return c.remark or c.nickname or user_id
        return user_id

    def normalize_messages(self, messages: List[ChatMessage]) -> List[Dict]:
        """Normalize messages to standard dict format."""
        return [
            {
                "time": m.time,
                "time_text": m.time_text,
                "hour": m.hour,
                "sender": m.sender,
                "sender_id": m.sender_id,
                "text": m.text,
                "msg_type": m.msg_type,
                "msg_type_label": m.msg_type_label,
            }
            for m in messages
        ]

    def close(self):
        """Close all database connections."""
        pass

"""FastAPI server for chat analysis."""
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, List
from collections import Counter

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add project root to path
_api_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(_api_dir)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Import platform implementations (hyphenated names need importlib)
import importlib
_wechat_mod = importlib.import_module('core-wechat.chat_platform')
_wecom_mod = importlib.import_module('core-wecom.chat_platform')
_dingtalk_mod = importlib.import_module('core-dingtalk.chat_platform')
_shared_mod = importlib.import_module('shared.platform_base')

WeChatPlatform = _wechat_mod.WeChatPlatform
WeComPlatform = _wecom_mod.WeComPlatform
DingTalkPlatform = _dingtalk_mod.DingTalkPlatform
BasePlatform = _shared_mod.BasePlatform

PLATFORMS = {
    "wechat": WeChatPlatform,
    "wecom": WeComPlatform,
    "dingtalk": DingTalkPlatform,
}

def get_platform(name, **kwargs):
    cls = PLATFORMS.get(name)
    if not cls:
        raise ValueError(f"Unknown platform: {name}")
    return cls(**kwargs)

app = FastAPI(title="Chat Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SessionResponse(BaseModel):
    username: str
    display_name: str
    session_type: int = 0
    summary: str = ""
    last_time: str = ""
    unread: int = 0
    msg_count: int = 0


class MessageResponse(BaseModel):
    time_text: str = ""
    sender: str = ""
    sender_id: str = ""
    text: str = ""
    msg_type: int = 0
    msg_type_label: str = ""
    hour: Optional[int] = None


class ContactResponse(BaseModel):
    user_id: str
    nickname: str
    remark: str


class StatsResponse(BaseModel):
    total_messages: int = 0
    unique_senders: int = 0
    sender_stats: dict = {}
    hourly_distribution: dict = {}
    msg_type_distribution: dict = {}
    time_range: dict = {}
    top_senders: list = []
    activity_timeline: list = []


class PlatformInfo(BaseModel):
    name: str
    display_name: str
    detected: bool = False
    data_dir: str = ""


_platforms_cache = {}


def _get_platform(name: str):
    if name not in _platforms_cache:
        try:
            plat = get_platform(name)
            data_dir = plat.detect_data_dir()
            if data_dir:
                plat.data_dir = data_dir
            _platforms_cache[name] = plat
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    return _platforms_cache[name]


@app.get("/api/platforms")
async def list_platforms():
    result = []
    for name, cls in PLATFORMS.items():
        try:
            plat = get_platform(name)
            data_dir = plat.detect_data_dir()
            result.append(PlatformInfo(
                name=name,
                display_name=cls.display_name,
                detected=data_dir is not None,
                data_dir=data_dir or "",
            ))
        except Exception:
            result.append(PlatformInfo(name=name, display_name=cls.display_name))
    return result


@app.get("/api/{platform}/sessions")
async def list_sessions(platform: str, limit: int = Query(100, ge=1, le=1000)):
    plat = _get_platform(platform)
    sessions = plat.list_sessions(limit=limit)
    return [SessionResponse(
        username=s.username,
        display_name=s.display_name,
        session_type=s.session_type,
        summary=s.summary,
        last_time=s.last_time,
        unread=s.unread,
        msg_count=s.msg_count,
    ) for s in sessions]


@app.get("/api/{platform}/messages/{session_id}")
async def get_messages(
    platform: str,
    session_id: str,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(500, ge=1, le=5000),
):
    plat = _get_platform(platform)
    start_time = None
    end_time = None
    if start_date:
        start_time = datetime.strptime(start_date, "%Y-%m-%d")
    if end_date:
        end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

    messages = plat.query_messages(session_id, start_time=start_time,
                                   end_time=end_time, limit=limit)
    return [MessageResponse(
        time_text=m.time_text,
        sender=m.sender,
        sender_id=m.sender_id,
        text=m.text,
        msg_type=m.msg_type,
        msg_type_label=m.msg_type_label,
        hour=m.hour,
    ) for m in messages]


@app.get("/api/{platform}/contacts")
async def get_contacts(platform: str):
    plat = _get_platform(platform)
    contacts = plat.get_contacts()
    return [ContactResponse(
        user_id=c.user_id,
        nickname=c.nickname,
        remark=c.remark,
    ) for c in contacts]


@app.get("/api/{platform}/stats/{session_id}")
async def get_stats(
    platform: str,
    session_id: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    plat = _get_platform(platform)
    start_time = None
    end_time = None
    if start_date:
        start_time = datetime.strptime(start_date, "%Y-%m-%d")
    if end_date:
        end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

    messages = plat.query_messages(session_id, start_time=start_time,
                                   end_time=end_time, limit=5000)

    if not messages:
        return StatsResponse()

    sender_counter = Counter(m.sender for m in messages if m.sender)
    hour_counter = Counter(m.hour for m in messages if m.hour is not None)
    type_counter = Counter(m.msg_type for m in messages)

    top_senders = sender_counter.most_common(20)

    time_range = {}
    if messages:
        times = [m.time for m in messages if m.time]
        if times:
            time_range = {
                "start": min(times).isoformat(),
                "end": max(times).isoformat(),
            }

    activity_timeline = []
    date_counter = Counter()
    for m in messages:
        if m.time:
            date_key = m.time.strftime("%Y-%m-%d")
            date_counter[date_key] += 1
    for date_key in sorted(date_counter.keys()):
        activity_timeline.append({"date": date_key, "count": date_counter[date_key]})

    return StatsResponse(
        total_messages=len(messages),
        unique_senders=len(sender_counter),
        sender_stats=dict(sender_counter),
        hourly_distribution={str(h): c for h, c in sorted(hour_counter.items())},
        msg_type_distribution={str(t): c for t, c in type_counter.items()},
        time_range=time_range,
        top_senders=[{"name": name, "count": count} for name, count in top_senders],
        activity_timeline=activity_timeline,
    )


@app.get("/api/{platform}/groups")
async def list_groups(platform: str):
    plat = _get_platform(platform)
    sessions = plat.list_sessions(limit=500)
    groups = [s for s in sessions if "@chatroom" in s.username or s.session_type == 2]
    return [SessionResponse(
        username=s.username,
        display_name=s.display_name,
        session_type=s.session_type,
        msg_count=s.msg_count,
    ) for s in groups]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)

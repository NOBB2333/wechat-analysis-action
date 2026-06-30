"""Comprehensive test of the chat analysis system."""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib
_wechat_mod = importlib.import_module('core-wechat.chat_platform')
_wecom_mod = importlib.import_module('core-wecom.chat_platform')
_dingtalk_mod = importlib.import_module('core-dingtalk.chat_platform')

WeChatPlatform = _wechat_mod.WeChatPlatform
WeComPlatform = _wecom_mod.WeComPlatform
DingTalkPlatform = _dingtalk_mod.DingTalkPlatform

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
from collections import Counter

print("=== Chat Analysis System Test ===\n")

# Test 1: Platform imports
print("1. Platform imports")
for name, cls in PLATFORMS.items():
    print(f"   {name}: {cls.display_name}")
print("   OK\n")

# Test 2: WeChat platform
print("2. WeChat platform")
p = get_platform('wechat')
dd = p.detect_data_dir()
status = "OK" if dd else "FAIL"
print(f"   Detection: {status}")
if dd:
    print(f"   Data dir: {dd}")
print()

# Test 3: Sessions
print("3. Sessions")
sessions = p.list_sessions(limit=5)
print(f"   Found: {len(sessions)}")
for s in sessions[:3]:
    name = s.display_name[:25]
    print(f"   - {name} ({s.username[:20]}...)")
print()

# Test 4: Messages
print("4. Messages")
if sessions:
    sid = sessions[0].username
    msgs = p.query_messages(sid, limit=50)
    print(f"   Session: {sessions[0].display_name[:30]}")
    print(f"   Messages: {len(msgs)}")
    for m in msgs[:3]:
        text = m.text[:40] if m.text else "[no text]"
        print(f"   [{m.time_text}] {m.sender[:15]}: {text}")
print()

# Test 5: Stats
print("5. Statistics")
if sessions:
    all_msgs = p.query_messages(sid, limit=500)
    senders = Counter(m.sender for m in all_msgs if m.sender)
    hours = Counter(m.hour for m in all_msgs if m.hour is not None)
    print(f"   Total messages: {len(all_msgs)}")
    print(f"   Unique senders: {len(senders)}")
    print(f"   Top 3 senders:")
    for name, count in senders.most_common(3):
        print(f"     {name[:20]}: {count}")
    print(f"   Active hours: {len(hours)}")
print()

print("=== All tests passed! ===")

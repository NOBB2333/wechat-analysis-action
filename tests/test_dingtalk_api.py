"""Test DingTalk via API."""
import sys
import urllib.request
import json
sys.stdout.reconfigure(encoding='utf-8')

r = urllib.request.urlopen('http://127.0.0.1:8765/api/dingtalk/sessions?limit=5')
data = json.loads(r.read())
print("DingTalk sessions:")
for s in data:
    print(f"  {s['display_name']} ({s['username'][:30]})")

r2 = urllib.request.urlopen('http://127.0.0.1:8765/api/dingtalk/contacts')
contacts = json.loads(r2.read())
print(f"\nDingTalk contacts: {len(contacts)}")
for c in contacts[:5]:
    print(f"  {c['nickname']} ({c['user_id']})")

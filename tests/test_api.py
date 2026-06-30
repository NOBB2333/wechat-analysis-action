"""Test the API server."""
import urllib.request
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    r = urllib.request.urlopen('http://127.0.0.1:8765/api/platforms')
    data = json.loads(r.read())
    print("=== Platforms ===")
    for p in data:
        print(f"  {p['name']}: {p['display_name']} detected={p['detected']}")

    # Test sessions
    r2 = urllib.request.urlopen('http://127.0.0.1:8765/api/wechat/sessions?limit=5')
    sessions = json.loads(r2.read())
    print("\n=== WeChat Sessions (top 5) ===")
    for s in sessions:
        print(f"  {s['display_name']} ({s['username']})")

    # Test stats for first session
    if sessions:
        sid = sessions[0]['username']
        r3 = urllib.request.urlopen(f'http://127.0.0.1:8765/api/wechat/stats/{sid}?start_date=2026-06-01&end_date=2026-06-28')
        stats = json.loads(r3.read())
        print(f"\n=== Stats for {sessions[0]['display_name']} ===")
        print(f"  Total messages: {stats['total_messages']}")
        print(f"  Unique senders: {stats['unique_senders']}")
        print(f"  Top senders: {stats['top_senders'][:3]}")
        print(f"  Hourly distribution: {dict(list(stats['hourly_distribution'].items())[:5])}")

    print("\nAll tests passed!")
except Exception as e:
    print(f"Error: {e}")

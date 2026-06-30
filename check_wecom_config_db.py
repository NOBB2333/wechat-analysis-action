"""Check WeCom config.db for database key"""
import sys
import os
import sqlite3
sys.stdout.reconfigure(encoding='utf-8')

config_db = r'D:\5_Cache\企业微信文件\WXWork\Global\config.db'
if os.path.exists(config_db):
    try:
        conn = sqlite3.connect(config_db)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"config.db tables: {[t[0] for t in tables]}")
        for t in tables[:10]:
            name = t[0]
            try:
                rows = conn.execute(f'SELECT * FROM "{name}" LIMIT 5').fetchall()
                cols = [d[0] for d in conn.execute(f'SELECT * FROM "{name}" LIMIT 1').description]
                print(f"  {name}: {cols}")
                for row in rows:
                    print(f"    {row}")
            except Exception as e:
                print(f"  {name}: {e}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"File not found: {config_db}")

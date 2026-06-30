"""Test WeCom data reading."""
import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

db_path = r'C:\Users\hl\Documents\WXWork\1688855268826405\Data\message.db'
conn = sqlite3.connect(db_path)
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"Tables: {len(tables)}")
for t in tables[:15]:
    name = t[0]
    count = conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
    print(f"  {name}: {count} rows")
conn.close()

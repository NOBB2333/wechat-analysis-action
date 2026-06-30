"""Check updated storage.db"""
import sys
import os
import sqlite3
sys.stdout.reconfigure(encoding='utf-8')

db = r'C:\Users\hl\AppData\Roaming\DingTalk\globalStorage\storage.db'
with open(db, 'rb') as f:
    h = f.read(16)
print(f'Header: {h.hex()}')
print(f'Is SQLite: {h == b"SQLite format 3\x00"}')

if h == b'SQLite format 3\x00':
    conn = sqlite3.connect(db)
    tables = conn.execute("SELECT name FROM sqlite_master").fetchall()
    print(f'Tables: {[t[0] for t in tables]}')
    for t in tables[:5]:
        name = t[0]
        rows = conn.execute(f'SELECT * FROM "{name}" LIMIT 5').fetchall()
        cols = [d[0] for d in conn.execute(f'SELECT * FROM "{name}" LIMIT 1').description]
        print(f'  {name}: {cols}')
        for row in rows:
            print(f'    {row}')
    conn.close()
else:
    print('Not SQLite - still encrypted')

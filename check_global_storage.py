"""Check DingTalk globalStorage for key info"""
import sys
import os
import sqlite3
sys.stdout.reconfigure(encoding='utf-8')

gs_dir = r'C:\Users\hl\AppData\Roaming\DingTalk\globalStorage'
print(f'Directory: {gs_dir}')

for f in os.listdir(gs_dir):
    fp = os.path.join(gs_dir, f)
    if os.path.isfile(fp):
        sz = os.path.getsize(fp)
        print(f'  {f}: {sz} bytes')

# Try to read storage.db
db_path = os.path.join(gs_dir, 'storage.db')
try:
    conn = sqlite3.connect(db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f'\nstorage.db tables: {[t[0] for t in tables]}')
    for t in tables[:5]:
        name = t[0]
        try:
            rows = conn.execute(f'SELECT * FROM "{name}" LIMIT 5').fetchall()
            cols = [d[0] for d in conn.execute(f'SELECT * FROM "{name}" LIMIT 1').description]
            print(f'  {name}: {cols}')
            for row in rows:
                print(f'    {row}')
        except Exception as e:
            print(f'  {name}: {e}')
    conn.close()
except Exception as e:
    print(f'Error reading storage.db: {e}')

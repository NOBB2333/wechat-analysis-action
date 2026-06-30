"""Check QQ database format"""
import sys
import os
import sqlite3
sys.stdout.reconfigure(encoding='utf-8')

dbs = [
    r'C:\Users\hl\Documents\Tencent Files\2855813844\Msg3.0.db',
    r'C:\Users\hl\Documents\Tencent Files\572766574\Msg3.0.db',
]

for db in dbs:
    print(f'\n{os.path.basename(db)}:')
    with open(db, 'rb') as f:
        h = f.read(16)
    print(f'  Header: {h.hex()}')
    print(f'  Is SQLite: {h == b"SQLite format 3\x00"}')
    
    if h == b'SQLite format 3\x00':
        try:
            conn = sqlite3.connect(db)
            tables = conn.execute("SELECT name FROM sqlite_master").fetchall()
            print(f'  Tables: {[t[0] for t in tables]}')
            for t in tables[:5]:
                name = t[0]
                count = conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
                print(f'    {name}: {count} rows')
            conn.close()
        except Exception as e:
            print(f'  Error: {e}')

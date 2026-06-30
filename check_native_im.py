"""Check NativeIM directory"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

nim_dir = r'C:\Users\hl\AppData\Roaming\DingTalk\edb0646a4ee08ab16913_v3\NativeIM'
if os.path.isdir(nim_dir):
    print('NativeIM directory:')
    for f in os.listdir(nim_dir):
        fp = os.path.join(nim_dir, f)
        if os.path.isfile(fp):
            sz = os.path.getsize(fp)
            with open(fp, 'rb') as fh:
                h = fh.read(16)
            is_sqlite = h == b'SQLite format 3\x00'
            print(f'  {f}: {sz} bytes, SQLite={is_sqlite}')

"""Decrypt DingTalk with phone number as UID."""
import sys, hashlib, os, json, base64, sqlite3
from Crypto.Cipher import AES
sys.stdout.reconfigure(encoding='utf-8')

db_path = r'C:\Users\hl\AppData\Roaming\DingTalk\edb0646a4ee08ab16913_v3\DBFiles\dingtalk.db'
with open(db_path, 'rb') as f:
    data = f.read()

with open(r'C:\Users\hl\AppData\Roaming\DingTalk\edb0646a4ee08ab16913_v3\user_config', 'rb') as f:
    salt = json.loads(base64.b64decode(f.read()))['salt']

out_dir = r'D:\4_Code\0_Github_Project\wechat-analysis\export\dingtalk_decrypted'
os.makedirs(out_dir, exist_ok=True)

for uid in ['17629033158', '18821775905']:
    dk = hashlib.pbkdf2_hmac('sha1', (uid + salt).encode(), b'666DingT', 1000, dklen=32)
    key = hashlib.md5(dk).hexdigest()[:16].encode()
    c = AES.new(key, AES.MODE_ECB)
    out = bytearray()
    for off in range(0, len(data), 4096):
        page = data[off:off + 4096]
        if len(page) == 4096:
            for i in range(0, 4096, 16):
                out.extend(c.decrypt(page[i:i + 16]))
        else:
            out.extend(page)

    if bytes(out)[:16] == b'SQLite format 3\x00':
        print(f'SUCCESS! UID = {uid}')
        out_path = os.path.join(out_dir, 'dingtalk.db')
        with open(out_path, 'wb') as f:
            f.write(bytes(out))
        conn = sqlite3.connect(out_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f'Tables: {len(tables)}')
        for t in tables[:15]:
            name = t[0]
            count = conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            print(f'  {name}: {count} rows')
        conn.close()
        break
    else:
        h = bytes(out)[:8].hex()
        print(f'UID {uid}: failed ({h})')

print('Done')

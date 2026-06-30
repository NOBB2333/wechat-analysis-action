"""Decrypt DingTalk with discovered UID, including WAL merge."""
import sys, hashlib, os, json, base64, sqlite3
from Crypto.Cipher import AES

sys.stdout.reconfigure(encoding='utf-8')

UID = '691398452'
_db_path = r'C:\Users\hl\AppData\Roaming\DingTalk\edb0646a4ee08ab16913_v3\DBFiles\dingtalk.db'
_config_path = r'C:\Users\hl\AppData\Roaming\DingTalk\edb0646a4ee08ab16913_v3\user_config'

# If the hard-coded path does not exist, try to auto-detect the DingTalk data directory.
if not os.path.exists(_db_path):
    appdata = os.environ.get('APPDATA', '')
    dt_dir = os.path.join(appdata, 'DingTalk')
    if os.path.isdir(dt_dir):
        for entry in sorted(os.listdir(dt_dir), key=lambda x: os.path.getmtime(os.path.join(dt_dir, x)), reverse=True):
            entry_path = os.path.join(dt_dir, entry)
            if os.path.isdir(entry_path):
                candidate_db = os.path.join(entry_path, 'DBFiles', 'dingtalk.db')
                candidate_cfg = os.path.join(entry_path, 'user_config')
                if os.path.exists(candidate_db) and os.path.exists(candidate_cfg):
                    _db_path = candidate_db
                    _config_path = candidate_cfg
                    break

out_dir = r'D:\4_Code\0_Github_Project\wechat-analysis\export_parse_result\decrypted_dingtalk'
out_path = os.path.join(out_dir, 'dingtalk.db')
# Write to a staging name first so a running server does not lock the final file.
staging_path = out_path + '.staging'

print(f'DingTalk DB: {_db_path}')
print(f'Output: {out_path}')

with open(_config_path, 'rb') as f:
    salt = json.loads(base64.b64decode(f.read()))['salt']

dk = hashlib.pbkdf2_hmac('sha1', (UID + salt).encode(), b'666DingT', 1000, dklen=32)
key = hashlib.md5(dk).hexdigest()[:16].encode()
print(f'UID: {UID}, Key: {key.decode()}')

c = AES.new(key, AES.MODE_ECB)


def _decrypt_page(data: bytes) -> bytes:
    out = bytearray()
    for i in range(0, len(data), 16):
        out.extend(c.decrypt(data[i:i + 16]))
    return bytes(out)


def _wal_checksum(data: bytes, s1: int, s2: int) -> tuple:
    """SQLite native (little-endian) WAL checksum."""
    s1 &= 0xffffffff
    s2 &= 0xffffffff
    assert len(data) % 8 == 0
    for i in range(0, len(data), 8):
        w1 = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16) | (data[i + 3] << 24)
        w2 = data[i + 4] | (data[i + 5] << 8) | (data[i + 6] << 16) | (data[i + 7] << 24)
        s1 = (s1 + w1 + s2) & 0xffffffff
        s2 = (s2 + w2 + s1) & 0xffffffff
    return s1, s2


# Decrypt main database page by page.
with open(_db_path, 'rb') as f:
    db_data = f.read()

out = bytearray()
for off in range(0, len(db_data), 4096):
    page = db_data[off:off + 4096]
    if len(page) == 4096:
        out.extend(_decrypt_page(page))
    else:
        out.extend(page)

if bytes(out)[:16] != b'SQLite format 3\x00':
    h = bytes(out)[:16].hex()
    print(f'FAILED: decrypted DB header is {h}')
    sys.exit(1)

os.makedirs(out_dir, exist_ok=True)
with open(staging_path, 'wb') as f:
    f.write(bytes(out))

# Decrypt WAL if present and merge it into the main database.
wal_path = _db_path + '-wal'
out_wal = staging_path + '-wal'

if os.path.exists(wal_path) and os.path.getsize(wal_path) > 32:
    print('Decrypting WAL...')
    with open(wal_path, 'rb') as f:
        wal_data = f.read()

    # WAL header (32 bytes) is not encrypted.
    wal_out = bytearray(wal_data[:32])
    hdr_ck1 = int.from_bytes(wal_data[24:28], 'big')
    hdr_ck2 = int.from_bytes(wal_data[28:32], 'big')

    idx = 32
    frame_count = 0
    aCksum = [hdr_ck1, hdr_ck2]
    while idx + 24 + 4096 <= len(wal_data):
        hdr = wal_data[idx:idx + 24]
        page_enc = wal_data[idx + 24:idx + 24 + 4096]
        page = _decrypt_page(page_enc)

        aCksum[0], aCksum[1] = _wal_checksum(hdr[:8], aCksum[0], aCksum[1])
        aCksum[0], aCksum[1] = _wal_checksum(page, aCksum[0], aCksum[1])

        new_hdr = bytearray(hdr)
        new_hdr[16:20] = aCksum[0].to_bytes(4, 'big')
        new_hdr[20:24] = aCksum[1].to_bytes(4, 'big')
        wal_out.extend(new_hdr)
        wal_out.extend(page)

        idx += 24 + 4096
        frame_count += 1

    with open(out_wal, 'wb') as f:
        f.write(bytes(wal_out))
    print(f'WAL decrypted ({frame_count} frames), checksums fixed.')

    # Merge WAL into the main DB so the output is a single self-contained file.
    conn = sqlite3.connect(staging_path)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA wal_checkpoint(RESTART)')
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.close()
    for extra in (out_wal, staging_path + '-shm'):
        if os.path.exists(extra):
            os.remove(extra)
    print('WAL merged into main DB.')
else:
    print('No WAL found; using decrypted main DB only.')

# Atomically replace the old output file with the newly decrypted/merged DB.
if os.path.exists(out_path):
    os.remove(out_path)
os.replace(staging_path, out_path)

# Print summary.
conn = sqlite3.connect(out_path)
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f'Tables: {len(tables)}')
for t in tables[:20]:
    name = t[0]
    count = conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
    print(f'  {name}: {count} rows')

msg_total = 0
for i in range(128):
    try:
        msg_total += conn.execute(f'SELECT count(*) FROM tbmsg_{i:03d}').fetchone()[0]
    except Exception:
        pass
print(f'Total messages across tbmsg_*: {msg_total}')
print(f'\nSaved to: {out_path}')
conn.close()

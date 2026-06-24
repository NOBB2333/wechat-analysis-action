"""聊天图片提取 — 从解密后的消息数据库定位并解密 .dat 图片文件。

V2 文件需要 AES key: 运行 tools/wechat-decrypt/find_image_key.py 提取后自动保存到
tools/wechat-decrypt/config.json，本模块自动读取。

用法:
    from image_extract import extract_chat_images
    extract_chat_images(chatroom, date_str, output_dir)
"""

import os, sys, sqlite3, hashlib, glob, json, subprocess
from datetime import datetime, timedelta

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(PROJECT_DIR, "tools", "wechat-decrypt")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from paths import DECRYPTED_DIR
from decode_image import decrypt_dat_file, extract_md5_from_packed_info


def _load_decode_config():
    """读取 wechat-decrypt 的图片解密配置（AES key / XOR key / base_dir）。"""
    cfg_path = os.path.join(TOOLS_DIR, "config.json")
    if not os.path.exists(cfg_path):
        return None
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


def _hevc_to_png(hevc_path):
    """wxgf/HEVC → PNG。ffprobe 拿不到帧数时直接尝试提取单帧。"""
    base = os.path.splitext(hevc_path)[0]
    png_path = base + ".png"
    try:
        probe = subprocess.run([
            "ffprobe", "-v", "quiet", "-select_streams", "v:0",
            "-show_entries", "stream=nb_frames,duration",
            "-of", "csv=p=0", hevc_path
        ], capture_output=True, text=True, timeout=10)
        # ffprobe 可能返回 N/A，此时也按单帧处理
        nb_frames = 1
        duration = 0.0
        if probe.stdout.strip():
            parts = probe.stdout.strip().split(",")
            try:
                duration = float(parts[0]) if parts[0] and parts[0] != "N/A" else 0.0
            except ValueError:
                duration = 0.0
            try:
                nb_frames = int(parts[1]) if len(parts) > 1 and parts[1] and parts[1] != "N/A" else 1
            except ValueError:
                nb_frames = 1
    except Exception:
        pass

    result = subprocess.run([
        "ffmpeg", "-y", "-i", hevc_path, "-frames:v", "1",
        "-loglevel", "error", png_path
    ], capture_output=True, text=True, timeout=30)
    if result.returncode == 0 and os.path.exists(png_path):
        os.unlink(hevc_path)
        return png_path

    return None


def extract_chat_images(chatroom, date_str, output_dir):
    """提取并解密某个群在某天的所有图片。

    Args:
        chatroom: 群聊 wxid（如 21001820917@chatroom）
        date_str: 日期 YYYY-MM-DD
        output_dir: 图片输出目录（自动创建）

    Returns:
        dict: {ok: int, fail: int, total: int}
    """
    cfg = _load_decode_config()
    if not cfg:
        return {"ok": 0, "fail": 0, "total": 0, "error": "wechat-decrypt config.json 不存在"}

    aes_key = cfg.get("image_aes_key", "")
    xor_key = cfg.get("image_xor_key", 0x88)
    if isinstance(aes_key, str) and aes_key:
        aes_key = aes_key.encode()[:16]
    elif not aes_key:
        aes_key = None
    if isinstance(xor_key, str):
        xor_key = int(xor_key, 0)
    base_dir = os.path.dirname(cfg["db_dir"])

    start = datetime.strptime(date_str, "%Y-%m-%d")
    end = start + timedelta(days=1)

    # 1. 查图片消息
    msg_db = os.path.join(DECRYPTED_DIR, "message", "message_0.db")
    table = f"Msg_{hashlib.md5(chatroom.encode()).hexdigest()}"

    conn = sqlite3.connect(msg_db)
    try:
        rows = conn.execute(
            f"SELECT local_id, create_time FROM {table} "
            "WHERE local_type = 3 AND create_time >= ? AND create_time <= ? "
            "ORDER BY create_time",
            (start.timestamp(), end.timestamp())
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return {"ok": 0, "fail": 0, "total": 0}
    conn.close()

    if not rows:
        return {"ok": 0, "fail": 0, "total": 0}

    # 2. 查 message_resource.db
    res_db = os.path.join(DECRYPTED_DIR, "message", "message_resource.db")
    res_conn = sqlite3.connect(res_db)
    chat_row = res_conn.execute(
        "SELECT rowid FROM ChatName2Id WHERE user_name = ?", (chatroom,)
    ).fetchone()
    chat_id = chat_row[0] if chat_row else None
    chat_hash = hashlib.md5(chatroom.encode()).hexdigest()
    search_base = os.path.join(base_dir, "msg", "attach", chat_hash)
    os.makedirs(output_dir, exist_ok=True)

    ok = 0
    fail = 0

    for local_id, create_time in rows:
        row = res_conn.execute(
            "SELECT packed_info FROM MessageResourceInfo "
            "WHERE chat_id = ? AND message_local_id = ? "
            "AND (message_local_type = 3 OR message_local_type % 4294967296 = 3) "
            "ORDER BY message_create_time DESC LIMIT 1",
            (chat_id, local_id)
        ).fetchone()

        file_md5 = extract_md5_from_packed_info(row[0]) if (row and row[0]) else None
        if not file_md5:
            fail += 1
            continue

        dat_files = sorted(glob.glob(os.path.join(search_base, "*", "Img", f"{file_md5}*.dat")))
        if not dat_files:
            fail += 1
            continue

        # 优先级: _h.dat (高清原图) > .dat (普通) > 其他
        selected = dat_files[0]
        for suffix in (f"{file_md5}_h.dat", f"{file_md5}.dat"):
            for f in dat_files:
                if os.path.basename(f) == suffix:
                    selected = f
                    break
            else:
                continue
            break

        result_path, fmt = decrypt_dat_file(selected, aes_key=aes_key, xor_key=xor_key)
        if not result_path or not fmt:
            fail += 1
            continue

        name_prefix = f"[{datetime.fromtimestamp(create_time):%H%M}]_{file_md5}"
        final = os.path.join(output_dir, f"{name_prefix}.{fmt}")
        if os.path.exists(final):
            os.unlink(final)
        os.rename(result_path, final)

        if fmt == "hevc":
            png_path = _hevc_to_png(final)
            if png_path:
                final = png_path

        ok += 1

    res_conn.close()
    return {"ok": ok, "fail": fail, "total": len(rows)}

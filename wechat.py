"""One-command entry for WeChat chat analysis."""
import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_DIR, "src")
sys.path.insert(0, SRC_DIR)

from decrypt import decrypt_from_keys
from keys import generate_keys
from paths import ALL_KEYS_FILE, DECRYPTED_DIR, EXPORT_DIR, LOGS_DIR, REPORTS_DIR, WECHAT_DECRYPT_CONFIG
from query import WeChatDB
from visual_report import parse_llm_json, render_html_report, render_html_to_png

CONFIG_FILE = os.path.join(PROJECT_DIR, "config.jsonc")
DEFAULT_SETTINGS = {
    "default_groups": ["家"],
    "self_wxid": "",
    "self_name": "我",
    "display_name_mode": "remark",
    "llm": {
        "auth_token": "",
        "base_url": "https://api.deepseek.com/anthropic",
        "model": "anthropic/deepseek-v4-pro",
        "timeout": 90,
        "num_retries": 0,
    },
    "report": {
        "format": "html",
        "render_png": True,
        "include_raw_sample": True,
    },
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_SETTINGS
    with open(CONFIG_FILE, encoding="utf-8") as f:
        settings = json.loads(strip_jsonc(f.read()))
    merged = dict(DEFAULT_SETTINGS)
    merged.update(settings)
    merged["llm"] = {**DEFAULT_SETTINGS["llm"], **settings.get("llm", {})}
    merged["report"] = {**DEFAULT_SETTINGS["report"], **settings.get("report", {})}
    return merged


def strip_jsonc(text):
    """Remove // and /* */ comments plus trailing commas from JSONC text."""
    result = []
    i = 0
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if in_string:
            result.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            i += 2
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        result.append(ch)
        i += 1
    cleaned = "".join(result)
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    return cleaned


def call_llm(messages, max_tokens, llm_config):
    try:
        import litellm
        from litellm import completion
    except ImportError:
        print("[WARN] litellm 未安装，跳过 LLM")
        return None

    litellm.suppress_debug_info = True
    model = llm_config.get("model") or DEFAULT_SETTINGS["llm"]["model"]
    api_key = llm_config.get("auth_token")
    api_base = llm_config.get("base_url")
    kwargs = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "timeout": llm_config.get("timeout", DEFAULT_SETTINGS["llm"]["timeout"]),
        "num_retries": llm_config.get("num_retries", DEFAULT_SETTINGS["llm"]["num_retries"]),
    }
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base

    t0 = time.perf_counter()
    response = completion(**kwargs)
    elapsed = time.perf_counter() - t0
    print(f"[LLM] {model} 用时 {elapsed:.1f}s")
    message = response.choices[0].message
    content = getattr(message, "content", None)
    if content:
        return content
    # Some reasoning models may return only reasoning_content when max_tokens is
    # exhausted. Treat this as no usable answer instead of triggering another LLM call.
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning:
        print("[WARN] LLM 只返回了 reasoning_content，没有返回正文。建议增大 max_tokens 或关闭/更换 reasoning 模型。")
    return None


def detect_db_dir_windows():
    appdata = os.environ.get("APPDATA", "")
    config_dir = os.path.join(appdata, "Tencent", "xwechat", "config")
    candidates = []
    if os.path.isdir(config_dir):
        for ini_file in glob.glob(os.path.join(config_dir, "*.ini")):
            content = None
            for enc in ("utf-8", "gbk"):
                try:
                    with open(ini_file, "r", encoding=enc) as f:
                        content = f.read(1024).strip()
                    break
                except UnicodeDecodeError:
                    continue
                except OSError:
                    break
            if content and os.path.isdir(content):
                candidates.extend(glob.glob(os.path.join(content, "xwechat_files", "*", "db_storage")))

    candidates = [c for c in candidates if os.path.isdir(c)]

    def sort_time(path):
        message_dir = os.path.join(path, "message")
        target = message_dir if os.path.isdir(message_dir) else path
        try:
            return os.path.getmtime(target)
        except OSError:
            return 0

    candidates = sorted(set(candidates), key=sort_time, reverse=True)
    return candidates[0] if candidates else None


def ensure_export_dirs():
    for path in (EXPORT_DIR, DECRYPTED_DIR, REPORTS_DIR, LOGS_DIR):
        os.makedirs(path, exist_ok=True)


def write_wechat_decrypt_config(db_dir):
    ensure_export_dirs()
    cfg = {
        "db_dir": db_dir,
        "keys_file": ALL_KEYS_FILE,
        "decrypted_dir": DECRYPTED_DIR,
        "decoded_image_dir": os.path.join(EXPORT_DIR, "decoded_images"),
        "wechat_process": "Weixin.exe",
        "wxwork_db_dir": "",
        "wxwork_keys_file": os.path.join(EXPORT_DIR, "wxwork_keys.json"),
        "wxwork_decrypted_dir": os.path.join(EXPORT_DIR, "wxwork_decrypted"),
        "wxwork_export_dir": os.path.join(EXPORT_DIR, "wxwork_export"),
        "wxwork_process": "WXWork.exe",
        "transcription_backend": "local",
        "local_whisper_model": "base",
        "openai_api_key": "",
    }
    os.makedirs(os.path.dirname(WECHAT_DECRYPT_CONFIG), exist_ok=True)
    with open(WECHAT_DECRYPT_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)
    return WECHAT_DECRYPT_CONFIG


def find_group(db, name):
    if "@chatroom" in name:
        return name

    if db.contact:
        row = db.contact.execute(
            "SELECT username FROM contact WHERE (nick_name=? OR remark=?) AND username LIKE ?",
            (name, name, "%@chatroom%"),
        ).fetchone()
        if row:
            return row[0]

        rows = db.contact.execute(
            "SELECT username, nick_name, remark FROM contact WHERE (nick_name LIKE ? OR remark LIKE ?) AND username LIKE ?",
            (f"%{name}%", f"%{name}%", "%@chatroom%"),
        ).fetchall()
        if len(rows) == 1:
            return rows[0][0]
        if len(rows) > 1:
            print(f"[WARN] 找到多个匹配 '{name}' 的群，使用第一个:")
            for username, nick, remark in rows:
                print(f"  {remark or nick or username}  {username}")
            return rows[0][0]

    if db.session:
        row = db.session.execute(
            "SELECT username FROM SessionTable WHERE username LIKE ? AND username LIKE ?",
            (f"%{name}%", "%@chatroom%"),
        ).fetchone()
        if row:
            return row[0]
    return None


def day_range(date_str=None):
    d = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
    start = d.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def summarize_with_llm(messages_text, group_name, date_str, llm_config):
    try:
        return call_llm(
            [{
                "role": "user",
                "content": (
                    f"以下是微信群「{group_name}」在 {date_str} 的聊天记录，请用中文简洁总结：\n"
                    f"1. 今日主要讨论话题（2-5个，每个话题一句话概括）\n"
                    f"2. 关键结论或决定\n"
                    f"3. 值得注意的观点或信息（如有）\n\n"
                    f"{messages_text}"
                ),
            }],
            max_tokens=1500,
            llm_config=llm_config,
        )
    except Exception as e:
        print(f"[WARN] LLM 总结失败: {e}")
        return None


def analyze_structured_with_llm(messages_text, group_name, date_str, llm_config):
    prompt = f"""你是群聊日报分析器。请分析微信群「{group_name}」在 {date_str} 的聊天记录。

只输出 JSON，不要 Markdown，不要解释。JSON 格式：
{{
  "summary": "100字内总体概括",
  "topics": [
    {{
      "topic": "话题名",
      "time_range": "HH:MM-HH:MM",
      "contributors": ["成员A", "成员B"],
      "detail": "谁提出了什么、讨论了什么、有什么结论",
      "evidence": ["原话摘录1", "原话摘录2"]
    }}
  ],
  "user_titles": [
    {{"name": "成员名", "title": "简短称号", "reason": "为什么给这个称号"}}
  ]
}}

要求：
- 话题必须按连续对话内容和语义聚合，不要按关键词机械拆分。
- 不要求固定数量；只保留真实形成讨论的主题，通常 3-8 个即可，少就少。
- 单句寒暄、单张图片、@某人、纯表情、无上下文短句不要单独列为话题。
- @对象不是话题，也不是有效证据；纯@消息必须忽略，除非后续有实质内容形成同一段讨论。
- 如果短句是同一段讨论的一部分，应合并到对应话题。
- contributors 必须来自聊天记录中出现的成员名。
- user_titles 只给真实有发言的人，称号要基于行为，不要攻击性。
- 不要把“我”误写成聊天记录里的其他联系人。
- evidence 使用短摘录，不超过 3 条，每条不超过 40 字。

聊天记录：
{messages_text}
"""
    try:
        text = call_llm([{"role": "user", "content": prompt}], max_tokens=5000, llm_config=llm_config)
        return parse_llm_json(text)
    except Exception as e:
        print(f"[WARN] 结构化 LLM 分析失败: {e}")
        return None


def render_report(summaries, date_str):
    ensure_export_dirs()
    md = f"# 微信群日报 - {date_str}\n\n"
    for group_name, info in summaries.items():
        md += f"## {group_name}\n\n"
        md += f"_消息数: {info['count']} 条_\n\n"
        if info.get("summary"):
            md += f"### AI 总结\n\n{info['summary']}\n\n"
        if info.get("sample"):
            md += f"### 部分消息\n\n```\n{info['sample']}\n```\n\n"
        md += "---\n\n"

    path = os.path.join(REPORTS_DIR, f"report_{date_str}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path


def cmd_setup(args):
    db_dir = args.db_dir or detect_db_dir_windows()
    if not db_dir:
        print("[ERROR] 未能自动检测 db_storage，请手动传 --db-dir")
        return 1
    config_path = write_wechat_decrypt_config(db_dir)
    print(f"DB 目录: {db_dir}")
    print(f"已写入配置: {config_path}")
    print(f"输出目录: {EXPORT_DIR}")
    if args.raw_key:
        info = generate_keys(args.raw_key, db_dir, ALL_KEYS_FILE)
        print(f"已生成密钥文件: {info['output']}")
    else:
        print("未传 --raw-key，跳过 all_keys.json 生成")
    return 0


def cmd_decrypt(args):
    result = decrypt_from_keys(ALL_KEYS_FILE, DECRYPTED_DIR, args.only)
    for rel, reason in result["failures"]:
        print(f"[FAIL] {rel}: {reason}")
    print(f"\n输出目录: {result['output_dir']}")
    print(f"完成: {result['ok']} 成功, {result['failed']} 失败, {result['skipped']} 跳过")
    return 1 if result["failed"] else 0


def cmd_groups(_args):
    db = WeChatDB(DECRYPTED_DIR)
    try:
        for s in db.list_sessions():
            if "@chatroom" in s["username"]:
                dn = db.get_chatroom_name(s["username"])
                marker = " *" if dn != s["username"] else ""
                print(f'{dn:30s} {s["username"]:45s} {s["last_time"]}{marker}')
    finally:
        db.close()
    return 0


def cmd_report(args):
    settings = load_config()
    llm_config = settings.get("llm", DEFAULT_SETTINGS["llm"])
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    start, end = day_range(date_str)
    default_groups = settings.get("default_groups") or DEFAULT_SETTINGS["default_groups"]
    groups = [g.strip() for g in (args.groups or ",".join(default_groups)).split(",") if g.strip()]

    db = WeChatDB(
        DECRYPTED_DIR,
        self_wxid=settings.get("self_wxid") or None,
        self_name=settings.get("self_name") or "我",
        display_name_mode=settings.get("display_name_mode", "remark"),
    )
    summaries = {}
    visual_outputs = []
    try:
        print(f"日期: {date_str}")
        print(f"目标群: {groups}")
        for group_name in groups:
            print(f"\n--- {group_name} ---")
            username = find_group(db, group_name)
            if not username:
                print(f"[SKIP] 未找到群: {group_name}")
                continue
            display = db.get_chatroom_name(username)
            messages = db.query_messages(username, start_time=start, end_time=end, limit=args.limit)
            print(f"chatroom: {username} ({display})")
            print(f"消息数: {len(messages)}")
            if not messages:
                continue

            normalized = db.normalize_messages(messages)
            formatted = "\n".join(f'[{m["time_text"]}] {m["sender"]}: {m["text"]}' for m in normalized)
            analysis = None if args.dry_run else analyze_structured_with_llm(formatted, display, date_str, llm_config)
            summary = (analysis or {}).get("summary")
            summaries[display] = {
                "count": len(messages),
                "summary": summary,
                "sample": formatted[:3000] if not summary else formatted[:1000],
            }
            safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in display)[:60]
            html_path = os.path.join(REPORTS_DIR, f"report_{date_str}_{safe_name}.html")
            render_html_report(display, date_str, normalized, analysis, html_path)
            visual_outputs.append(html_path)
            if settings.get("report", {}).get("render_png", True):
                png_path = os.path.join(REPORTS_DIR, f"report_{date_str}_{safe_name}.png")
                ok, reason = render_html_to_png(html_path, png_path)
                if ok:
                    visual_outputs.append(png_path)
                else:
                    print(f"[WARN] PNG 生成失败: {reason}")
    finally:
        db.close()

    if not summaries:
        print("\n没有数据可生成报告")
        return 0
    path = render_report(summaries, date_str)
    print(f"\n报告已保存: {path}")
    for output in visual_outputs:
        print(f"可视化报告: {output}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="微信聊天记录分析工具")
    sub = parser.add_subparsers(dest="command")

    setup = sub.add_parser("setup", help="自动检测 db_storage、写配置、生成 all_keys.json")
    setup.add_argument("--raw-key", help="wx_key 输出的 64 位 hex raw_key")
    setup.add_argument("--db-dir", help="微信 db_storage 目录；不传则尝试自动检测")
    setup.set_defaults(func=cmd_setup)

    decrypt = sub.add_parser("decrypt", help="解密 export/all_keys.json 中记录的数据库")
    decrypt.add_argument("--only", help="只解密包含该字符串的相对路径，如 session.db")
    decrypt.set_defaults(func=cmd_decrypt)

    groups = sub.add_parser("groups", help="列出可用群聊")
    groups.set_defaults(func=cmd_groups)

    report = sub.add_parser("report", help="生成群聊日报")
    report.add_argument("--date", help="日期 YYYY-MM-DD，默认今天")
    report.add_argument("--groups", help="群名列表，逗号分隔，如: 家,.NET性能优化")
    report.add_argument("--dry-run", action="store_true", help="不调用 LLM，只输出消息样本")
    report.add_argument("--limit", type=int, default=1000, help="每个群最多读取消息数")
    report.set_defaults(func=cmd_report)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        args = parser.parse_args(["report"])
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()

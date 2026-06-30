"""Generate simple visual HTML reports for WeChat group activity."""
import html
import json
import os
import re
from collections import Counter

try:
    from paths import REPORTS_DIR
except ImportError:
    from .paths import REPORTS_DIR
import sys as _sys
_shared = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")
if _shared not in _sys.path:
    _sys.path.insert(0, _shared)
from templates import DEFAULT_TEMPLATE, list_templates, render_template


def emoji_count(text):
    return sum(1 for ch in text if ord(ch) >= 0x1F300)


def parse_llm_json(text):
    if not text:
        return None
    # 1) 提取 ```json ... ``` 或 ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if not match:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        candidate = match.group(1).strip()
        if candidate.startswith("{"):
            text = candidate
    # 2) 找不到代码块 → 取最外层 { ... }
    if not text.strip().startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
    # 3) 尝试解析，失败则修复常见问题后重试
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 去掉尾部逗号 (最常导致 json 解析失败的问题)
    fixed = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        return None


def build_stats(messages, top_users_count=8):
    by_hour = Counter(msg["hour"] for msg in messages if msg["hour"] is not None)
    by_sender = Counter(msg["sender"] for msg in messages)
    total_chars = sum(len(msg["text"]) for msg in messages)
    emojis = sum(emoji_count(msg["text"]) for msg in messages)
    active_hour, active_count = (0, 0)
    if by_hour:
        active_hour, active_count = by_hour.most_common(1)[0]
    return {
        "message_count": len(messages),
        "participant_count": len(by_sender),
        "total_characters": total_chars,
        "emoji_count": emojis,
        "hourly": {hour: by_hour.get(hour, 0) for hour in range(24)},
        "most_active_period": f"{active_hour:02d}:00-{(active_hour + 1) % 24:02d}:00" if by_hour else "无",
        "top_users": by_sender.most_common(top_users_count),
    }


def html_escape(value):
    return html.escape(str(value), quote=True)


def _enrich_evidence(topics, messages):
    """给每条 evidence 匹配原始消息，补上发送者名称。"""
    for topic in topics:
        enriched = []
        for item in topic.get("evidence", []):
            matched_sender = None
            # LLM 摘录的 evidence 是原话片段，去空白后匹配
            clean = item.strip()
            for m in messages:
                if clean and (clean in m["text"] or m["text"] in clean):
                    matched_sender = m["sender"]
                    break
            if matched_sender:
                enriched.append(f"{matched_sender}：{item}")
            else:
                enriched.append(item)
        topic["evidence"] = enriched
    return topics


def render_html_report(group_name, date_str, messages, analysis=None, output_path=None,
                       top_users_count=9, evidence_per_topic=3, template=None):
    stats = build_stats(messages, top_users_count=top_users_count)
    topics = (analysis or {}).get("topics") or []
    topics = _enrich_evidence(topics, messages)
    user_titles = (analysis or {}).get("user_titles") or []
    quote = (analysis or {}).get("quote") or {}

    if not user_titles:
        user_titles = [
            {
                "name": name,
                "title": "活跃成员" if idx == 0 else "参与讨论",
                "reason": f"发言 {count} 条",
            }
            for idx, (name, count) in enumerate(stats["top_users"])
        ]

    template_name = template or DEFAULT_TEMPLATE
    html_text = render_template(
        template_name,
        group_name=group_name,
        date_str=date_str,
        stats=stats,
        topics=topics,
        user_titles=user_titles,
        quote=quote,
        top_users_count=top_users_count,
        evidence_per_topic=evidence_per_topic,
    )

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_text)
    return html_text


def find_font():
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def draw_wrapped(draw, xy, text, font, fill, max_width, line_gap=6):
    x, y = xy
    lines = []
    for raw_line in str(text).splitlines() or [""]:
        current = ""
        for ch in raw_line:
            trial = current + ch
            if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += draw.textbbox((0, 0), line, font=font)[3] + line_gap
    return y


def render_html_to_png(html_path, png_path, width=1180):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "未安装 Python Playwright：pip install playwright"

    try:
        html_url = "file:///" + os.path.abspath(html_path).replace(os.sep, "/")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": 1600}, device_scale_factor=1)
            page.goto(html_url)
            height = page.evaluate("document.documentElement.scrollHeight")
            page.set_viewport_size({"width": width, "height": height})
            os.makedirs(os.path.dirname(png_path), exist_ok=True)
            page.screenshot(path=png_path, full_page=True)
            browser.close()
        if os.path.exists(png_path):
            return True, ""
        return False, "Playwright 执行完成，但 PNG 文件未生成"
    except Exception as e:
        msg = str(e)
        if "Executable doesn't exist" in msg or "playwright install" in msg:
            return False, "缺少 Chromium：python -m playwright install chromium"
        return False, msg[:300]

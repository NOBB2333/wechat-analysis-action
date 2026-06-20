"""Generate simple visual HTML reports for WeChat group activity."""
import html
import json
import os
import re
from collections import Counter

from paths import REPORTS_DIR


def emoji_count(text):
    return sum(1 for ch in text if ord(ch) >= 0x1F300)


def parse_llm_json(text):
    if not text:
        return None
    match = re.search(r"```json\s*(.*?)```", text, re.S)
    if match:
        text = match.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
    try:
        return json.loads(text)
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


def render_hourly_chart(hourly):
    max_count = max(hourly.values()) if hourly else 0
    rows = []
    for hour in range(24):
        count = hourly.get(hour, 0)
        width = 0 if max_count == 0 else max(2, int(count / max_count * 100))
        rows.append(
            f'<div class="hour-row"><span class="hour-label">{hour:02d}:00</span>'
            f'<div class="bar-wrap"><div class="bar" style="width:{width}%"></div><span>{count}</span></div></div>'
        )
    return "\n".join(rows)


def render_html_report(group_name, date_str, messages, analysis=None, output_path=None,
                       top_users_count=9, evidence_per_topic=3):
    stats = build_stats(messages, top_users_count=top_users_count)
    topics = (analysis or {}).get("topics") or []
    user_titles = (analysis or {}).get("user_titles") or []

    if not user_titles:
        user_titles = [
            {
                "name": name,
                "title": "活跃成员" if idx == 0 else "参与讨论",
                "reason": f"发言 {count} 条",
            }
            for idx, (name, count) in enumerate(stats["top_users"])
        ]

    topic_cards = []
    for idx, topic in enumerate(topics, 1):
        contributors = "、".join(topic.get("contributors", [])) or "未识别"
        time_range = topic.get("time_range", "")
        evidence_html = ""
        if topic.get("evidence"):
            evidence_html = (
                '<div class="evidence">'
                + ''.join(f'<em>{html_escape(item)}</em>' for item in topic.get("evidence", [])[:evidence_per_topic])
                + '</div>'
            )
        card_html = (
            '<div class="topic-card">'
            f'<div class="topic-head"><span>{idx}</span><strong>{html_escape(topic.get("topic", "未知话题"))}</strong></div>'
            f'<div class="meta">{html_escape(time_range + " / " if time_range else "")}参与者：{html_escape(contributors)}</div>'
            f'<p>{html_escape(topic.get("detail", ""))}</p>'
            f'{evidence_html}'
            '</div>'
        )
        topic_cards.append(card_html)
    if not topic_cards:
        topic_cards.append('<div class="empty">未进行 AI 话题分析，或模型未返回有效话题。</div>')

    user_cards = []
    for item in user_titles[:top_users_count]:
        name = item.get("name") or item.get("user") or "未知"
        title = item.get("title") or "群成员"
        reason = item.get("reason") or ""
        initial = html_escape(name[:1])
        user_cards.append(
            '<div class="user-card">'
            f'<div class="avatar">{initial}</div>'
            '<div>'
            f'<div class="user-name">{html_escape(name)}</div>'
            f'<div class="badge">{html_escape(title)}</div>'
            f'<p>{html_escape(reason)}</p>'
            '</div></div>'
        )

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(group_name)} - {date_str}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f3f3f3; color: #181818; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; }}
    .page {{ width: min(1180px, calc(100vw - 32px)); margin: 0 auto; background: #fff; padding: 46px 34px 36px; }}
    header {{ text-align: center; padding-bottom: 32px; border-bottom: 1px solid #eee; }}
    h1 {{ margin: 0; font-family: "SimSun", "Songti SC", serif; font-size: 32px; letter-spacing: 0; }}
    .date {{ margin-top: 10px; color: #777; font-size: 13px; }}
    section {{ margin-top: 34px; }}
    h2 {{ font-family: "SimSun", "Songti SC", serif; font-size: 21px; margin: 0 0 18px; padding-left: 12px; border-left: 4px solid #222; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
    .stat {{ border: 1px solid #e8e8e8; border-radius: 8px; text-align: center; padding: 18px 8px; background: #fafafa; }}
    .num {{ font-size: 24px; font-weight: 700; }}
    .label {{ color: #777; font-size: 12px; margin-top: 5px; }}
    .active {{ margin-top: 20px; border-radius: 8px; background: #202020; color: #fff; text-align: center; padding: 22px; }}
    .active strong {{ display: block; font-family: Georgia, serif; font-size: 28px; font-weight: 400; }}
    .hour-row {{ display: flex; align-items: center; height: 22px; margin: 4px 0; }}
    .hour-label {{ width: 54px; color: #777; font-size: 12px; }}
    .bar-wrap {{ flex: 1; display: flex; align-items: center; gap: 8px; }}
    .bar {{ height: 7px; background: #333; border-radius: 4px; }}
    .bar-wrap span {{ width: 34px; color: #777; font-size: 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }}
    .topic-card, .user-card {{ border: 1px solid #e8e8e8; border-radius: 8px; background: #fbfbfb; padding: 18px; }}
    .topic-head {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
    .topic-head span {{ width: 22px; height: 22px; border-radius: 50%; background: #111; color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; }}
    .topic-head strong {{ font-size: 16px; }}
    .meta {{ color: #777; font-size: 12px; margin-bottom: 8px; }}
    p {{ margin: 0; color: #444; font-size: 13px; line-height: 1.7; }}
    .evidence {{ margin-top: 10px; display: flex; flex-direction: column; gap: 5px; }}
    .evidence em {{ color: #666; background: #f1f1f1; border-radius: 4px; padding: 5px 8px; font-size: 12px; font-style: normal; }}
    .user-card {{ display: flex; gap: 14px; }}
    .avatar {{ width: 42px; height: 42px; border-radius: 50%; background: #ddd; display: flex; align-items: center; justify-content: center; font-weight: 700; flex: 0 0 auto; }}
    .user-name {{ font-weight: 700; margin-bottom: 6px; }}
    .badge {{ display: inline-block; border: 1px solid #222; border-radius: 4px; padding: 2px 7px; font-size: 12px; margin-bottom: 8px; }}
    .empty {{ grid-column: 1 / -1; border: 1px dashed #ddd; border-radius: 8px; padding: 18px; color: #777; background: #fafafa; }}
    footer {{ margin-top: 42px; padding-top: 20px; border-top: 1px solid #eee; color: #999; text-align: center; font-size: 12px; }}
    @media (max-width: 760px) {{
      .page {{ width: 100%; padding: 28px 18px; }}
      .stats {{ grid-template-columns: repeat(2, 1fr); }}
      .grid {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 26px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header>
      <h1>群聊日常分析报告</h1>
      <div class="date">{html_escape(group_name)} / {date_str}</div>
    </header>
    <section>
      <h2>基础统计</h2>
      <div class="stats">
        <div class="stat"><div class="num">{stats["message_count"]}</div><div class="label">消息总数</div></div>
        <div class="stat"><div class="num">{stats["participant_count"]}</div><div class="label">参与人数</div></div>
        <div class="stat"><div class="num">{stats["total_characters"]}</div><div class="label">总字符数</div></div>
        <div class="stat"><div class="num">{stats["emoji_count"]}</div><div class="label">表情数量</div></div>
      </div>
      <div class="active"><strong>{stats["most_active_period"]}</strong><span>最活跃时段</span></div>
    </section>
    <section>
      <h2>24小时活跃度分布</h2>
      {render_hourly_chart(stats["hourly"])}
    </section>
    <section>
      <h2>热门话题</h2>
      <div class="grid">{''.join(topic_cards)}</div>
    </section>
    <section>
      <h2>群友称号</h2>
      <div class="grid">{''.join(user_cards)}</div>
    </section>
    <footer>Generated by wechat-analysis / Inspired by astrbot_plugin_qq_group_daily_analysis</footer>
  </div>
</body>
</html>"""

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

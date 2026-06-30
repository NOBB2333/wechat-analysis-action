"""二次元模板 — 漫画杂志风格，对话气泡话题、角色卡片用户、贴纸统计、渐变背景。"""

import html

NAME = "二次元"
DESCRIPTION = "漫画杂志风格：对话气泡话题、角色卡片用户、贴纸统计、渐变背景"


def _esc(value):
    """HTML 转义辅助函数。"""
    return html.escape(str(value), quote=True)


def _render_hourly_chart(hourly):
    """渲染 24 小时渐变柱状活跃度图（渐变紫色系）。"""
    max_count = max(hourly.values()) if hourly else 0
    rows = []
    colors = ["#f8bbd0", "#e1bee7", "#ce93d8", "#ba68c8", "#ab47bc",
              "#9c27b0", "#7b1fa2", "#6a1b9a", "#4a148c"]
    for hour in range(24):
        count = hourly.get(hour, 0)
        height = 0 if max_count == 0 else max(4, int(count / max_count * 140))
        color = colors[min(hour // 3, len(colors) - 1)]
        rows.append(
            '<div class="bar-unit">'
            f'<div class="bar-fill" style="height:{height}px;background:{color}"></div>'
            f'<span class="bar-hour">{hour:02d}</span>'
            f'<span class="bar-num">{count}</span>'
            '</div>'
        )
    return "\n".join(rows)


def render(group_name, date_str, stats, topics, user_titles,
           quote=None, top_users_count=9, evidence_per_topic=3):
    """渲染二次元漫画风格完整 HTML 报告。包含渐变 Hero 头图、贴纸统计、对话气泡话题和角色卡片用户。"""
    # --- 贴纸统计 ---
    stat_items = [
        ("📨", stats["message_count"], "消息总数"),
        ("👥", stats["participant_count"], "参与人数"),
        ("📝", stats["total_characters"], "总字符数"),
        ("💕", stats["emoji_count"], "表情数量"),
    ]

    # --- 对话框话题 ---
    topic_boxes = []
    colors_bubble = ["#ffe0f0", "#f0e0ff", "#e0f0ff", "#fff0e0", "#e0ffe8", "#ffe8f0"]
    for idx, topic in enumerate(topics, 1):
        contributors = "、".join(topic.get("contributors", [])) or "未识别"
        time_range = topic.get("time_range", "")
        bg = colors_bubble[(idx - 1) % len(colors_bubble)]
        evidence_html = ""
        if topic.get("evidence"):
            evidence_html = (
                '<div class="bubble-quotes">'
                + ''.join(f'<em>{_esc(item)}</em>' for item in topic.get("evidence", [])[:evidence_per_topic])
                + '</div>'
            )
        topic_boxes.append(
            '<div class="topic-bubble">'
            f'<div class="bubble-arrow" style="border-right-color:{bg}"></div>'
            f'<div class="bubble-body" style="background:{bg}">'
            f'<div class="bubble-header"><span class="bubble-idx">#{idx}</span><strong>{_esc(topic.get("topic", "未知话题"))}</strong></div>'
            f'<div class="bubble-meta">⏰ {_esc(time_range)} · 👤 {_esc(contributors)}</div>'
            f'<p>{_esc(topic.get("detail", ""))}</p>'
            f'{evidence_html}'
            '</div></div>'
        )
    if not topic_boxes:
        topic_boxes.append('<div class="empty-msg">(´；ω；`) 未进行 AI 话题分析...</div>')

    # --- 角色卡片用户 ---
    badges = ["🌸", "🌟", "💎", "✨", "🎀", "💫", "⭐", "🌙", "♠"]
    user_cards = []
    for idx, item in enumerate(user_titles[:top_users_count]):
        name = item.get("name") or item.get("user") or "未知"
        title = item.get("title") or "群成员"
        reason = item.get("reason") or ""
        badge = badges[idx % len(badges)]
        user_cards.append(
            '<div class="char-card">'
            f'<div class="char-avatar"><span>{_esc(name[:1])}</span></div>'
            f'<div class="char-badge">{badge}</div>'
            f'<div class="char-name">{_esc(name)}</div>'
            f'<div class="char-title">{_esc(title)}</div>'
            f'<div class="char-reason">{_esc(reason)}</div>'
            '</div>'
        )

    # --- 名言警句 ---
    quote_html = ""
    if quote and quote.get("text"):
        quote_html = (
            '<div class="quote-ribbon"><span class="quote-icon">📜</span>'
            '<p>「' + _esc(quote["text"]) + '」</p>'
            '<span class="quote-src">—— ' + _esc(quote.get("source", "佚名")) + '</span></div>'
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>✦ {_esc(group_name)} - {date_str}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: linear-gradient(160deg, #fce4ec 0%, #f3e5f5 25%, #e8eaf6 50%, #e1f5fe 75%, #fce4ec 100%);
      background-attachment: fixed;
      color: #4a3b5c;
      font-family: "Segoe UI", "Microsoft YaHei", "Hiragino Sans", "PingFang SC", sans-serif;
      min-height: 100vh;
    }}
    .magazine {{ width: min(1200px, calc(100vw - 24px)); margin: 0 auto; padding: 30px 0 60px; }}

    /* === HERO HEADER === */
    .hero {{
      position: relative;
      background: linear-gradient(135deg, #fff 60%, #fce4ec);
      border-radius: 28px;
      padding: 48px 40px 36px;
      margin-bottom: 32px;
      box-shadow: 0 8px 32px rgba(156, 39, 176, 0.10), 0 2px 8px rgba(0,0,0,0.04);
      text-align: center;
      overflow: hidden;
    }}
    .hero::before {{
      content: "";
      position: absolute;
      top: -60px; right: -40px;
      width: 200px; height: 200px;
      background: radial-gradient(circle, rgba(255,182,193,0.4) 0%, transparent 70%);
      border-radius: 50%;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      bottom: -40px; left: -30px;
      width: 160px; height: 160px;
      background: radial-gradient(circle, rgba(186,104,200,0.25) 0%, transparent 70%);
      border-radius: 50%;
    }}
    .hero h1 {{
      font-size: 36px;
      background: linear-gradient(135deg, #e91e63, #9c27b0, #673ab7);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      font-weight: 900;
      letter-spacing: 2px;
      position: relative;
      z-index: 1;
    }}
    .hero .subtitle {{
      margin-top: 10px;
      font-size: 14px;
      color: #9575cd;
      position: relative;
      z-index: 1;
    }}
    .sparkles {{
      display: flex; justify-content: center; gap: 6px; margin-top: 14px;
      font-size: 20px; position: relative; z-index: 1;
    }}

    /* === STICKER STATS === */
    .sticker-row {{
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
      margin-bottom: 36px;
    }}
    .sticker {{
      background: #fff;
      border-radius: 18px;
      padding: 22px 12px;
      text-align: center;
      box-shadow: 0 4px 16px rgba(156, 39, 176, 0.08);
      border: 2px solid #f3e5f5;
      position: relative;
      transition: transform 0.2s;
    }}
    .sticker:hover {{ transform: translateY(-4px) rotate(2deg); }}
    .sticker:nth-child(2n) {{ transform: rotate(-1deg); }}
    .sticker:nth-child(3n) {{ transform: rotate(1deg); }}
    .sticker:hover:nth-child(2n) {{ transform: translateY(-4px) rotate(-2deg); }}
    .sticker:hover:nth-child(3n) {{ transform: translateY(-4px) rotate(2deg); }}
    .sticker .emoji {{ font-size: 28px; margin-bottom: 6px; }}
    .sticker .val {{ font-size: 28px; font-weight: 800; color: #7b1fa2; }}
    .sticker .lbl {{ font-size: 11px; color: #9575cd; margin-top: 2px; }}

    /* === PEAK BADGE === */
    .peak-ribbon {{
      background: linear-gradient(135deg, #ab47bc, #7e57c2);
      border-radius: 16px;
      padding: 16px 24px;
      text-align: center;
      color: #fff;
      margin-bottom: 36px;
      box-shadow: 0 4px 20px rgba(126, 87, 194, 0.3);
      display: flex; align-items: center; justify-content: center; gap: 16px;
    }}
    .peak-ribbon .peak-val {{ font-size: 32px; font-weight: 800; letter-spacing: 2px; }}
    .peak-ribbon .peak-lbl {{ font-size: 13px; opacity: 0.85; }}

    /* ===  SECTION HEADERS === */
    .section-title {{
      display: flex; align-items: center; gap: 10px;
      font-size: 20px; font-weight: 800; color: #6a1b9a;
      margin: 36px 0 18px;
      padding-left: 8px;
    }}
    .section-title .icon {{ font-size: 24px; }}

    /* === HOUR CHART === */
    .chart-card {{
      background: #fff; border-radius: 20px; padding: 24px 20px;
      box-shadow: 0 4px 16px rgba(156, 39, 176, 0.06);
      margin-bottom: 36px;
    }}
    .bar-chart {{ display: flex; align-items: flex-end; justify-content: space-between; height: 180px; gap: 2px; }}
    .bar-unit {{ display: flex; flex-direction: column; align-items: center; flex: 1; min-width: 0; }}
    .bar-fill {{ width: 100%; max-width: 28px; border-radius: 6px 6px 0 0; min-height: 4px; }}
    .bar-hour {{ font-size: 9px; color: #9575cd; margin-top: 4px; }}
    .bar-num {{ font-size: 9px; color: #ce93d8; }}

    /* === TOPIC BUBBLES === */
    .topic-list {{ display: flex; flex-direction: column; gap: 20px; margin-bottom: 36px; }}
    .topic-bubble {{ display: flex; align-items: flex-start; }}
    .topic-bubble:nth-child(even) {{ flex-direction: row-reverse; }}
    .bubble-arrow {{
      width: 0; height: 0;
      border-top: 12px solid transparent;
      border-bottom: 12px solid transparent;
      border-right: 16px solid #ccc;
      margin-top: 18px;
      flex-shrink: 0;
    }}
    .topic-bubble:nth-child(even) .bubble-arrow {{
      border-right: none;
      border-left: 16px solid #ccc;
    }}
    .bubble-body {{
      flex: 1; border-radius: 18px; padding: 20px; position: relative;
      box-shadow: 0 3px 12px rgba(0,0,0,0.06);
    }}
    .bubble-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
    .bubble-idx {{
      display: inline-flex; align-items: center; justify-content: center;
      width: 26px; height: 26px; border-radius: 50%;
      background: linear-gradient(135deg, #e91e63, #9c27b0);
      color: #fff; font-size: 12px; font-weight: 700;
    }}
    .bubble-header strong {{ font-size: 16px; color: #4a3b5c; }}
    .bubble-meta {{ font-size: 11px; color: #9575cd; margin-bottom: 6px; }}
    .bubble-body p {{ font-size: 13px; color: #5c4a6e; line-height: 1.7; }}
    .bubble-quotes {{ margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }}
    .bubble-quotes em {{
      background: rgba(255,255,255,0.7); border-radius: 10px;
      padding: 5px 10px; font-size: 11px; font-style: normal; color: #6a5a7e;
    }}

    /* === CHARACTER CARDS === */
    .char-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 18px;
      margin-bottom: 36px;
    }}
    .char-card {{
      background: #fff; border-radius: 20px; padding: 24px 16px 20px;
      text-align: center;
      box-shadow: 0 4px 16px rgba(156, 39, 176, 0.07);
      border: 2px solid #f3e5f5;
      position: relative;
      transition: transform 0.2s;
    }}
    .char-card:hover {{ transform: translateY(-4px); }}
    .char-card:nth-child(3n) {{ border-color: #e1bee7; }}
    .char-card:nth-child(4n) {{ border-color: #bbdefb; }}
    .char-avatar {{
      width: 56px; height: 56px; border-radius: 50%;
      background: linear-gradient(135deg, #f48fb1, #ce93d8, #7e57c2);
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 10px;
      color: #fff; font-size: 22px; font-weight: 700;
      box-shadow: 0 3px 10px rgba(156, 39, 176, 0.2);
    }}
    .char-badge {{ font-size: 22px; position: absolute; top: 14px; right: 18px; }}
    .char-name {{ font-weight: 700; font-size: 15px; color: #4a3b5c; margin-bottom: 4px; }}
    .char-title {{
      display: inline-block;
      background: linear-gradient(135deg, #f3e5f5, #e1bee7);
      color: #7b1fa2; border-radius: 10px; padding: 2px 12px;
      font-size: 11px; font-weight: 600; margin-bottom: 8px;
    }}
    .char-reason {{ font-size: 11px; color: #9575cd; line-height: 1.5; }}

    .empty-msg {{ text-align: center; color: #9575cd; padding: 32px; font-size: 14px; background: #fff; border-radius: 16px; }}

    /* === FOOTER === */
    footer {{
      text-align: center; padding: 24px; color: #ce93d8; font-size: 12px;
      border-top: 2px dashed #e1bee7; margin-top: 20px;
    }}

    @media (max-width: 700px) {{
      .sticker-row {{ grid-template-columns: repeat(2, 1fr); }}
      .char-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .hero h1 {{ font-size: 26px; }}
    }}
  </style>
</head>
<body>
<div class="magazine">
  <div class="hero">
    <h1>✦ {_esc(group_name)} 日报 ✦</h1>
    <div class="subtitle">{date_str} · 今日の分析レポート</div>
    <div class="sparkles">🌸 ✨ 💖 ✨ 🌸</div>
  </div>

  <div class="sticker-row">
    {''.join(f'<div class="sticker"><div class="emoji">{e}</div><div class="val">{v}</div><div class="lbl">{l}</div></div>' for e, v, l in stat_items)}
  </div>

  <div class="peak-ribbon">
    <span>⚡</span>
    <div><div class="peak-val">{stats["most_active_period"]}</div><div class="peak-lbl">最活跃时段 ~ みんな集まれ！</div></div>
    <span>⚡</span>
  </div>

  <div class="section-title"><span class="icon">📊</span> 24h 活跃趋势</div>
  <div class="chart-card">
    <div class="bar-chart">{_render_hourly_chart(stats["hourly"])}</div>
  </div>

  <div class="section-title"><span class="icon">💬</span> 热门话题</div>
  <div class="topic-list">{''.join(topic_boxes)}</div>

  <div class="section-title"><span class="icon">🎭</span> 群友角色卡</div>
  <div class="char-grid">{''.join(user_cards)}</div>

  {quote_html}
  <footer>♡ Generated by wechat-analysis · {date_str} · 今日もいい日になりますように ♡</footer>
</div>
</body>
</html>"""

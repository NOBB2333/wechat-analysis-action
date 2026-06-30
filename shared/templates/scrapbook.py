"""手账剪贴簿模板 — 手绘剪贴簿风格，胶带贴纸、旋转卡片、点阵纸背景、手写字体。"""

import html

NAME = "手账剪贴簿"
DESCRIPTION = "手绘剪贴簿风格：胶带贴纸、旋转卡片、点阵纸背景、手写字体"


def _esc(value):
    """HTML 转义辅助函数。"""
    return html.escape(str(value), quote=True)


def _render_hourly_chart(hourly):
    """渲染 24 小时手绘风格横向条形活跃度图。"""
    max_count = max(hourly.values()) if hourly else 0
    rows = []
    for hour in range(24):
        count = hourly.get(hour, 0)
        width = 0 if max_count == 0 else max(2, int(count / max_count * 100))
        color = "#ff7043" if count >= max_count * 0.5 else "#ffab91"
        rows.append(
            '<div class="doodle-row">'
            f'<span class="doodle-label">{hour:02d}</span>'
            f'<div class="doodle-bar-bg"><div class="doodle-bar" style="width:{width}%;background:{color}"></div></div>'
            f'<span class="doodle-num">{count}</span>'
            '</div>'
        )
    return "\n".join(rows)


def render(group_name, date_str, stats, topics, user_titles,
           quote=None, top_users_count=9, evidence_per_topic=3):
    """渲染手账剪贴簿风格完整 HTML 报告。包含胶带贴纸标题、邮票统计、清单话题和旋转宝丽来用户卡片。"""
    # --- Stats as stamps ---
    stat_stamps = [
        ("💬", stats["message_count"], "消息总数"),
        ("👥", stats["participant_count"], "参与人数"),
        ("📝", stats["total_characters"], "总字符数"),
        ("😊", stats["emoji_count"], "表情统计"),
    ]

    # --- Topics as checklist items ---
    topic_items = []
    for idx, topic in enumerate(topics, 1):
        contributors = "、".join(topic.get("contributors", [])) or "未识别"
        time_range = topic.get("time_range", "")
        evidence_html = ""
        if topic.get("evidence"):
            evidence_html = (
                '<div class="scrap-evidence">'
                + ''.join(f'<em>" {_esc(item)} "</em>' for item in topic.get("evidence", [])[:evidence_per_topic])
                + '</div>'
            )
        topic_items.append(
            '<div class="checklist-item">'
            '<div class="check-box"><div class="check-tick"></div></div>'
            '<div class="check-content">'
            f'<div class="check-title">{_esc(topic.get("topic", "未知话题"))}</div>'
            f'<div class="check-meta">{_esc(time_range)} · 参与者：{_esc(contributors)}</div>'
            f'<p>{_esc(topic.get("detail", ""))}</p>'
            f'{evidence_html}'
            '</div></div>'
        )
    if not topic_items:
        topic_items.append('<div class="empty-note">✏️ 未进行 AI 话题分析，或模型未返回有效话题...</div>')

    # --- User cards with tape ---
    tapes = ["#ffb74d", "#64b5f6", "#e57373", "#81c784", "#ba68c8"]
    user_cards = []
    for idx, item in enumerate(user_titles[:top_users_count]):
        name = item.get("name") or item.get("user") or "未知"
        title = item.get("title") or "群成员"
        reason = item.get("reason") or ""
        tape_color = tapes[idx % len(tapes)]
        rotation = [-1.5, 1, -0.5, 1.5, -1, 0.5][idx % 6]
        user_cards.append(
            f'<div class="polaroid" style="transform:rotate({rotation}deg)">'
            f'<div class="tape-piece" style="background:{tape_color}"></div>'
            f'<div class="pol-avatar">{_esc(name[:1])}</div>'
            f'<div class="pol-name">{_esc(name)}</div>'
            f'<div class="pol-badge">{_esc(title)}</div>'
            f'<div class="pol-reason">{_esc(reason)}</div>'
            '</div>'
        )

    # --- 名言警句 ---
    quote_html = ""
    if quote and quote.get("text"):
        quote_html = (
            '<div class="quote-note"><span class="quote-pin">📌</span>'
            '<p>「' + _esc(quote["text"]) + '」</p>'
            '<span class="quote-by">—— ' + _esc(quote.get("source", "佚名")) + '</span></div>'
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(group_name)} - {date_str}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: #fdfbf7;
      background-image: radial-gradient(#e0d8c8 2px, transparent 2px);
      background-size: 22px 22px;
      color: #5d4037;
      font-family: "Patrick Hand", "KaiTi", "STKaiti", "Microsoft YaHei", cursive, sans-serif;
      min-height: 100vh;
      padding: 30px 20px;
    }}
    .journal {{ width: min(1060px, calc(100vw - 24px)); margin: 0 auto; }}

    /* paper card */
    .paper {{
      background: #fff;
      border: 2px solid #5d4037;
      border-radius: 20px;
      padding: 44px 36px;
      box-shadow: 8px 8px 0 #b3e5fc, 16px 16px 0 #ffccbc, 0 24px 40px rgba(0,0,0,0.08);
      position: relative;
      margin-bottom: 36px;
    }}
    .paper::before {{
      content: "";
      position: absolute; top: 12px; bottom: 12px; left: 12px; right: 12px;
      border: 2px dashed #bcaaa4; border-radius: 14px; pointer-events: none; opacity: 0.5;
    }}

    /* title sticker */
    .title-wrap {{
      text-align: center; margin-bottom: 32px; position: relative; padding-top: 10px;
    }}
    .title-sticker {{
      display: inline-block; background: #fff; padding: 16px 50px;
      border: 3px dashed #5d4037; border-radius: 14px;
      box-shadow: 5px 5px 0 #b3e5fc;
      transform: rotate(-2deg); position: relative;
    }}
    .title-sticker h1 {{ font-size: 38px; color: #ff7043; margin: 0; letter-spacing: 2px; }}
    .title-sticker .sticker-tape {{
      position: absolute; top: -14px; left: 50%; transform: translateX(-50%);
      width: 90px; height: 24px; background: rgba(255,183,77,0.7);
    }}
    .date-badge {{
      position: absolute; bottom: -14px; right: -16px;
      background: #fff9c4; padding: 4px 14px; font-size: 14px;
      box-shadow: 2px 2px 3px rgba(0,0,0,0.1); transform: rotate(4deg);
      border: 1px solid #5d4037;
    }}

    /* stamps row */
    .stamps-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 30px; }}
    .stamp {{
      background: #fff; border: 2px solid #5d4037; border-radius: 10px;
      padding: 18px 8px; text-align: center; box-shadow: 4px 4px 0 rgba(0,0,0,0.08);
      position: relative; transition: transform 0.2s;
    }}
    .stamp:hover {{ transform: translateY(-2px); }}
    .stamp::after {{
      content: ""; position: absolute; top: 4px; bottom: 4px; left: 4px; right: 4px;
      border: 1px dotted #e0d8c8; border-radius: 6px; pointer-events: none;
    }}
    .stamp-emoji {{ font-size: 26px; margin-bottom: 4px; }}
    .stamp-num {{ font-size: 26px; font-weight: 700; color: #ff7043; }}
    .stamp-label {{ font-size: 12px; color: #8d6e63; }}

    /* peak highlight */
    .peak-note {{
      background: #fff9c4; border: 2px solid #5d4037; border-radius: 18px;
      padding: 20px; text-align: center; margin-bottom: 30px;
      box-shadow: 6px 6px 0 #ffccbc;
      background-image: repeating-linear-gradient(45deg, rgba(255,255,255,0.3) 0, rgba(255,255,255,0.3) 10px, transparent 10px, transparent 20px);
    }}
    .peak-note .time-big {{ font-size: 36px; color: #5d4037; font-weight: 700; }}
    .peak-note .time-desc {{ font-size: 16px; color: #8d6e63; }}

    /* section headers */
    .sec-title {{
      font-size: 22px; margin: 32px 0 16px; display: flex; align-items: center; gap: 8px;
      color: #ff7043;
    }}

    /* doodle chart */
    .paper-card {{
      background: #fff; border: 2px solid #5d4037; border-radius: 14px;
      padding: 22px 20px; box-shadow: 5px 5px 0 rgba(0,0,0,0.05); margin-bottom: 30px;
    }}
    .doodle-row {{ display: flex; align-items: center; margin: 5px 0; gap: 8px; }}
    .doodle-label {{ width: 32px; font-size: 13px; text-align: right; color: #8d6e63; }}
    .doodle-bar-bg {{ flex: 1; height: 12px; background: #f5f0e8; border-radius: 6px; border: 1px solid #bcaaa4; overflow: hidden; }}
    .doodle-bar {{ height: 10px; border-radius: 5px; min-width: 2px; border: 1px solid #5d4037; }}
    .doodle-num {{ width: 34px; font-size: 11px; color: #8d6e63; }}

    /* checklist topics */
    .checklist {{ display: flex; flex-direction: column; gap: 18px; margin-bottom: 30px; }}
    .checklist-item {{ display: flex; gap: 14px; background: #fff; border: 2px solid #5d4037; border-radius: 12px; padding: 18px; box-shadow: 4px 4px 0 rgba(0,0,0,0.05); }}
    .check-box {{
      width: 24px; height: 24px; border: 2px solid #5d4037; flex-shrink: 0;
      margin-top: 2px; display: flex; align-items: center; justify-content: center;
      background: #fff;
    }}
    .check-tick {{ width: 16px; height: 16px; background: #ff7043; clip-path: polygon(14% 44%, 0 65%, 50% 100%, 100% 16%, 80% 0%, 43% 62%); }}
    .check-title {{ font-size: 18px; font-weight: 700; color: #5d4037; margin-bottom: 4px; }}
    .check-meta {{ font-size: 11px; color: #8d6e63; margin-bottom: 6px; }}
    .check-content p {{ font-size: 13px; color: #5d4037; line-height: 1.7; }}
    .scrap-evidence {{ margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }}
    .scrap-evidence em {{ color: #795548; background: #fff9c4; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-style: normal; }}

    /* polaroid user cards */
    .polaroid-wall {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 24px;
      margin-bottom: 30px;
    }}
    .polaroid {{
      background: #fff; border: 2px solid #5d4037; padding: 14px 14px 18px;
      box-shadow: 4px 4px 0 rgba(0,0,0,0.1); position: relative;
      text-align: center; transition: transform 0.2s;
    }}
    .polaroid:hover {{ transform: rotate(0deg) translateY(-4px) !important; z-index: 5; }}
    .tape-piece {{
      position: absolute; top: -10px; left: 50%; transform: translateX(-50%) rotate(-2deg);
      width: 70px; height: 22px; opacity: 0.8; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .pol-avatar {{
      width: 52px; height: 52px; border-radius: 50%; border: 2px solid #5d4037;
      background: #ffccbc; display: flex; align-items: center; justify-content: center;
      margin: 8px auto 8px; font-size: 22px; font-weight: 700; color: #5d4037;
    }}
    .pol-name {{ font-size: 16px; font-weight: 700; color: #5d4037; margin-bottom: 2px; }}
    .pol-badge {{
      display: inline-block; background: #fffde7; border: 1px solid #ffb74d;
      color: #bf360c; border-radius: 4px; padding: 2px 10px; font-size: 11px; margin-bottom: 6px;
    }}
    .pol-reason {{ font-size: 11px; color: #8d6e63; line-height: 1.5; }}

    .empty-note {{ text-align: center; color: #8d6e63; padding: 24px; font-size: 16px; }}

    /* footer */
    .paper-footer {{
      margin-top: 40px; padding: 16px 20px;
      display: flex; justify-content: space-between; flex-wrap: wrap;
      font-size: 12px; color: #8d6e63;
      border-top: 2px dashed #bcaaa4;
    }}

    @media (max-width: 700px) {{
      .stamps-row {{ grid-template-columns: repeat(2, 1fr); }}
      .polaroid-wall {{ grid-template-columns: repeat(2, 1fr); }}
      .title-sticker h1 {{ font-size: 26px; }}
    }}
  </style>
</head>
<body>
<div class="journal">
<div class="paper">
  <div class="title-wrap">
    <div class="title-sticker">
      <div class="sticker-tape"></div>
      <h1>五彩斑斓的一天</h1>
      <div class="date-badge">{date_str}</div>
    </div>
    <div style="text-align:center;margin-top:22px;font-size:15px;color:#8d6e63;">
      来看看 {_esc(group_name)} 群里发生了什么吧 ✨
    </div>
  </div>

  <div class="stamps-row">
    {''.join(f'<div class="stamp"><div class="stamp-emoji">{e}</div><div class="stamp-num">{v}</div><div class="stamp-label">{l}</div></div>' for e, v, l in stat_stamps)}
  </div>

  <div class="peak-note">
    <div style="font-size:16px;color:#8d6e63;">✨ Highlight Time</div>
    <div class="time-big">{stats["most_active_period"]}</div>
    <div class="time-desc">（此刻，世界色彩斑斓）</div>
  </div>

  <div class="sec-title">📊 24H 活跃轨迹</div>
  <div class="paper-card">{_render_hourly_chart(stats["hourly"])}</div>

  <div class="sec-title">💬 今日话题</div>
  <div class="checklist">{''.join(topic_items)}</div>

  <div class="sec-title">🏆 群友画像</div>
  <div class="polaroid-wall">{''.join(user_cards)}</div>

  {quote_html}
  <div class="paper-footer">
    <span>✂️ 剪贴簿 · {date_str}</span>
    <span>wechat-analysis · 群聊日报</span>
  </div>
</div>
</div>
</body>
</html>"""

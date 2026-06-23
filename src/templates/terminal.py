"""黑客终端模板 — 绿字黑底终端风格，ASCII 艺术分隔，命令行输出格式，极客风。"""

import html

NAME = "黑客终端"
DESCRIPTION = "绿字黑底终端风格，ASCII 艺术分隔，命令行输出格式，极客风"


def _esc(value):
    """HTML 转义辅助函数。"""
    return html.escape(str(value), quote=True)


def _bar(ratio, width=40):
    """按比例渲染终端风格方块条形图（█ + ░）。"""
    filled = max(1, int(ratio * width))
    return "█" * filled + "░" * (width - filled)


def _render_hourly_chart(hourly):
    """渲染 24 小时终端风格块状条形活跃度图。"""
    max_count = max(hourly.values()) if hourly else 0
    rows = []
    for hour in range(24):
        count = hourly.get(hour, 0)
        ratio = 0 if max_count == 0 else count / max_count
        rows.append(
            f'<div class="line"><span class="hour">{hour:02d}</span> '
            f'<span class="bar">{_bar(ratio)}</span> '
            f'<span class="cnt">{count:>4}</span></div>'
        )
    return "\n".join(rows)


def render(group_name, date_str, stats, topics, user_titles,
           quote=None, top_users_count=9, evidence_per_topic=3):
    """渲染黑客终端风格完整 HTML 报告。包含 ASCII 头部、命令行输出格式、cat 查看话题日志、用户排名列表。"""
    # --- Topics as terminal sections ---
    topic_sections = []
    for idx, topic in enumerate(topics, 1):
        contributors = "、".join(topic.get("contributors", [])) or "未识别"
        time_range = topic.get("time_range", "")
        evidence_html = ""
        if topic.get("evidence"):
            evidence_html = (
                '\n'.join(f'<div class="line dim">&gt; {_esc(item)}</div>' for item in topic.get("evidence", [])[:evidence_per_topic])
            )
        topic_sections.append(
            f"""<div class="block">
<div class="line"><span class="prompt">$</span> <span class="cmd">cat /topics/{idx:02d}_{{}}.log</span></div>
<div class="line title"># {_esc(topic.get("topic", "未知话题"))}</div>
<div class="line meta">  time_range={_esc(time_range)}  contributors=[{_esc(contributors)}]</div>
<div class="line">{_esc(topic.get("detail", ""))}</div>
{evidence_html}
</div>"""
        )
    if not topic_sections:
        topic_sections.append('<div class="line warn">[!] 未进行 AI 话题分析，或模型未返回有效话题。</div>')

    # --- Users as system user list ---
    user_lines = []
    for idx, item in enumerate(user_titles[:top_users_count]):
        name = item.get("name") or item.get("user") or "未知"
        title = item.get("title") or "群成员"
        reason = item.get("reason") or ""
        vol = stats["top_users"][idx][1] if idx < len(stats["top_users"]) else 0
        user_lines.append(
            f'<div class="line">'
            f'<span class="idx">[{idx + 1:02d}]</span> '
            f'<span class="user">{_esc(name):<14}</span> '
            f'<span class="tag">{_esc(title):<12}</span> '
            f'<span class="dim">msgs={vol:<5}</span> '
            f'<span class="dim">{_esc(reason)}</span>'
            '</div>'
        )

    # --- 名言警句 ---
    quote_html = ""
    if quote and quote.get("text"):
        quote_html = (
            '<div class="block" style="margin-top:28px;border:1px solid #0a7a1e;padding:14px 18px;">'
            '<div class="line dim">// MOTD — MESSAGE OF THE DAY</div>'
            '<div class="line" style="color:#ffffff;margin-top:4px;">「' + _esc(quote["text"]) + '」</div>'
            '<div class="line dim">—— ' + _esc(quote.get("source", "佚名")) + '</div>'
            '</div>'
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
      background: #0a0a0a;
      color: #00ff41;
      font-family: "Cascadia Code", "Consolas", "Courier New", "SimHei", monospace;
      font-size: 13px;
      line-height: 1.7;
      padding: 20px;
      min-height: 100vh;
    }}
    .screen {{ width: min(1100px, calc(100vw - 40px)); margin: 0 auto; }}
    .glow {{ text-shadow: 0 0 5px rgba(0,255,65,0.5); }}
    .dim {{ color: #0a7a1e; }}
    .warn {{ color: #ffaa00; }}
    hl {{ color: #00ff41; font-weight: bold; }}

    /* header */
    .ascii-header {{ margin-bottom: 24px; }}
    .ascii-header .line {{ color: #00cc33; }}
    .header-info {{ margin: 16px 0 24px; padding: 8px 0; border-top: 1px solid #0a7a1e; border-bottom: 1px solid #0a7a1e; }}

    /* stats box */
    .stats-box {{
      border: 1px solid #0a7a1e;
      padding: 12px 16px;
      margin-bottom: 24px;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
    }}
    .stat-item {{ text-align: center; }}
    .stat-val {{ font-size: 22px; font-weight: 700; color: #00ff41; }}
    .stat-lbl {{ font-size: 10px; color: #0a7a1e; text-transform: uppercase; }}

    /* peak */
    .peak-line {{
      text-align: center; padding: 12px; margin-bottom: 24px;
      border: 1px dashed #0a7a1e; font-size: 18px;
    }}

    /* hour chart */
    .line {{ white-space: pre; }}
    .line .hour {{ color: #0a7a1e; }}
    .line .bar {{ color: #00cc33; }}
    .line .cnt {{ color: #00ff41; }}

    /* section */
    .section-div {{
      margin: 28px 0 16px;
      padding: 4px 8px;
      border-left: 3px solid #00ff41;
      color: #00ff41;
      font-weight: bold;
      font-size: 14px;
    }}

    .block {{ margin-bottom: 20px; }}
    .block .prompt {{ color: #00cc33; }}
    .block .cmd {{ color: #00ff41; }}
    .block .title {{ color: #ffffff; font-weight: bold; font-size: 14px; }}
    .block .meta {{ color: #0a7a1e; font-size: 11px; }}

    .line .idx {{ color: #ffaa00; }}
    .line .user {{ color: #00ff41; font-weight: bold; }}
    .line .tag {{ color: #00cc33; }}

    /* footer */
    .footer-div {{
      margin-top: 36px; padding-top: 12px;
      border-top: 1px solid #0a7a1e;
      color: #0a7a1e; font-size: 11px;
      display: flex; justify-content: space-between;
    }}

    @media (max-width: 700px) {{
      .stats-box {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
<div class="screen">

<div class="ascii-header">
<div class="line">  ┌──────────────────────────────────────────────────────┐</div>
<div class="line">  │  <span class="glow">WECHAT ANALYSIS SYSTEM v3.1</span>                          │</div>
<div class="line">  │  <span class="dim">(c) 2026 Group Intelligence Terminal</span>                │</div>
<div class="line">  └──────────────────────────────────────────────────────┘</div>
</div>

<div class="header-info">
<div class="line"><span class="prompt">analyst@wechat:~$</span> <span class="cmd">./daily_report --group="{_esc(group_name)}" --date={date_str}</span></div>
<div class="line dim">[INFO] 正在加载解密数据... OK</div>
<div class="line dim">[INFO] 正在聚合消息... OK</div>
</div>

<div class="stats-box">
  <div class="stat-item"><div class="stat-val">{stats["message_count"]}</div><div class="stat-lbl">MSG_COUNT</div></div>
  <div class="stat-item"><div class="stat-val">{stats["participant_count"]}</div><div class="stat-lbl">USERS</div></div>
  <div class="stat-item"><div class="stat-val">{stats["total_characters"]}</div><div class="stat-lbl">CHARS</div></div>
  <div class="stat-item"><div class="stat-val">{stats["emoji_count"]}</div><div class="stat-lbl">EMOJI</div></div>
</div>

<div class="peak-line">
  <span class="prompt">$</span> <span class="cmd">peak_detect --window=60m</span>  →  <hl>{stats["most_active_period"]}</hl>  <span class="dim">[最活跃时段]</span>
</div>

<div class="section-div">// HOURLY_ACTIVITY_DISTRIBUTION</div>
{_render_hourly_chart(stats["hourly"])}

<div class="section-div">// TOPIC_ANALYSIS_RESULTS</div>
{''.join(topic_sections)}

<div class="section-div">// USER_RANKING_BY_ACTIVITY</div>
<div class="block">
{''.join(user_lines)}
</div>

    {quote_html}
<div class="footer-div">
  <span>wechat-analysis v3.1</span>
  <span>report_generated: {date_str}</span>
  <span>exit_code: 0</span>
</div>

</div>
</body>
</html>"""

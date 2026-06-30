"""股票终端模板 — 双栏交易终端布局，左侧大盘数据+分时图，右侧交易员排名+板块热度。"""

import html

NAME = "股票终端"
DESCRIPTION = "双栏交易终端布局，左侧大盘数据+分时图，右侧交易员排名+板块热度"


def _esc(value):
    """HTML 转义辅助函数。"""
    return html.escape(str(value), quote=True)


def _render_hourly_chart(hourly):
    """渲染 24 小时分时成交柱状图（蜡烛图风格）。"""
    max_count = max(hourly.values()) if hourly else 0
    rows = []
    for hour in range(24):
        count = hourly.get(hour, 0)
        height = 0 if max_count == 0 else max(3, int(count / max_count * 160))
        gradient = "#00d4aa" if hour < 12 else "#ff6b35"
        rows.append(
            '<div class="candle-col">'
            f'<span class="candle-val">{count}</span>'
            f'<div class="candle" style="height:{height}px;background:{gradient}"></div>'
            f'<span class="candle-hour">{hour:02d}</span>'
            '</div>'
        )
    return "\n".join(rows)


def render(group_name, date_str, stats, topics, user_titles,
           quote=None, top_users_count=9, evidence_per_topic=3):
    """渲染股票终端风格完整 HTML 报告。包含状态栏、行情滚动条、大盘数据、分时图、交易员排名和板块行情。"""
    # --- 话题板块 (板块行情) ---
    topic_cards = []
    for idx, topic in enumerate(topics, 1):
        contributors = "、".join(topic.get("contributors", [])) or "未识别"
        time_range = topic.get("time_range", "")
        ticker = "".join(ch for ch in topic.get("topic", "???") if ch.isalpha())[:4].upper() or "CHAT"
        change_pct = (idx * 7 + 3) % 20 - 5  # deterministic "change"
        direction = "up" if change_pct >= 0 else "down"
        evidence_html = ""
        if topic.get("evidence"):
            evidence_html = (
                '<div class="stock-quotes">'
                + ''.join(f'<em>{_esc(item)}</em>' for item in topic.get("evidence", [])[:evidence_per_topic])
                + '</div>'
            )
        topic_cards.append(
            '<tr class="sector-row">'
            f'<td class="col-ticker"><span>{ticker}</span></td>'
            f'<td class="col-name"><strong>{_esc(topic.get("topic", "未知话题"))}</strong><div class="col-meta">{_esc(time_range)} · {_esc(contributors)}</div></td>'
            f'<td class="col-detail"><p>{_esc(topic.get("detail", ""))}</p>{evidence_html}</td>'
            f'<td class="col-change {direction}">{"+" if change_pct >= 0 else ""}{change_pct}%</td>'
            '</tr>'
        )
    if not topic_cards:
        topic_cards.append('<tr><td colspan="4" class="empty-row">未进行 AI 话题分析，或模型未返回有效话题。</td></tr>')

    # --- 交易员排名 (像 order book) ---
    user_cards = []
    for idx, item in enumerate(user_titles[:top_users_count]):
        name = item.get("name") or item.get("user") or "未知"
        title = item.get("title") or "群成员"
        reason = item.get("reason") or ""
        vol = stats["top_users"][idx][1] if idx < len(stats["top_users"]) else 0
        user_cards.append(
            '<tr class="trader-row">'
            f'<td class="rank">#{idx + 1}</td>'
            f'<td class="trader-info"><span class="trader-name">{_esc(name)}</span><span class="trader-badge">{_esc(title)}</span></td>'
            f'<td class="trader-vol">{vol}</td>'
            f'<td class="trader-reason">{_esc(reason)}</td>'
            '</tr>'
        )

    # --- 名言警句 ---
    quote_html = ""
    if quote and quote.get("text"):
        quote_html = (
            '<div class="quote-box"><span class="quote-label">ANALYST NOTE</span>'
            '<p>「' + _esc(quote["text"]) + '」</p>'
            '<span class="quote-src">—— ' + _esc(quote.get("source", "佚名")) + '</span></div>'
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(group_name)} - {date_str}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0c1017; color: #b0bec5; font-family: "Consolas", "Cascadia Code", "SimHei", "Microsoft YaHei", monospace; }}
    .terminal {{ width: min(1280px, 100vw); margin: 0 auto; background: #0f1419; min-height: 100vh; }}
    /* 顶部状态栏 */
    .status-bar {{ display: flex; align-items: center; gap: 20px; padding: 8px 20px; background: #080c10; border-bottom: 1px solid #1a2530; font-size: 11px; color: #4a5a6a; }}
    .status-bar .dot {{ width: 8px; height: 8px; border-radius: 50%; }}
    .status-bar .dot.green {{ background: #00d4aa; }}
    .status-bar .dot.orange {{ background: #ff6b35; }}
    /* 行情滚动条 */
    .ticker-tape {{ display: flex; gap: 0; padding: 6px 0; background: #080c10; border-bottom: 1px solid #1a2530; overflow: hidden; font-size: 11px; white-space: nowrap; }}
    .ticker-item {{ padding: 0 24px; border-right: 1px solid #1a2530; }}
    .ticker-item .sym {{ color: #5c6e80; margin-right: 8px; }}
    .ticker-item .up {{ color: #00d4aa; }}
    .ticker-item .down {{ color: #ff4444; }}
    /* header */
    header {{ padding: 28px 32px 20px; border-bottom: 2px solid #1a2530; }}
    header h1 {{ font-size: 22px; color: #e6edf3; letter-spacing: 3px; text-transform: uppercase; }}
    header .sub {{ color: #4a5a6a; font-size: 12px; margin-top: 6px; }}
    /* 双栏布局 */
    .main-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; }}
    .col-left {{ border-right: 1px solid #1a2530; }}
    .panel {{ padding: 24px 28px; border-bottom: 1px solid #1a2530; }}
    .panel-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 18px; }}
    .panel-header .indicator {{ width: 3px; height: 16px; background: #ff6b35; }}
    .panel-header h2 {{ font-size: 13px; color: #ff6b35; letter-spacing: 2px; text-transform: uppercase; }}
    /* 四大数据卡 */
    .data-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .data-card {{ background: #111820; border: 1px solid #1a2530; border-radius: 4px; padding: 18px 16px; text-align: center; }}
    .data-card .value {{ font-size: 30px; font-weight: 700; color: #e6edf3; line-height: 1; }}
    .data-card .value.highlight {{ color: #00d4aa; }}
    .data-card .unit {{ font-size: 10px; color: #4a5a6a; margin-top: 4px; letter-spacing: 1px; }}
    /* 活跃时段高亮 */
    .peak-box {{ background: linear-gradient(135deg, #141e2b, #111820); border: 1px solid #1a2530; border-radius: 4px; padding: 20px; text-align: center; margin-top: 14px; }}
    .peak-box .peak-time {{ font-size: 38px; font-weight: 700; color: #ff6b35; letter-spacing: 2px; }}
    .peak-box .peak-label {{ font-size: 11px; color: #4a5a6a; margin-top: 4px; letter-spacing: 1px; }}
    /* 分时图 - 横向蜡烛 */
    .chart-wrap {{ display: flex; align-items: flex-end; justify-content: space-between; height: 200px; padding: 0 4px; }}
    .candle-col {{ display: flex; flex-direction: column; align-items: center; flex: 1; }}
    .candle-val {{ font-size: 9px; color: #4a5a6a; margin-bottom: 2px; }}
    .candle {{ width: 14px; border-radius: 2px 2px 0 0; min-height: 3px; }}
    .candle-hour {{ font-size: 9px; color: #4a5a6a; margin-top: 4px; }}
    /* 板块行情表 */
    .sector-table {{ width: 100%; border-collapse: collapse; }}
    .sector-table th {{ text-align: left; font-size: 10px; color: #4a5a6a; padding: 8px 12px; border-bottom: 1px solid #1a2530; letter-spacing: 1px; text-transform: uppercase; }}
    .sector-table td {{ padding: 14px 12px; border-bottom: 1px solid #111820; vertical-align: top; }}
    .sector-row:hover {{ background: #111820; }}
    .col-ticker span {{ display: inline-block; background: #ff6b35; color: #080c10; padding: 2px 6px; border-radius: 2px; font-size: 10px; font-weight: 700; }}
    .col-name strong {{ color: #e6edf3; font-size: 14px; display: block; }}
    .col-meta {{ color: #3a4a5a; font-size: 11px; margin-top: 3px; }}
    .col-detail p {{ color: #6a7a8a; font-size: 12px; line-height: 1.6; }}
    .col-change {{ text-align: right; font-size: 13px; font-weight: 700; white-space: nowrap; }}
    .col-change.up {{ color: #00d4aa; }}
    .col-change.down {{ color: #ff4444; }}
    .stock-quotes {{ margin-top: 8px; display: flex; flex-direction: column; gap: 3px; }}
    .stock-quotes em {{ color: #5a6a7a; background: #0d1117; border-left: 2px solid #ff6b35; padding: 3px 8px; font-size: 11px; font-style: normal; display: block; }}
    /* 交易员排名表 */
    .trader-table {{ width: 100%; border-collapse: collapse; }}
    .trader-table th {{ text-align: left; font-size: 10px; color: #4a5a6a; padding: 8px 12px; border-bottom: 1px solid #1a2530; letter-spacing: 1px; }}
    .trader-row {{ border-bottom: 1px solid #111820; }}
    .trader-row:hover {{ background: #111820; }}
    .trader-row td {{ padding: 12px; vertical-align: middle; }}
    .rank {{ color: #ff6b35; font-weight: 700; font-size: 13px; width: 40px; }}
    .trader-name {{ color: #e6edf3; font-weight: 600; font-size: 13px; }}
    .trader-badge {{ display: inline-block; border: 1px solid #ff6b35; color: #ff6b35; border-radius: 2px; padding: 1px 8px; font-size: 10px; margin-left: 8px; }}
    .trader-vol {{ color: #00d4aa; font-weight: 700; font-size: 13px; width: 50px; text-align: right; }}
    .trader-reason {{ color: #4a5a6a; font-size: 11px; }}
    .empty-row {{ text-align: center; color: #4a5a6a; padding: 24px; }}
    /* 全宽板块 (话题) */
    .full-width {{ grid-column: 1 / -1; }}
    /* footer */
    footer {{ padding: 20px 32px; border-top: 1px solid #1a2530; color: #2a3a4a; font-size: 10px; display: flex; justify-content: space-between; }}
    @media (max-width: 860px) {{
      .main-grid {{ grid-template-columns: 1fr; }}
      .col-left {{ border-right: none; }}
      .data-grid {{ grid-template-columns: 1fr 1fr; }}
      .chart-wrap {{ height: 140px; }}
    }}
  </style>
</head>
<body>
<div class="terminal">
  <div class="status-bar">
    <div class="dot green"></div><span>LIVE</span>
    <div class="dot orange"></div><span>SZSE</span>
    <span style="flex:1"></span>
    <span>SESSION: {date_str}</span>
    <span>DELAY: 0ms</span>
  </div>
  <div class="ticker-tape">
    <span class="ticker-item"><span class="sym">MSGS</span> <span class="up">{stats["message_count"]}</span></span>
    <span class="ticker-item"><span class="sym">USRS</span> <span class="up">{stats["participant_count"]}</span></span>
    <span class="ticker-item"><span class="sym">CHRS</span> <span class="up">{stats["total_characters"]}</span></span>
    <span class="ticker-item"><span class="sym">EMOJ</span> <span class="up">{stats["emoji_count"]}</span></span>
    <span class="ticker-item"><span class="sym">PEAK</span> <span class="up">{stats["most_active_period"]}</span></span>
  </div>
  <header>
    <h1>{_esc(group_name)} 群聊日报</h1>
    <div class="sub">DAILY ACTIVITY REPORT · {date_str}</div>
  </header>

  <div class="main-grid">
    <!-- 左栏: 大盘数据 + 分时图 -->
    <div class="col-left">
      <div class="panel">
        <div class="panel-header"><div class="indicator"></div><h2>大盘数据 MARKET DATA</h2></div>
        <div class="data-grid">
          <div class="data-card"><div class="value">{stats["message_count"]}</div><div class="unit">成交量 VOL</div></div>
          <div class="data-card"><div class="value highlight">{stats["participant_count"]}</div><div class="unit">活跃账户 ACCT</div></div>
          <div class="data-card"><div class="value">{stats["total_characters"]}</div><div class="unit">流通字符 CHR</div></div>
          <div class="data-card"><div class="value highlight">{stats["emoji_count"]}</div><div class="unit">情绪指数 EMO</div></div>
        </div>
        <div class="peak-box">
          <div class="peak-time">{stats["most_active_period"]}</div>
          <div class="peak-label">集合竞价时段 · PEAK AUCTION</div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-header"><div class="indicator"></div><h2>分时成交 INTRADAY</h2></div>
        <div class="chart-wrap">{_render_hourly_chart(stats["hourly"])}</div>
      </div>
    </div>

    <!-- 右栏: 交易员排名 -->
    <div class="col-right">
      <div class="panel">
        <div class="panel-header"><div class="indicator" style="background:#00d4aa"></div><h2 style="color:#00d4aa">交易员排名 TRADER BOARD</h2></div>
        <table class="trader-table">
          <thead><tr><th>#</th><th>交易员</th><th>成交量</th><th>评价</th></tr></thead>
          <tbody>{''.join(user_cards)}</tbody>
        </table>
      </div>
    </div>

    <!-- 全宽: 板块行情 -->
    <div class="panel full-width">
      <div class="panel-header"><div class="indicator"></div><h2>热门板块 SECTOR HEATMAP</h2></div>
      <table class="sector-table">
        <thead><tr><th style="width:60px">代码</th><th style="width:200px">板块名称</th><th>详情</th><th style="width:60px">涨跌</th></tr></thead>
        <tbody>{''.join(topic_cards)}</tbody>
      </table>
    </div>
  </div>

  {quote_html}
  <footer>
    <span>WECHAT-ANALYSIS TERMINAL v2.0</span>
    <span>市场有风险 · 聊天需谨慎 · {date_str}</span>
  </footer>
</div>
</body>
</html>"""

#!/usr/bin/env python3
"""
A股每日复盘 - 报告生成模块 v2.0
基于采集的数据生成 HTML 网页报告 + Markdown 邮件内容
支持行业板块领涨股TOP3、涨停全量归因、概念板块统计等增强功能
"""

import json
import os
from datetime import datetime

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "docs")


def load_data(date_str=None):
    """加载数据"""
    if date_str:
        path = os.path.join(OUTPUT_DIR, f"data_{date_str}.json")
    else:
        path = os.path.join(OUTPUT_DIR, "latest.json")

    if not os.path.exists(path):
        print(f"❌ 数据文件不存在: {path}")
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def market_sentiment(data):
    """判断市场情绪"""
    bw = data.get("市场宽度", {})
    up = bw.get("上涨家数", 0)
    down = bw.get("下跌家数", 0)

    if up + down == 0:
        return "数据缺失"

    ratio = up / (up + down) if (up + down) > 0 else 0.5

    if ratio >= 0.8:
        return "🔥 极度亢奋"
    elif ratio >= 0.6:
        return "😊 偏暖"
    elif ratio >= 0.4:
        return "😐 中性"
    elif ratio >= 0.2:
        return "😟 偏冷"
    else:
        return "❄️ 极度悲观"


def pct_class(val):
    """根据值返回 CSS class"""
    try:
        v = float(val)
        return "up" if v > 0 else ("down" if v < 0 else "flat")
    except (ValueError, TypeError):
        return ""


def pct_arrow(val):
    """涨跌箭头"""
    try:
        return "▲" if float(val) >= 0 else "▼"
    except (ValueError, TypeError):
        return ""


def fmt_pct(val):
    """格式化百分比"""
    try:
        return f"{float(val):+.2f}%"
    except (ValueError, TypeError):
        return str(val)


def fmt_num(val, decimals=2):
    """格式化数字"""
    try:
        return f"{float(val):.{decimals}f}"
    except (ValueError, TypeError):
        return str(val)


# ============================================================
# HTML 报告生成
# ============================================================

def generate_html_report(data):
    """生成完整 HTML 报告"""
    today = data.get("日期", datetime.now().strftime("%Y-%m-%d"))

    indexes = data.get("大盘指数", [])
    sectors = data.get("行业板块", {})
    concepts = data.get("概念板块", {})
    breadth = data.get("市场宽度", {})
    hot_stocks = data.get("热门个股", {})
    limit_data = data.get("涨跌停统计", {})
    north = data.get("北向资金", {})
    sentiment = market_sentiment(data)
    amount_compare = breadth.get("成交额对比", {})

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A股每日复盘报告 - {today}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            text-align: center; padding: 40px 20px;
            background: linear-gradient(135deg, #e94560, #0f3460);
            border-radius: 16px; margin-bottom: 24px;
        }}
        .header h1 {{ font-size: 2.2em; color: #fff; margin-bottom: 8px; }}
        .header .date {{ font-size: 1.1em; color: rgba(255,255,255,0.8); }}
        .header .sentiment {{
            display: inline-block; margin-top: 12px; padding: 8px 24px;
            background: rgba(255,255,255,0.15); border-radius: 20px;
            font-size: 1.3em; color: #fff;
        }}
        .card {{
            background: rgba(255,255,255,0.05); backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1); border-radius: 12px;
            padding: 24px; margin-bottom: 20px;
        }}
        .card h2 {{
            font-size: 1.3em; color: #e94560; margin-bottom: 16px;
            padding-bottom: 8px; border-bottom: 2px solid rgba(233,69,96,0.3);
        }}
        .card h3 {{
            font-size: 1.05em; color: #ff9a76; margin: 16px 0 10px;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.92em; }}
        th {{ background: rgba(233,69,96,0.2); padding: 10px 8px; text-align: left; font-weight: 600; color: #e94560; white-space: nowrap; }}
        td {{ padding: 9px 8px; border-bottom: 1px solid rgba(255,255,255,0.06); }}
        tr:hover {{ background: rgba(255,255,255,0.04); }}
        .number {{ text-align: right; font-variant-numeric: tabular-nums; }}
        .center {{ text-align: center; }}
        .up {{ color: #ff4d4d; font-weight: 600; }}
        .down {{ color: #4dff4d; font-weight: 600; }}
        .flat {{ color: #888; }}
        .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        @media (max-width: 768px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
        .stats {{ display: flex; justify-content: space-around; flex-wrap: wrap; gap: 16px; }}
        .stat-item {{ text-align: center; padding: 14px 12px; background: rgba(255,255,255,0.05); border-radius: 8px; min-width: 110px; }}
        .stat-value {{ font-size: 1.6em; font-weight: 700; }}
        .stat-label {{ font-size: 0.8em; color: #888; margin-top: 4px; }}
        .stat-sub {{ font-size: 0.75em; color: #aaa; margin-top: 2px; }}
        .tag {{
            display: inline-block; padding: 3px 10px; border-radius: 12px;
            margin: 2px; font-size: 0.82em;
        }}
        .tag.up {{ background: rgba(255,77,77,0.2); }}
        .tag.down {{ background: rgba(77,255,77,0.2); }}
        .bar-row {{ display: flex; align-items: center; margin: 6px 0; gap: 12px; }}
        .bar-label {{ width: 100px; font-size: 0.85em; color: #aaa; text-align: right; }}
        .bar-bg {{ flex: 1; height: 18px; background: rgba(255,255,255,0.08); border-radius: 9px; overflow: hidden; }}
        .bar-fill {{ height: 100%; border-radius: 9px; transition: width 0.5s ease; }}
        .bar-count {{ width: 120px; font-size: 0.85em; color: #ccc; }}
        .sub-row {{ font-size: 0.82em; color: #aaa; padding: 3px 8px 3px 24px; display: flex; gap: 12px; flex-wrap: wrap; }}
        .reason-tag {{
            display: inline-block; padding: 2px 8px; border-radius: 10px;
            font-size: 0.78em; margin: 1px 3px;
            background: rgba(255,255,255,0.08); color: #ccc;
        }}
        .reason-tag.leader {{ background: rgba(233,69,96,0.25); color: #ff9a76; }}
        .reason-tag.early {{ background: rgba(255,153,0,0.2); color: #ffb84d; }}
        .footer {{ text-align: center; padding: 24px; color: #666; font-size: 0.85em; }}
        .summary-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
        @media (max-width: 768px) {{ .summary-grid {{ grid-template-columns: 1fr; }} }}
        .small-table {{ font-size: 0.85em; }}
        .small-table td, .small-table th {{ padding: 6px 8px; }}
        .highlight {{ color: #ff9a76; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <div class="header">
            <h1>📊 A股每日复盘报告</h1>
            <div class="date">{today} | {data.get('采集时间', '')}</div>
            <div class="sentiment">市场情绪: {sentiment}</div>
        </div>

        <!-- 核心概览（含成交额对比） -->
        <div class="card">
            <h2>📈 核心概览</h2>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-value up">{breadth.get('上涨家数', '-')}</div>
                    <div class="stat-label">上涨家数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value down">{breadth.get('下跌家数', '-')}</div>
                    <div class="stat-label">下跌家数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{breadth.get('总成交额(亿)', '-')}</div>
                    <div class="stat-label">总成交额(亿)</div>
                    {_amount_compare_sub(amount_compare)}
                </div>
                <div class="stat-item">
                    <div class="stat-value up">{limit_data.get('涨停数量', '-')}</div>
                    <div class="stat-label">涨停家数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value down">{limit_data.get('跌停数量', '-')}</div>
                    <div class="stat-label">跌停家数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{north.get('当日净流入(亿)', '-')}</div>
                    <div class="stat-label">北向资金(亿)</div>
                </div>
            </div>
        </div>

        <!-- 大盘指数（8个） -->
        <div class="card">
            <h2>📊 大盘指数</h2>
            <table>
                <thead>
                    <tr>
                        <th>指数名称</th>
                        <th class="number">当前点位</th>
                        <th class="number">涨跌幅</th>
                        <th class="number">涨跌额</th>
                        <th class="number">成交额</th>
                    </tr>
                </thead>
                <tbody>{_index_rows_html(indexes)}</tbody>
            </table>
        </div>

        <!-- 行业板块 TOP10（含领涨股TOP3） -->
        <div class="card">
            <h2>🏭 行业板块 TOP10</h2>
            <table>
                <thead>
                    <tr>
                        <th>排名</th>
                        <th>板块</th>
                        <th class="number">涨跌幅</th>
                        <th class="number">成交额</th>
                        <th>领涨股 TOP3</th>
                    </tr>
                </thead>
                <tbody>{_industry_top_html(sectors.get("top10", []))}</tbody>
            </table>
        </div>

        <!-- 行业板块 跌幅榜（5个） -->
        <div class="card">
            <h2>📉 行业板块 跌幅榜 TOP5</h2>
            <table>
                <thead>
                    <tr><th>排名</th><th>板块</th><th class="number">涨跌幅</th><th class="number">成交额</th></tr></thead>
                <tbody>{_industry_bottom_html(sectors.get("bottom5", []))}</tbody>
            </table>
        </div>

        <!-- 概念板块（表格形式，含涨停统计） -->
        <div class="card">
            <h2>💡 概念板块 TOP10（含涨停统计）</h2>
            <table>
                <thead>
                    <tr>
                        <th>概念名称</th>
                        <th class="number">涨跌幅</th>
                        <th class="number">涨停个数</th>
                        <th class="number">涨超5%个数</th>
                    </tr>
                </thead>
                <tbody>{_concept_top_html(concepts.get("top10", []))}</tbody>
            </table>
            {_concept_bottom_html(concepts.get("bottom5", []))}
        </div>

        <!-- 市场宽度 -->
        <div class="card">
            <h2>📊 市场宽度分布</h2>
            {_breadth_bars_html(breadth)}
        </div>

        <!-- 涨停板全量 + 归因汇总 -->
        <div class="card">
            <h2>🚀 涨停板全量分析（{limit_data.get('涨停数量', 0)}只）</h2>
            {_limit_reason_summary_html(limit_data.get("涨停归因汇总", {}))}
            <h3>涨停个股明细</h3>
            <table class="small-table">
                <thead>
                    <tr>
                        <th>代码</th>
                        <th>名称</th>
                        <th class="number">涨幅</th>
                        <th class="center">连板</th>
                        <th>封板时间</th>
                        <th>涨停原因</th>
                        <th class="number">封单</th>
                    </tr>
                </thead>
                <tbody>{_limit_all_html(limit_data.get("涨停明细", []))}</tbody>
            </table>
        </div>

        <!-- 成交额 TOP20 + 占比 -->
        <div class="card">
            <h2>🔥 成交额 TOP20 <span style="font-size:0.7em;color:#888;">（占全市场 {hot_stocks.get('top20占比(%)', 0)}%）</span></h2>
            <table>
                <thead>
                    <tr>
                        <th>排名</th>
                        <th>代码</th>
                        <th>名称</th>
                        <th class="number">价格</th>
                        <th class="number">涨跌幅</th>
                        <th class="number">成交额</th>
                        <th class="number">换手率</th>
                    </tr>
                </thead>
                <tbody>{_hot20_html(hot_stocks.get("top20", []))}</tbody>
            </table>
        </div>

        <!-- 页脚 -->
        <div class="footer">
            <p>⚠️ 本报告由自动化程序生成，仅供参考，不构成投资建议。</p>
            <p>Generated by A-Stock Daily Review Bot v2.0 | {today}</p>
        </div>
    </div>
</body>
</html>"""

    # 保存 HTML
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html_path = os.path.join(OUTPUT_DIR, "index.html")
    date_html_path = os.path.join(OUTPUT_DIR, f"report_{today}.html")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(date_html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML 报告已生成: {html_path}")
    return html_path


# ---- HTML 辅助函数 ----

def _amount_compare_sub(ac):
    """成交额对比子行"""
    if not ac or ac.get("环比变化(%)") == "N/A":
        return ""
    circ = float(ac["环比变化(%)"])
    vs5 = float(ac["与5日均值比(%)"])
    circ_cls = "up" if circ > 0 else "down"
    vs5_cls = "up" if vs5 > 0 else "down"
    return f"""
                <div class="stat-sub"><span class="{circ_cls}">环比 {circ:+.1f}%</span></div>
                <div class="stat-sub">5日均 {ac['5日均成交额(亿)']}亿</div>
                <div class="stat-sub"><span class="{vs5_cls}">vs5日 {vs5:+.1f}%</span></div>"""


def _index_rows_html(indexes):
    rows = ""
    for idx in indexes:
        pct = idx["涨跌幅(%)"]
        cls = pct_class(pct)
        arrow = pct_arrow(pct)
        rows += f"""
        <tr>
            <td>{idx['指数名称']}</td>
            <td class="number">{fmt_num(idx['当前点位'])}</td>
            <td class="number {cls}">{arrow} {fmt_pct(pct)}</td>
            <td class="number">{idx.get('涨跌额', '-')}</td>
            <td class="number">{idx.get('成交额(亿)', '-')}亿</td>
        </tr>"""
    return rows


def _industry_top_html(top10):
    rows = ""
    for i, s in enumerate(top10):
        pct = s["涨跌幅(%)"]
        cls = pct_class(pct)
        arrow = pct_arrow(pct)
        top3 = s.get("领涨股TOP3", [])
        top3_html = ""
        if top3:
            top3_parts = []
            for j, stock in enumerate(top3):
                sp = stock["涨跌幅(%)"]
                scls = pct_class(sp)
                top3_parts.append(f'<span class="{scls}">{j+1}.{stock["名称"]}({fmt_pct(sp)})</span>')
            top3_html = " | ".join(top3_parts)
        else:
            top3_html = s.get("领涨股", "-")

        rows += f"""
        <tr>
            <td class="center">{i+1}</td>
            <td>{s['板块名称']}</td>
            <td class="number {cls}">{arrow} {fmt_pct(pct)}</td>
            <td class="number">{s.get('成交额(亿)', '-')}</td>
            <td style="font-size:0.85em;">{top3_html}</td>
        </tr>"""
    return rows


def _industry_bottom_html(bottom5):
    rows = ""
    for i, s in enumerate(bottom5):
        pct = s["涨跌幅(%)"]
        cls = pct_class(pct)
        arrow = pct_arrow(pct)
        rows += f"""
        <tr>
            <td class="center">{i+1}</td>
            <td>{s['板块名称']}</td>
            <td class="number {cls}">{arrow} {fmt_pct(pct)}</td>
            <td class="number">{s.get('成交额(亿)', '-')}</td>
        </tr>"""
    return rows


def _concept_top_html(top10):
    rows = ""
    for s in top10:
        pct = s["涨跌幅(%)"]
        cls = pct_class(pct)
        arrow = pct_arrow(pct)
        rows += f"""
        <tr>
            <td>{s['概念名称']}</td>
            <td class="number {cls}">{arrow} {fmt_pct(pct)}</td>
            <td class="number up">{s.get('涨停个数', 0)}</td>
            <td class="number">{s.get('涨超5%个数', 0)}</td>
        </tr>"""
    return rows


def _concept_bottom_html(bottom5):
    if not bottom5:
        return ""
    rows = ""
    for s in bottom5:
        pct = s["涨跌幅(%)"]
        cls = pct_class(pct)
        arrow = pct_arrow(pct)
        rows += f'<span class="tag {cls}">❄️ {s["概念名称"]} {fmt_pct(pct)}</span>'
    return f'<div style="margin-top:12px;"><strong>📉 跌幅前5:</strong><br>{rows}</div>'


def _breadth_bars_html(breadth):
    dist = breadth.get("涨幅分布", {})
    total = sum(dist.values())
    if total == 0:
        return '<p style="color:#888;">暂无数据</p>'

    bars = ""
    labels = ["涨停(≥9%)", "大涨(5%-9%)", "中涨(3%-5%)", "小涨(0-3%)",
              "小跌(0-3%)", "中跌(3%-5%)", "大跌(5%-9%)", "跌停(≤-9%)"]
    colors = ["#ff0000", "#ff6600", "#ff9900", "#ffcccc",
              "#ccffcc", "#99cc00", "#66aa00", "#009900"]

    for label, color in zip(labels, colors):
        count = dist.get(label, 0)
        pct = (count / total * 100) if total > 0 else 0
        bars += f"""
        <div class="bar-row">
            <span class="bar-label">{label}</span>
            <div class="bar-bg"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>
            <span class="bar-count">{count}家 ({pct:.1f}%)</span>
        </div>"""
    return bars


def _limit_reason_summary_html(summary):
    if not summary:
        return ""
    lb = summary.get("连板分布", {})
    ft = summary.get("封板时间分布", {})

    return f"""
    <div class="summary-grid" style="margin-bottom:16px;">
        <div>
            <strong style="color:#ff9a76;">连板分布</strong>
            <table class="small-table" style="margin-top:6px;">
                <tr><td>首板</td><td class="number">{lb.get('首板', 0)}</td></tr>
                <tr><td>2连板</td><td class="number">{lb.get('2连板', 0)}</td></tr>
                <tr><td>3-4连板</td><td class="number">{lb.get('3-4连板', 0)}</td></tr>
                <tr><td>5连板及以上</td><td class="number up">{lb.get('5连板及以上', 0)}</td></tr>
            </table>
        </div>
        <div>
            <strong style="color:#ff9a76;">封板时间分布</strong>
            <table class="small-table" style="margin-top:6px;">
                <tr><td>早盘秒板</td><td class="number up">{ft.get('早盘秒板', 0)}</td></tr>
                <tr><td>早盘封板</td><td class="number">{ft.get('早盘封板', 0)}</td></tr>
                <tr><td>其他</td><td class="number">{ft.get('其他', 0)}</td></tr>
            </table>
        </div>
    </div>"""


def _limit_all_html(details):
    rows = ""
    for s in details:
        reason = s.get("涨停原因", "-")
        # 判断归因类型加样式
        reason_cls = ""
        if "龙头" in reason:
            reason_cls = "leader"
        elif "秒板" in reason:
            reason_cls = "early"

        rows += f"""
        <tr>
            <td>{s.get('股票代码', '')}</td>
            <td>{s.get('股票名称', '')}</td>
            <td class="number up">{fmt_pct(s.get('涨跌幅(%)', 0))}</td>
            <td class="center">{s.get('连板数', '-')}</td>
            <td>{s.get('首次封板时间', '-')}</td>
            <td><span class="reason-tag {reason_cls}">{reason}</span></td>
            <td class="number">{s.get('封单金额', '-')}</td>
        </tr>"""
    return rows


def _hot20_html(stocks):
    rows = ""
    for i, s in enumerate(stocks):
        pct = s["涨跌幅(%)"]
        cls = pct_class(pct)
        arrow = pct_arrow(pct)
        rows += f"""
        <tr>
            <td class="center">{i+1}</td>
            <td>{s['股票代码']}</td>
            <td>{s['股票名称']}</td>
            <td class="number">{fmt_num(s['最新价'])}</td>
            <td class="number {cls}">{arrow} {fmt_pct(pct)}</td>
            <td class="number">{s['成交额(亿)']}亿</td>
            <td class="number">{s.get('换手率(%)', '-')}</td>
        </tr>"""
    return rows


# ============================================================
# Markdown 邮件报告
# ============================================================

def generate_markdown_report(data):
    """生成 Markdown 邮件内容"""
    today = data.get("日期", datetime.now().strftime("%Y-%m-%d"))
    indexes = data.get("大盘指数", [])
    sectors = data.get("行业板块", {})
    concepts = data.get("概念板块", {})
    breadth = data.get("市场宽度", {})
    hot_stocks = data.get("热门个股", {})
    limit_data = data.get("涨跌停统计", {})
    north = data.get("北向资金", {})
    sentiment = market_sentiment(data)
    amount_compare = breadth.get("成交额对比", {})

    md = f"""# 📊 A股每日复盘报告 - {today}

> 生成时间: {data.get('采集时间', '')} | 市场情绪: **{sentiment}**

---

## 📈 核心概览

| 指标 | 数值 |
|------|------|
| 上涨家数 | **{breadth.get('上涨家数', '-')}** |
| 下跌家数 | **{breadth.get('下跌家数', '-')}** |
| 平盘家数 | {breadth.get('平盘家数', '-')} |
| 总成交额 | **{breadth.get('总成交额(亿)', '-')} 亿** |
| 涨停家数 | **{limit_data.get('涨停数量', '-')}** |
| 跌停家数 | **{limit_data.get('跌停数量', '-')}** |
| 北向资金 | **{north.get('当日净流入(亿)', '-')} 亿** |
"""

    # 成交额对比
    if amount_compare.get("环比变化(%)") != "N/A":
        md += f"""| 成交额环比 | **{amount_compare['环比变化(%)']:+.2f}%** |
| 5日均成交额 | **{amount_compare['5日均成交额(亿)']} 亿** |
| 与5日均值比 | **{amount_compare['与5日均值比(%)']:+.2f}%** |
"""

    md += f"""
---

## 📊 大盘指数

| 指数 | 点位 | 涨跌幅 | 涨跌额 | 成交额 |
|------|------|--------|--------|--------|
"""
    for idx in indexes:
        pct = idx["涨跌幅(%)"]
        arrow = "🔴" if pct >= 0 else "🟢"
        md += f"| {idx['指数名称']} | {fmt_num(idx['当前点位'])} | {arrow} {fmt_pct(pct)} | {idx.get('涨跌额', '-')} | {idx.get('成交额(亿)', '-')}亿 |\n"

    md += f"""
---

## 🏭 行业板块 TOP10

| 排名 | 板块 | 涨跌幅 | 成交额 | 领涨股TOP3 |
|------|------|--------|--------|------------|
"""
    for i, s in enumerate(sectors.get("top10", [])):
        pct = s["涨跌幅(%)"]
        arrow = "🔴" if pct >= 0 else "🟢"
        top3 = s.get("领涨股TOP3", [])
        if top3:
            top3_str = " | ".join([f"{st['名称']}({st['涨跌幅(%)']:+.2f}%)" for st in top3])
        else:
            top3_str = s.get("领涨股", "-")
        md += f"| {i+1} | {s['板块名称']} | {arrow} {fmt_pct(pct)} | {s.get('成交额(亿)', '-')} | {top3_str} |\n"

    md += f"""
## 📉 行业板块 跌幅榜 TOP5

| 排名 | 板块 | 涨跌幅 | 成交额 |
|------|------|--------|--------|
"""
    for i, s in enumerate(sectors.get("bottom5", [])):
        pct = s["涨跌幅(%)"]
        arrow = "🔴" if pct >= 0 else "🟢"
        md += f"| {i+1} | {s['板块名称']} | {arrow} {fmt_pct(pct)} | {s.get('成交额(亿)', '-')} |\n"

    md += f"""
---

## 💡 概念板块 TOP10

| 概念 | 涨跌幅 | 涨停个数 | 涨超5%个数 |
|------|--------|----------|------------|
"""
    for s in concepts.get("top10", []):
        pct = s["涨跌幅(%)"]
        arrow = "🔴" if pct >= 0 else "🟢"
        md += f"| {s['概念名称']} | {arrow} {fmt_pct(pct)} | {s.get('涨停个数', 0)} | {s.get('涨超5%个数', 0)} |\n"

    if concepts.get("bottom5"):
        md += f"\n**📉 跌幅前5:** " + " | ".join([f"{c['概念名称']}({c['涨跌幅(%)']:+.2f}%)" for c in concepts["bottom5"]])

    md += f"""
---

## 🔥 成交额 TOP20（占全市场 {hot_stocks.get('top20占比(%)', 0)}%）

| 排名 | 代码 | 名称 | 价格 | 涨跌幅 | 成交额 | 换手率 |
|------|------|------|------|--------|--------|--------|
"""
    for i, s in enumerate(hot_stocks.get("top20", [])):
        pct = s["涨跌幅(%)"]
        arrow = "🔴" if pct >= 0 else "🟢"
        md += f"| {i+1} | {s['股票代码']} | {s['股票名称']} | {fmt_num(s['最新价'])} | {arrow} {fmt_pct(pct)} | {s['成交额(亿)']}亿 | {s.get('换手率(%)', '-')} |\n"

    md += f"""
---

## 🚀 涨停板全量分析（{limit_data.get('涨停数量', 0)}只）

### 归因汇总
| 连板分布 | 数量 | | 封板时间 | 数量 |
|----------|------|---|----------|------|
"""
    summary = limit_data.get("涨停归因汇总", {})
    lb = summary.get("连板分布", {})
    ft = summary.get("封板时间分布", {})
    md += f"| 首板 | {lb.get('首板', 0)} | | 早盘秒板 | {ft.get('早盘秒板', 0)} |\n"
    md += f"| 2连板 | {lb.get('2连板', 0)} | | 早盘封板 | {ft.get('早盘封板', 0)} |\n"
    md += f"| 3-4连板 | {lb.get('3-4连板', 0)} | | 其他 | {ft.get('其他', 0)} |\n"
    md += f"| 5连板及以上 | {lb.get('5连板及以上', 0)} | | | |\n"

    md += f"""
### 涨停明细

| 代码 | 名称 | 涨幅 | 连板 | 封板时间 | 涨停原因 | 封单 |
|------|------|------|------|----------|----------|------|
"""
    for s in limit_data.get("涨停明细", []):
        md += f"| {s.get('股票代码', '')} | {s.get('股票名称', '')} | {fmt_pct(s.get('涨跌幅(%)', 0))} | {s.get('连板数', '-')} | {s.get('首次封板时间', '-')} | {s.get('涨停原因', '-')} | {s.get('封单金额', '-')} |\n"

    if not limit_data.get("涨停明细"):
        md += "| - | 今日无涨停数据 | - | - | - | - | - |\n"

    md += f"""
---

> ⚠️ 本报告由自动化程序生成，仅供参考，不构成投资建议。
> Generated by A-Stock Daily Review Bot v2.0 | {today}
"""

    # 保存 MD
    md_path = os.path.join(OUTPUT_DIR, "report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"✅ Markdown 报告已生成: {md_path}")
    return md


if __name__ == "__main__":
    data = load_data()
    if data:
        generate_html_report(data)
        generate_markdown_report(data)
        print("\n🎉 报告生成完毕!")
    else:
        print("请先运行 fetch_data.py 获取数据")

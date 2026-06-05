#!/usr/bin/env python3
"""
A股每日复盘 - 报告生成模块
基于采集的数据生成 HTML 网页报告 + Markdown 邮件内容
"""

import json
import os
from datetime import datetime
from string import Template

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "docs")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


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


def color_pct(value):
    """根据涨跌返回颜色标签"""
    if isinstance(value, str):
        return value
    if value > 0:
        return f'<span class="up">{value:+.2f}%</span>'
    elif value < 0:
        return f'<span class="down">{value:+.2f}%</span>'
    else:
        return f'<span class="flat">{value:.2f}%</span>'


def color_pct_md(value):
    """Markdown 版本的涨跌颜色"""
    if isinstance(value, str):
        return value
    if value > 0:
        return f"🔴 {value:+.2f}%"
    elif value < 0:
        return f"🟢 {value:+.2f}%"
    else:
        return f"⚪ {value:.2f}%"


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


def generate_index_table_html(indexes):
    """生成大盘指数 HTML 表格"""
    rows = ""
    for idx in indexes:
        pct = idx["涨跌幅(%)"]
        if pct >= 0:
            direction_class = "up"
            arrow = "▲"
        else:
            direction_class = "down"
            arrow = "▼"
        
        rows += f"""
        <tr>
            <td>{idx['指数名称']}</td>
            <td class="number">{idx['当前点位']}</td>
            <td class="number {direction_class}">{arrow} {pct:+.2f}%</td>
            <td class="number">{idx.get('涨跌额', '-')}</td>
            <td class="number">{idx.get('成交额(亿)', '-')}亿</td>
        </tr>"""
    
    return rows


def generate_industry_html(sectors):
    """生成行业板块 HTML"""
    top_rows = ""
    for s in sectors.get("top10", []):
        pct = s["涨跌幅(%)"]
        cls = "up" if pct >= 0 else "down"
        arrow = "▲" if pct >= 0 else "▼"
        top_rows += f"""
        <tr>
            <td>{s['板块名称']}</td>
            <td class="number {cls}">{arrow} {pct:+.2f}%</td>
            <td>{s.get('领涨股', '-')}</td>
        </tr>"""
    
    bottom_rows = ""
    for s in sectors.get("bottom10", []):
        pct = s["涨跌幅(%)"]
        cls = "up" if pct >= 0 else "down"
        arrow = "▲" if pct >= 0 else "▼"
        bottom_rows += f"""
        <tr>
            <td>{s['板块名称']}</td>
            <td class="number {cls}">{arrow} {pct:+.2f}%</td>
            <td>{s.get('领涨股', '-')}</td>
        </tr>"""
    
    return top_rows, bottom_rows


def generate_concept_html(concepts):
    """生成概念板块 HTML"""
    top_rows = ""
    for c in concepts.get("top5", []):
        top_rows += f'<span class="tag up">🔥 {c["概念名称"]} {c["涨跌幅(%)"]:+.2f}%</span>'
    
    bottom_rows = ""
    for c in concepts.get("bottom5", []):
        bottom_rows += f'<span class="tag down">❄️ {c["概念名称"]} {c["涨跌幅(%)"]:+.2f}%</span>'
    
    return top_rows, bottom_rows


def generate_breadth_html(breadth):
    """生成市场宽度 HTML"""
    dist = breadth.get("涨幅分布", {})
    total = sum(dist.values())
    
    if total == 0:
        return ""
    
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
            <div class="bar-bg">
                <div class="bar-fill" style="width:{pct}%;background:{color}"></div>
            </div>
            <span class="bar-count">{count}家 ({pct:.1f}%)</span>
        </div>"""
    
    return bars


def generate_hot_stocks_html(stocks):
    """生成热门个股 HTML"""
    rows = ""
    for s in stocks:
        pct = s["涨跌幅(%)"]
        cls = "up" if pct >= 0 else "down"
        arrow = "▲" if pct >= 0 else "▼"
        rows += f"""
        <tr>
            <td>{s['股票代码']}</td>
            <td>{s['股票名称']}</td>
            <td class="number">{s['最新价']}</td>
            <td class="number {cls}">{arrow} {pct:+.2f}%</td>
            <td class="number">{s['成交额(亿)']}亿</td>
        </tr>"""
    return rows


def generate_limit_up_html(limit_data):
    """生成涨停明细 HTML"""
    rows = ""
    for s in limit_data.get("涨停明细", []):
        rows += f"""
        <tr>
            <td>{s.get('股票代码', '')}</td>
            <td>{s.get('股票名称', '')}</td>
            <td>{s.get('连板数', '-')}</td>
            <td>{s.get('封单金额', '-')}</td>
        </tr>"""
    return rows


def generate_html_report(data):
    """生成完整 HTML 报告"""
    today = data.get("日期", datetime.now().strftime("%Y-%m-%d"))
    
    indexes = data.get("大盘指数", [])
    sectors = data.get("行业板块", {})
    concepts = data.get("概念板块", {})
    breadth = data.get("市场宽度", {})
    hot_stocks = data.get("热门个股", [])
    limit_data = data.get("涨跌停统计", {})
    north = data.get("北向资金", {})
    sentiment = market_sentiment(data)
    
    index_rows = generate_index_table_html(indexes)
    industry_top, industry_bottom = generate_industry_html(sectors)
    concept_top, concept_bottom = generate_concept_html(concepts)
    breadth_bars = generate_breadth_html(breadth)
    hot_rows = generate_hot_stocks_html(hot_stocks)
    limit_rows = generate_limit_up_html(limit_data)
    
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
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            padding: 40px 20px;
            background: linear-gradient(135deg, #e94560, #0f3460);
            border-radius: 16px;
            margin-bottom: 24px;
        }}
        .header h1 {{
            font-size: 2.2em;
            color: #fff;
            margin-bottom: 8px;
        }}
        .header .date {{
            font-size: 1.1em;
            color: rgba(255,255,255,0.8);
        }}
        .header .sentiment {{
            display: inline-block;
            margin-top: 12px;
            padding: 8px 24px;
            background: rgba(255,255,255,0.15);
            border-radius: 20px;
            font-size: 1.3em;
            color: #fff;
        }}
        .card {{
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
        }}
        .card h2 {{
            font-size: 1.3em;
            color: #e94560;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid rgba(233,69,96,0.3);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95em;
        }}
        th {{
            background: rgba(233,69,96,0.2);
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            color: #e94560;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }}
        tr:hover {{
            background: rgba(255,255,255,0.04);
        }}
        .number {{ text-align: right; font-variant-numeric: tabular-nums; }}
        .up {{ color: #ff4d4d; font-weight: 600; }}
        .down {{ color: #4dff4d; font-weight: 600; }}
        .flat {{ color: #888; }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        @media (max-width: 768px) {{
            .grid-2 {{ grid-template-columns: 1fr; }}
        }}
        .stats {{
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .stat-item {{
            text-align: center;
            padding: 16px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            min-width: 120px;
        }}
        .stat-value {{
            font-size: 1.8em;
            font-weight: 700;
        }}
        .stat-label {{
            font-size: 0.85em;
            color: #888;
            margin-top: 4px;
        }}
        .tag {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 14px;
            margin: 4px;
            font-size: 0.9em;
        }}
        .tag.up {{ background: rgba(255,77,77,0.2); }}
        .tag.down {{ background: rgba(77,255,77,0.2); }}
        .bar-row {{
            display: flex;
            align-items: center;
            margin: 6px 0;
            gap: 12px;
        }}
        .bar-label {{
            width: 100px;
            font-size: 0.85em;
            color: #aaa;
            text-align: right;
        }}
        .bar-bg {{
            flex: 1;
            height: 18px;
            background: rgba(255,255,255,0.08);
            border-radius: 9px;
            overflow: hidden;
        }}
        .bar-fill {{
            height: 100%;
            border-radius: 9px;
            transition: width 0.5s ease;
        }}
        .bar-count {{
            width: 120px;
            font-size: 0.85em;
            color: #ccc;
        }}
        .footer {{
            text-align: center;
            padding: 24px;
            color: #666;
            font-size: 0.85em;
        }}
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

        <!-- 核心统计 -->
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

        <!-- 大盘指数 -->
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
                <tbody>{index_rows}</tbody>
            </table>
        </div>

        <!-- 行业板块 + 概念板块 -->
        <div class="grid-2">
            <div class="card">
                <h2>🏭 行业板块 TOP10</h2>
                <table>
                    <thead><tr><th>板块</th><th class="number">涨跌幅</th><th>领涨股</th></tr></thead>
                    <tbody>{industry_top}</tbody>
                </table>
            </div>
            <div class="card">
                <h2>📉 行业板块 跌幅榜</h2>
                <table>
                    <thead><tr><th>板块</th><th class="number">涨跌幅</th><th>领跌股</th></tr></thead>
                    <tbody>{industry_bottom}</tbody>
                </table>
            </div>
        </div>

        <!-- 概念板块 -->
        <div class="card">
            <h2>💡 概念板块热度</h2>
            <div style="margin-bottom:12px;"><strong>🔥 涨幅前5:</strong><br>{concept_top}</div>
            <div><strong>❄️ 跌幅前5:</strong><br>{concept_bottom}</div>
        </div>

        <!-- 市场宽度 -->
        <div class="card">
            <h2>📊 市场宽度分布</h2>
            {breadth_bars}
        </div>

        <!-- 涨停明细 + 热门个股 -->
        <div class="grid-2">
            <div class="card">
                <h2>🚀 涨停板明细</h2>
                <table>
                    <thead><tr><th>代码</th><th>名称</th><th>连板</th><th>封单</th></tr></thead>
                    <tbody>{limit_rows}</tbody>
                </table>
                {'' if limit_rows else '<p style="color:#888;">今日无涨停数据或非交易日</p>'}
            </div>
            <div class="card">
                <h2>🔥 成交额 TOP10</h2>
                <table>
                    <thead><tr><th>代码</th><th>名称</th><th class="number">价格</th><th class="number">涨跌幅</th><th class="number">成交额</th></tr></thead>
                    <tbody>{hot_rows}</tbody>
                </table>
            </div>
        </div>

        <!-- 页脚 -->
        <div class="footer">
            <p>⚠️ 本报告由自动化程序生成，仅供参考，不构成投资建议。</p>
            <p>Generated by A-Stock Daily Review Bot | {today}</p>
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


def generate_markdown_report(data):
    """生成 Markdown 邮件内容"""
    today = data.get("日期", datetime.now().strftime("%Y-%m-%d"))
    indexes = data.get("大盘指数", [])
    sectors = data.get("行业板块", {})
    concepts = data.get("概念板块", {})
    breadth = data.get("市场宽度", {})
    hot_stocks = data.get("热门个股", [])
    limit_data = data.get("涨跌停统计", {})
    north = data.get("北向资金", {})
    sentiment = market_sentiment(data)
    
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

---

## 📊 大盘指数

| 指数 | 点位 | 涨跌幅 | 涨跌额 | 成交额 |
|------|------|--------|--------|--------|
"""
    
    for idx in indexes:
        pct = idx["涨跌幅(%)"]
        arrow = "🔴" if pct >= 0 else "🟢"
        md += f"| {idx['指数名称']} | {idx['当前点位']} | {arrow} {pct:+.2f}% | {idx.get('涨跌额', '-')} | {idx.get('成交额(亿)', '-')}亿 |\n"
    
    md += f"""
---

## 🏭 行业板块 TOP10

| 板块 | 涨跌幅 | 领涨股 |
|------|--------|--------|
"""
    for s in sectors.get("top10", []):
        pct = s["涨跌幅(%)"]
        arrow = "🔴" if pct >= 0 else "🟢"
        md += f"| {s['板块名称']} | {arrow} {pct:+.2f}% | {s.get('领涨股', '-')} |\n"
    
    md += f"""
## 📉 行业板块 跌幅榜

| 板块 | 涨跌幅 | 领跌股 |
|------|--------|--------|
"""
    for s in sectors.get("bottom10", []):
        pct = s["涨跌幅(%)"]
        arrow = "🔴" if pct >= 0 else "🟢"
        md += f"| {s['板块名称']} | {arrow} {pct:+.2f}% | {s.get('领涨股', '-')} |\n"
    
    md += f"""
---

## 💡 概念板块热度

**🔥 涨幅前5:** {" ｜ ".join([f"{c['概念名称']}({c['涨跌幅(%)']:+.2f}%)" for c in concepts.get('top5', [])])}

**❄️ 跌幅前5:** {" ｜ ".join([f"{c['概念名称']}({c['涨跌幅(%)']:+.2f}%)" for c in concepts.get('bottom5', [])])}

---

## 🔥 成交额 TOP10

| 代码 | 名称 | 价格 | 涨跌幅 | 成交额 |
|------|------|------|--------|--------|
"""
    for s in hot_stocks:
        pct = s["涨跌幅(%)"]
        arrow = "🔴" if pct >= 0 else "🟢"
        md += f"| {s['股票代码']} | {s['股票名称']} | {s['最新价']} | {arrow} {pct:+.2f}% | {s['成交额(亿)']}亿 |\n"
    
    md += f"""
---

## 🚀 涨停板明细

| 代码 | 名称 | 连板 | 封单 |
|------|------|------|------|
"""
    for s in limit_data.get("涨停明细", []):
        md += f"| {s.get('股票代码', '')} | {s.get('股票名称', '')} | {s.get('连板数', '-')} | {s.get('封单金额', '-')} |\n"
    
    if not limit_data.get("涨停明细"):
        md += "| - | 今日无涨停数据 | - | - |\n"
    
    md += f"""
---

> ⚠️ 本报告由自动化程序生成，仅供参考，不构成投资建议。
> Generated by A-Stock Daily Review Bot | {today}
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

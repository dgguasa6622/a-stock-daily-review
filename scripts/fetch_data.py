#!/usr/bin/env python3
"""
A股每日复盘 - 数据获取模块 v3.1
数据源策略：
- 主力：akshare 新浪数据源（GitHub Actions 可用，不受东方财富 IP 封禁）
  - stock_zh_a_spot() → 全市场行情（新浪源）
  - stock_zh_index_spot_em() → 大盘指数（东方财富，可能不可用）
- 备用：新浪财经 hq.sinajs.cn 直连
- 涨停板：akshare stock_zt_pool_em()（已验证在 Actions 中可用）
- 涨停原因：智能归因引擎（行业/概念/连板/封板时间多维度）
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from data_sources import (
    sina_index_spot, em_index_daily, em_limit_up_detail,
    em_limit_up_detail_strong, analyze_limit_up_reason,
    em_industry_boards, em_concept_boards, em_board_stocks
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")

# 全局缓存
_spot_cache = None
_industry_cache = None
_concept_cache = None


def _get_spot_sina():
    """全市场A股行情 - 新浪数据源（Actions 可用）"""
    global _spot_cache
    if _spot_cache is not None:
        return _spot_cache

    print("📡 获取全市场A股行情（新浪数据源）...")
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot()
        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "代码": str(row.get("代码", "")),
                    "名称": str(row.get("名称", "")),
                    "最新价": float(row.get("最新价", 0) or 0),
                    "涨跌额": float(row.get("涨跌额", 0) or 0),
                    "涨跌幅": float(row.get("涨跌幅", 0) or 0),
                    "昨收": float(row.get("昨收", 0) or 0),
                    "成交量": float(row.get("成交量", 0) or 0),
                    "成交额": float(row.get("成交额", 0) or 0) / 1e8,  # 新浪数据源单位是「元」，转为「亿元」
                    "换手率": float(row.get("换手率", 0) or 0),
                    "流通市值": float(row.get("流通市值", 0) or 0),
                })
            _spot_cache = records
            print(f"  ✅ 全市场行情: {len(records)} 只")
            return records
    except Exception as e:
        print(f"  ⚠️ 新浪全市场行情失败: {e}")

    _spot_cache = []
    return _spot_cache


def _get_industry_from_em():
    """行业板块 - 东方财富 push2"""
    global _industry_cache
    if _industry_cache is not None:
        return _industry_cache
    _industry_cache = em_industry_boards()
    if _industry_cache is None:
        _industry_cache = []
    return _industry_cache


def _get_concept_from_em():
    """概念板块 - 东方财富 push2"""
    global _concept_cache
    if _concept_cache is not None:
        return _concept_cache
    _concept_cache = em_concept_boards()
    if _concept_cache is None:
        _concept_cache = []
    return _concept_cache


# ============================================================
# 大盘指数
# ============================================================

def get_market_index():
    """获取8个大盘指数（东方财富优先，新浪备用）"""
    print("📊 获取大盘指数...")

    # 先试东方财富
    try:
        import akshare as ak
        df = ak.stock_zh_index_spot_em()
        if df is not None and not df.empty:
            targets = ["上证指数", "深证成指", "创业板指", "科创50",
                       "沪深300", "中证500", "中证1000", "中证2000"]
            result = df[df["名称"].isin(targets)].copy()
            if len(result) >= 4:
                records = []
                for _, row in result.iterrows():
                    records.append({
                        "指数名称": row["名称"],
                        "当前点位": round(float(row["最新价"]), 2),
                        "涨跌幅(%)": round(float(row["涨跌幅"]), 2),
                        "涨跌额": round(float(row["涨跌额"]), 2),
                        "成交额(亿)": round(float(row["成交额"]) / 1e8, 2) if row.get("成交额") else 0,
                    })
                # 排序
                order = {v: i for i, v in enumerate(targets)}
                records.sort(key=lambda x: order.get(x["指数名称"], 99))
                print(f"  ✅ 大盘指数(东财): {len(records)} 个")
                return records
    except Exception as e:
        print(f"  ⚠️ 东方财富指数失败: {e}")

    # 备用：新浪财经
    result = sina_index_spot()
    if result:
        print(f"  ✅ 大盘指数(新浪): {len(result)} 个")
        return result

    print("  ❌ 大盘指数获取失败")
    return []


# ============================================================
# 历史成交额对比
# ============================================================

def get_historical_amount():
    """成交额环比和5日均值"""
    print("📅 获取历史成交额对比...")
    
    # 方案1: 东方财富 push2his K线接口（和 push2 不同域名，Actions 中可能可用）
    amounts = em_index_daily("1.000001", days=6)
    if amounts and len(amounts) >= 2:
        today_amt = amounts[-1]
        prev_amt = amounts[-2]
        prev_5 = amounts[-6:-1] if len(amounts) >= 6 else amounts[:-1]
        avg_5d = sum(prev_5) / len(prev_5) if prev_5 else today_amt
        prev_change = ((today_amt - prev_amt) / prev_amt * 100) if prev_amt > 0 else 0
        vs_5d = ((today_amt - avg_5d) / avg_5d * 100) if avg_5d > 0 else 0
        print(f"  ✅ 环比: {prev_change:+.2f}%, 5日均: {avg_5d:.1f}亿")
        return {
            "前一交易日成交额(亿)": round(prev_amt, 2),
            "环比变化(%)": round(prev_change, 2),
            "5日均成交额(亿)": round(avg_5d, 2),
            "与5日均值比(%)": round(vs_5d, 2)
        }
    
    # 方案2: akshare 东方财富日K（备用）
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily_em(symbol="sh000001")
        if df is not None and not df.empty and "amount" in df.columns:
            df = df.tail(6)
            amounts = (df["amount"] / 1e8).tolist()
            if len(amounts) >= 2:
                today_amt = amounts[-1]
                prev_amt = amounts[-2]
                prev_5 = amounts[-6:-1] if len(amounts) >= 6 else amounts[:-1]
                avg_5d = sum(prev_5) / len(prev_5) if prev_5 else today_amt
                prev_change = ((today_amt - prev_amt) / prev_amt * 100) if prev_amt > 0 else 0
                vs_5d = ((today_amt - avg_5d) / avg_5d * 100) if avg_5d > 0 else 0
                print(f"  ✅ 环比: {prev_change:+.2f}%, 5日均: {avg_5d:.1f}亿")
                return {
                    "前一交易日成交额(亿)": round(prev_amt, 2),
                    "环比变化(%)": round(prev_change, 2),
                    "5日均成交额(亿)": round(avg_5d, 2),
                    "与5日均值比(%)": round(vs_5d, 2)
                }
    except Exception as e:
        pass
    
    print("  ⚠️ 历史成交额获取失败")
    return {
        "前一交易日成交额(亿)": "N/A", "环比变化(%)": "N/A",
        "5日均成交额(亿)": "N/A", "与5日均值比(%)": "N/A"
    }


# ============================================================
# 行业板块
# ============================================================

def get_industry_sectors():
    """行业板块 + 领涨股TOP3"""
    print("🏭 获取行业板块...")
    industries = _get_industry_from_em()

    if not industries:
        print("  ⚠️ 行业板块数据为空")
        return {"all": [], "top10": [], "bottom5": []}

    # top10 + 领涨股TOP3
    top10 = industries[:10]
    print(f"  获取领涨股TOP3（{len(top10)}个板块）...")
    for sector in top10:
        code = sector.get("板块代码", "")
        if code:
            stocks = em_board_stocks(code, "industry")
            if stocks:
                sorted_s = sorted(stocks, key=lambda x: x["涨跌幅(%)"], reverse=True)
                sector["领涨股TOP3"] = [
                    {"名称": s["名称"], "代码": s["代码"], "涨跌幅(%)": round(s["涨跌幅(%)"], 2)}
                    for s in sorted_s[:3]
                ]
            else:
                sector["领涨股TOP3"] = []
        else:
            sector["领涨股TOP3"] = []
        sector["强势天数"] = "N/A"

    bottom5 = industries[-5:] if len(industries) >= 5 else []
    bottom5.reverse()

    return {"all": industries, "top10": top10, "bottom5": bottom5}


# ============================================================
# 概念板块
# ============================================================

def get_concept_sectors():
    """概念板块 + 涨停/涨超5%统计"""
    print("💡 获取概念板块...")
    concepts = _get_concept_from_em()

    if not concepts:
        print("  ⚠️ 概念板块数据为空")
        return {"top10": [], "bottom5": []}

    top10_raw = concepts[:10]
    bottom5 = concepts[-5:] if len(concepts) >= 5 else []
    bottom5.reverse()

    print(f"  统计概念板块成分股（{len(top10_raw)}个）...")
    top10 = []
    for concept in top10_raw:
        code = concept.get("概念代码", "")
        limit_up_count = 0
        up5_count = 0
        if code:
            stocks = em_board_stocks(code, "concept")
            if stocks:
                limit_up_count = sum(1 for s in stocks if s["涨跌幅(%)"] >= 9.9)
                up5_count = sum(1 for s in stocks if s["涨跌幅(%)"] >= 5)

        concept["涨停个数"] = limit_up_count
        concept["涨超5%个数"] = up5_count
        top10.append(concept)

    return {"top10": top10, "bottom5": bottom5}


# ============================================================
# 涨停板全量 + 智能归因
# ============================================================

def get_limit_up_down():
    """涨停板全量 + 智能归因"""
    print("📈 获取涨停板数据...")
    today_str = datetime.now().strftime("%Y%m%d")

    # 获取涨停池
    df_up = em_limit_up_detail(today_str)
    limit_up_count = len(df_up) if df_up is not None and not (hasattr(df_up, 'empty') and df_up.empty) else 0

    # 获取行业和概念排名
    industries = _get_industry_from_em()
    concepts = _get_concept_from_em()

    industry_ranking = {}
    for i, ind in enumerate(industries):
        industry_ranking[ind["板块名称"]] = {"rank": i + 1, "pct": ind["涨跌幅(%)"]}

    concept_ranking = {}
    for i, con in enumerate(concepts):
        concept_ranking[con["概念名称"]] = {"rank": i + 1, "pct": con["涨跌幅(%)"]}

    board_stock_map = {}

    # 处理涨停明细
    limit_up_details = []
    if df_up is not None and not (hasattr(df_up, 'empty') and df_up.empty):
        for _, row in df_up.iterrows():
            stock_code = str(row.get("代码", ""))
            stock_name = str(row.get("名称", ""))

            stock_info = {
                "代码": stock_code,
                "名称": stock_name,
                "连板数": row.get("连板数", 0),
                "首次封板时间": str(row.get("首次封板时间", "-")),
                "封单金额": str(row.get("封单金额", row.get("封板资金", ""))),
                "成交额(亿)": round(float(row.get("成交额", 0)) / 1e8, 2) if row.get("成交额") else "N/A",
            }
            reason = analyze_limit_up_reason(stock_info, industry_ranking, concept_ranking, board_stock_map)

            limit_up_details.append({
                "股票代码": stock_code,
                "股票名称": stock_name,
                "最新价": row.get("最新价", ""),
                "涨跌幅(%)": round(float(row.get("涨跌幅", 0)), 2),
                "封单金额": str(row.get("封单金额", row.get("封板资金", ""))),
                "连板数": str(row.get("连板数", "-")),
                "首次封板时间": str(row.get("首次封板时间", "-")),
                "成交额(亿)": round(float(row.get("成交额", 0)) / 1e8, 2) if row.get("成交额") else "N/A",
                "换手率(%)": round(float(row.get("换手率", 0)), 2) if row.get("换手率") else "N/A",
                "涨停原因": reason["summary"],
                "归因详情": reason["details"]
            })

    # 归因汇总
    reason_summary = _summarize_reasons(limit_up_details)

    # 跌停数量
    limit_down_count = 0
    spot = _get_spot_sina()
    if spot:
        limit_down_count = sum(1 for s in spot if s["涨跌幅"] <= -9.9)

    return {
        "涨停数量": limit_up_count,
        "跌停数量": limit_down_count,
        "涨停明细": limit_up_details,
        "涨停归因汇总": reason_summary
    }


def _summarize_reasons(details):
    """涨停归因汇总"""
    lb_count = {"首板": 0, "2连板": 0, "3-4连板": 0, "5连板及以上": 0}
    time_count = {"早盘秒板": 0, "早盘封板": 0, "其他": 0}
    board_count = {}
    concept_count = {}

    for stock in details:
        reason = stock.get("涨停原因", "")
        detail = stock.get("归因详情", {})
        lb_val = stock.get("连板数", "0")
        try:
            lb_val = int(lb_val)
        except (ValueError, TypeError):
            lb_val = 0

        if lb_val >= 5:
            lb_count["5连板及以上"] += 1
        elif lb_val >= 3:
            lb_count["3-4连板"] += 1
        elif lb_val >= 2:
            lb_count["2连板"] += 1
        else:
            lb_count["首板"] += 1

        if "秒板" in reason:
            time_count["早盘秒板"] += 1
        elif "早盘" in reason:
            time_count["早盘封板"] += 1
        else:
            time_count["其他"] += 1

        ind_attr = detail.get("行业归因", "")
        if ind_attr:
            ind_name = ind_attr.split("(")[0] if "(" in ind_attr else ind_attr
            board_count[ind_name] = board_count.get(ind_name, 0) + 1

        con_attr = detail.get("概念归因", "")
        if con_attr:
            con_name = con_attr.split("(")[0] if "(" in con_attr else con_attr
            concept_count[con_name] = concept_count.get(con_name, 0) + 1

    top_boards = sorted(board_count.items(), key=lambda x: x[1], reverse=True)[:10]
    top_concepts = sorted(concept_count.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "连板分布": lb_count,
        "封板时间分布": time_count,
        "涨停行业分布": dict(top_boards),
        "涨停概念分布": dict(top_concepts),
    }


# ============================================================
# 市场宽度
# ============================================================

def get_market_breadth():
    """市场宽度"""
    print("📉 获取市场宽度...")
    spot = _get_spot_sina()

    if not spot:
        return {
            "上涨家数": 0, "下跌家数": 0, "平盘家数": 0,
            "总成交额(亿)": 0,
            "成交额对比": {"前一交易日成交额(亿)": "N/A", "环比变化(%)": "N/A",
                        "5日均成交额(亿)": "N/A", "与5日均值比(%)": "N/A"},
            "涨幅分布": {}
        }

    up = sum(1 for s in spot if s["涨跌幅"] > 0)
    down = sum(1 for s in spot if s["涨跌幅"] < 0)
    flat = len(spot) - up - down

    surge_9 = sum(1 for s in spot if s["涨跌幅"] >= 9)
    surge_5_9 = sum(1 for s in spot if 5 <= s["涨跌幅"] < 9)
    surge_3_5 = sum(1 for s in spot if 3 <= s["涨跌幅"] < 5)
    up_0_3 = sum(1 for s in spot if 0 < s["涨跌幅"] < 3)
    down_0_3 = sum(1 for s in spot if -3 < s["涨跌幅"] <= 0)
    down_3_5 = sum(1 for s in spot if -5 < s["涨跌幅"] <= -3)
    down_5_9 = sum(1 for s in spot if -9 < s["涨跌幅"] <= -5)
    plunge_9 = sum(1 for s in spot if s["涨跌幅"] <= -9)

    total_amount = sum(s["成交额"] for s in spot)  # 已在缓存层转为亿元
    amount_compare = get_historical_amount()

    return {
        "上涨家数": up, "下跌家数": down, "平盘家数": flat,
        "总成交额(亿)": round(total_amount, 2),
        "成交额对比": amount_compare,
        "涨幅分布": {
            "涨停(≥9%)": surge_9, "大涨(5%-9%)": surge_5_9,
            "中涨(3%-5%)": surge_3_5, "小涨(0-3%)": up_0_3,
            "小跌(0-3%)": down_0_3, "中跌(3%-5%)": down_3_5,
            "大跌(5%-9%)": down_5_9, "跌停(≤-9%)": plunge_9
        }
    }


# ============================================================
# 北向资金
# ============================================================

def get_north_flow():
    """北向资金"""
    print("💰 获取北向资金...")
    try:
        import akshare as ak
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            return {
                "日期": str(latest.get("date", "")),
                "当日净流入(亿)": round(float(latest.get("value", 0)), 2)
            }
    except Exception as e:
        print(f"  ⚠️ 北向资金失败: {e}")

    return {"日期": "", "当日净流入(亿)": "N/A"}


# ============================================================
# 成交额 TOP20
# ============================================================

def get_leading_stocks():
    """成交额 TOP20"""
    print("🔥 获取热门个股 TOP20...")
    spot = _get_spot_sina()

    if not spot:
        return {"top20": [], "top20成交额合计(亿)": 0, "top20占比(%)": 0}

    total_amount = sum(s["成交额"] for s in spot)
    sorted_stocks = sorted(spot, key=lambda x: x["成交额"], reverse=True)
    top20 = sorted_stocks[:20]
    top20_amount = sum(s["成交额"] for s in top20)

    result = []
    for s in top20:
        result.append({
            "股票代码": s["代码"],
            "股票名称": s["名称"],
            "最新价": round(s["最新价"], 2),
            "涨跌幅(%)": round(s["涨跌幅"], 2),
            "成交额(亿)": round(s["成交额"], 2),
            "换手率(%)": round(s.get("换手率", 0), 2) if s.get("换手率") else "N/A",
        })

    return {
        "top20": result,
        "top20成交额合计(亿)": round(top20_amount, 2),
        "top20占比(%)": round(top20_amount / total_amount * 100, 2) if total_amount > 0 else 0
    }


# ============================================================
# 主入口
# ============================================================

def collect_all_data():
    """收集所有复盘数据"""
    today = datetime.now().strftime("%Y-%m-%d")
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"  📊 A股每日复盘数据采集 v3.1 - {today}")
    print(f"  主力: 新浪数据源 + 东方财富涨停板")
    print(f"{'='*60}\n")

    # 并行预热缓存
    data = {
        "日期": today,
        "采集时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "大盘指数": get_market_index(),
        "行业板块": get_industry_sectors(),
        "概念板块": get_concept_sectors(),
        "涨跌停统计": get_limit_up_down(),
        "北向资金": get_north_flow(),
        "市场宽度": get_market_breadth(),
        "热门个股": get_leading_stocks()
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR, f"data_{today}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    latest_path = os.path.join(OUTPUT_DIR, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    elapsed = time.time() - start_time
    print(f"\n✅ 数据采集完成，耗时 {elapsed:.1f}s")
    return data


if __name__ == "__main__":
    data = collect_all_data()
    if data["大盘指数"]:
        print("\n📊 大盘指数:")
        for idx in data["大盘指数"][:4]:
            d = "📈" if idx["涨跌幅(%)"] >= 0 else "📉"
            print(f"  {d} {idx['指数名称']}: {idx['当前点位']} ({idx['涨跌幅(%)']:+.2f}%)")
    bw = data["市场宽度"]
    print(f"\n📉 涨: {bw['上涨家数']} / 跌: {bw['下跌家数']} | 成交额: {bw['总成交额(亿)']}亿")
    zt = data["涨跌停统计"]
    print(f"🚀 涨停: {zt['涨停数量']} | 跌停: {zt['跌停数量']}")
    hs = data["热门个股"]
    print(f"🔥 TOP20占比: {hs.get('top20占比(%)', 0)}%")

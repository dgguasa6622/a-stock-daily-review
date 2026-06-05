#!/usr/bin/env python3
"""
A股每日复盘 - 数据获取模块 v2.0
获取大盘指数、行业板块、概念板块、涨停统计、北向资金等核心数据
支持成交额历史对比、涨停归因分析、板块成分股统计等增强功能
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")

# 全局缓存：全市场个股数据，避免重复请求
_spot_df_cache = None


def _get_spot_df():
    """获取全市场A股实时行情（带缓存）"""
    global _spot_df_cache
    if _spot_df_cache is not None:
        return _spot_df_cache
    try:
        _spot_df_cache = ak.stock_zh_a_spot_em()
        return _spot_df_cache
    except Exception as e:
        print(f"⚠️ 获取全市场行情失败: {e}")
        return None


# ============================================================
# 需求 1 & 2：大盘指数（扩展版）+ 历史成交额
# ============================================================

def get_market_index():
    """
    获取主要大盘指数行情：
    上证指数、深证成指、创业板指、科创50、
    沪深300、中证500、中证1000、中证2000
    """
    print("📊 获取大盘指数数据...")
    try:
        df = ak.stock_zh_index_spot_em()
        target_codes = [
            "上证指数", "深证成指", "创业板指", "科创50",
            "沪深300", "中证500", "中证1000", "中证2000"
        ]

        result = df[df["名称"].isin(target_codes)].copy()

        columns_map = {
            "名称": "指数名称",
            "最新价": "当前点位",
            "涨跌额": "涨跌额",
            "涨跌幅": "涨跌幅(%)",
            "成交量": "成交量(手)",
            "成交额": "成交额(亿)"
        }

        result = result[list(columns_map.keys())].rename(columns=columns_map)
        result["涨跌幅(%)"] = result["涨跌幅(%)"].round(2)
        result["当前点位"] = result["当前点位"].round(2)
        result["成交额(亿)"] = (result["成交额(亿)"] / 1e8).round(2)

        # 保持目标顺序
        result["_order"] = result["指数名称"].apply(lambda x: target_codes.index(x) if x in target_codes else 99)
        result = result.sort_values("_order").drop(columns=["_order"])

        return result.to_dict(orient="records")
    except Exception as e:
        print(f"⚠️ 获取大盘指数失败: {e}")
        return []


def get_historical_amount():
    """
    需求1：获取历史成交额对比数据
    通过上证指数日K获取近6个交易日成交额，计算：
    - 前一交易日成交额及环比
    - 5日均成交额及对比
    """
    print("📅 获取历史成交额数据...")
    try:
        df = ak.stock_zh_index_daily_em(symbol="sh000001")
        if df is None or df.empty:
            return {"前一交易日成交额(亿)": "N/A", "环比变化(%)": "N/A",
                    "5日均成交额(亿)": "N/A", "与5日均值比(%)": "N/A"}

        df = df.tail(6)  # 取最近6个交易日（今天+前5天）
        if len(df) < 2:
            return {"前一交易日成交额(亿)": "N/A", "环比变化(%)": "N/A",
                    "5日均成交额(亿)": "N/A", "与5日均值比(%)": "N/A"}

        amounts = df["amount"].values / 1e8  # 转为亿

        # 最后一个可能是今天（如果盘中），倒数第二个是前一交易日
        today_amt = amounts[-1]
        prev_amt = amounts[-2] if len(amounts) >= 2 else today_amt

        # 前5个交易日（不含今天）
        prev_5 = amounts[-6:-1] if len(amounts) >= 6 else amounts[:-1]
        avg_5d = prev_5.mean() if len(prev_5) > 0 else today_amt

        prev_change = ((today_amt - prev_amt) / prev_amt * 100) if prev_amt > 0 else 0
        vs_5d = ((today_amt - avg_5d) / avg_5d * 100) if avg_5d > 0 else 0

        return {
            "前一交易日成交额(亿)": round(prev_amt, 2),
            "环比变化(%)": round(prev_change, 2),
            "5日均成交额(亿)": round(avg_5d, 2),
            "与5日均值比(%)": round(vs_5d, 2)
        }
    except Exception as e:
        print(f"⚠️ 获取历史成交额失败: {e}")
        return {"前一交易日成交额(亿)": "N/A", "环比变化(%)": "N/A",
                "5日均成交额(亿)": "N/A", "与5日均值比(%)": "N/A"}


# ============================================================
# 需求 3：行业板块增强（成交额、强势天数、领涨股TOP3）
# ============================================================

def _get_board_stocks(board_name, board_type="industry"):
    """获取板块成分股（带缓存和降级）"""
    try:
        if board_type == "industry":
            df = ak.stock_board_industry_cons_em(symbol=board_name)
        else:
            df = ak.stock_board_concept_cons_em(symbol=board_name)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass
    return None


def get_industry_sectors():
    """
    需求3：获取行业板块涨跌情况（增强版）
    - top10 板块含成交额、强势天数、领涨股TOP3
    - bottom5 只保留5个
    """
    print("🏭 获取行业板块数据...")
    try:
        df = ak.stock_board_industry_name_em()
        df = df.sort_values("涨跌幅", ascending=False)

        all_sectors = []
        for _, row in df.iterrows():
            all_sectors.append({
                "板块名称": row["板块名称"],
                "板块代码": row.get("板块代码", ""),
                "涨跌幅(%)": round(row["涨跌幅"], 2),
                "成交额(亿)": round(row.get("成交额", 0) / 1e8, 2) if row.get("成交额") else "N/A",
                "领涨股": row.get("领涨股票-名称", ""),
                "领涨股涨幅(%)": round(row.get("领涨股票-涨跌幅", 0), 2) if row.get("领涨股票-涨跌幅") else "N/A",
                "上涨家数": int(row.get("上涨家数", 0)) if row.get("上涨家数") else 0,
                "下跌家数": int(row.get("下跌家数", 0)) if row.get("下跌家数") else 0,
            })

        # top10 板块：获取领涨股TOP3
        top10 = all_sectors[:10]
        print("  获取领涨股TOP3（top10板块）...")
        for sector in top10:
            sector["领涨股TOP3"] = _get_top3_stocks(sector["板块名称"], "industry")
            sector["强势天数"] = "N/A"  # 需要历史数据，先标记

        # bottom5
        bottom5 = all_sectors[-5:] if len(all_sectors) >= 5 else all_sectors[-len(all_sectors):]
        bottom5.reverse()

        return {
            "all": all_sectors,
            "top10": top10,
            "bottom5": bottom5
        }
    except Exception as e:
        print(f"⚠️ 获取行业板块失败: {e}")
        return {"all": [], "top10": [], "bottom5": []}


def _get_top3_stocks(board_name, board_type="industry"):
    """获取板块内涨幅前3的个股"""
    try:
        df = _get_board_stocks(board_name, board_type)
        if df is None or df.empty:
            return []

        # 按涨跌幅排序
        if "涨跌幅" in df.columns:
            df = df.sort_values("涨跌幅", ascending=False)

        top3 = []
        for _, row in df.head(3).iterrows():
            name = row.get("名称", row.get("股票名称", ""))
            code = row.get("代码", row.get("股票代码", ""))
            pct = row.get("涨跌幅", 0)
            top3.append({
                "名称": str(name),
                "代码": str(code),
                "涨跌幅(%)": round(float(pct), 2) if pct else 0
            })
        return top3
    except Exception as e:
        return []


# ============================================================
# 需求 4：概念板块增强（涨停个数、涨超5%个数）
# ============================================================

def get_concept_sectors():
    """
    需求4：获取概念板块涨跌（增强版）
    - top10：含涨停个数、涨超5%个数
    - bottom5
    """
    print("💡 获取概念板块数据...")
    try:
        df = ak.stock_board_concept_name_em()
        df = df.sort_values("涨跌幅", ascending=False)

        all_concepts = []
        for _, row in df.iterrows():
            all_concepts.append({
                "概念名称": row["板块名称"],
                "涨跌幅(%)": round(row["涨跌幅"], 2),
                "领涨股": row.get("领涨股票-名称", ""),
                "领涨股涨幅(%)": round(row.get("领涨股票-涨跌幅", 0), 2) if row.get("领涨股票-涨跌幅") else "N/A",
            })

        top10 = all_concepts[:10]
        bottom5 = all_concepts[-5:] if len(all_concepts) >= 5 else []
        bottom5.reverse()

        # 对 top10 概念板块统计成分股涨停数和涨超5%数
        print("  统计概念板块成分股（top10）...")
        for concept in top10:
            stats = _count_limit_up_in_board(concept["概念名称"], "concept")
            concept["涨停个数"] = stats["涨停个数"]
            concept["涨超5%个数"] = stats["涨超5%个数"]

        return {"top10": top10, "bottom5": bottom5}
    except Exception as e:
        print(f"⚠️ 获取概念板块失败: {e}")
        return {"top10": [], "bottom5": []}


def _count_limit_up_in_board(board_name, board_type="concept"):
    """统计板块内涨停和涨超5%的个股数"""
    try:
        df = _get_board_stocks(board_name, board_type)
        if df is None or df.empty:
            return {"涨停个数": 0, "涨超5%个数": 0}

        pct_col = "涨跌幅"
        if pct_col not in df.columns:
            return {"涨停个数": 0, "涨超5%个数": 0}

        df[pct_col] = pd.to_numeric(df[pct_col], errors="coerce")
        limit_up = int((df[pct_col] >= 9.9).sum())
        up5 = int((df[pct_col] >= 5).sum())

        return {"涨停个数": limit_up, "涨超5%个数": up5}
    except Exception:
        return {"涨停个数": 0, "涨超5%个数": 0}


# ============================================================
# 需求 5：涨停全量 + 归因分析
# ============================================================

def get_limit_up_down():
    """
    需求5：获取涨停/跌停统计（全量涨停 + 归因分析）
    """
    print("📈 获取涨跌停统计...")
    try:
        today_str = datetime.now().strftime("%Y%m%d")

        # 涨停板 - 全量
        df_up = ak.stock_zt_pool_em(date=today_str)
        limit_up_count = len(df_up) if df_up is not None else 0

        # 跌停板
        try:
            df_down = ak.stock_zt_pool_dtgc_em(date=today_str)
            limit_down_count = len(df_down) if df_down is not None else 0
        except Exception:
            limit_down_count = 0

        # 涨停全量明细
        limit_up_details = []
        if df_up is not None and not df_up.empty:
            # 获取行业板块映射（用于归因）
            industry_map = _get_industry_ranking()

            for _, row in df_up.iterrows():
                stock_name = str(row.get("名称", ""))
                stock_code = str(row.get("代码", ""))

                # 涨停原因归因
                reason = _analyze_limit_up_reason(row, industry_map)

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

        # 涨停归因汇总
        reason_summary = _summarize_reasons(limit_up_details)

        return {
            "涨停数量": limit_up_count,
            "跌停数量": limit_down_count,
            "涨停明细": limit_up_details,
            "涨停归因汇总": reason_summary
        }
    except Exception as e:
        print(f"⚠️ 获取涨跌停统计失败: {e}")
        return {"涨停数量": 0, "跌停数量": 0, "涨停明细": [], "涨停归因汇总": {}}


def _get_industry_ranking():
    """获取行业板块当日排名（用于涨停归因）"""
    try:
        df = ak.stock_board_industry_name_em()
        df = df.sort_values("涨跌幅", ascending=False)
        ranking = {}
        for i, (_, row) in enumerate(df.iterrows()):
            ranking[row["板块名称"]] = {
                "rank": i + 1,
                "pct": round(row["涨跌幅"], 2),
                "is_top5": i < 5
            }
        return ranking
    except Exception:
        return {}


def _analyze_limit_up_reason(row, industry_map):
    """分析单只涨停股的归因"""
    reasons = []
    details = {}

    # 1. 连板归因
    lb = row.get("连板数", 0)
    try:
        lb = int(lb)
    except (ValueError, TypeError):
        lb = 0

    if lb >= 5:
        reasons.append(f"{lb}连板龙头")
        details["连板"] = f"{lb}连板"
    elif lb >= 3:
        reasons.append(f"{lb}连板")
        details["连板"] = f"{lb}连板"
    elif lb >= 2:
        reasons.append("2连板")
        details["连板"] = "2连板"

    # 2. 封板时间归因
    ft = str(row.get("首次封板时间", ""))
    if ft and ft != "-" and ft != "nan":
        try:
            hour = int(ft.split(":")[0])
            minute = int(ft.split(":")[1])
            if hour < 10 or (hour == 10 and minute <= 0):
                reasons.append("早盘秒板")
                details["封板时间"] = f"早盘{ft}"
            elif hour < 11:
                reasons.append("早盘封板")
                details["封板时间"] = f"早盘{ft}"
        except Exception:
            pass

    # 3. 成交额归因
    amt = row.get("成交额", 0)
    try:
        amt = float(amt) / 1e8
        if amt > 50:
            reasons.append(f"巨量封板({amt:.0f}亿)")
            details["成交额"] = f"{amt:.0f}亿"
    except Exception:
        pass

    if not reasons:
        reasons.append("首板涨停")
        details["类型"] = "首板"

    return {
        "summary": " + ".join(reasons),
        "details": details
    }


def _summarize_reasons(limit_up_details):
    """涨停归因汇总统计"""
    lb_count = {"首板": 0, "2连板": 0, "3-4连板": 0, "5连板及以上": 0}
    time_count = {"早盘秒板": 0, "早盘封板": 0, "其他": 0}

    for stock in limit_up_details:
        reason = stock.get("涨停原因", "")
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

    return {
        "连板分布": lb_count,
        "封板时间分布": time_count
    }


# ============================================================
# 需求 1（续）：市场宽度 + 成交额对比
# ============================================================

def get_market_breadth():
    """
    获取市场宽度数据（涨跌家数统计）+ 成交额历史对比
    """
    print("📉 获取市场宽度数据...")
    try:
        df = _get_spot_df()
        if df is not None and not df.empty:
            total = len(df)
            up = int((df["涨跌幅"] > 0).sum())
            down = int((df["涨跌幅"] < 0).sum())
            flat = total - up - down

            # 按涨跌幅分段统计
            surge_9_plus = int((df["涨跌幅"] >= 9).sum())
            surge_5_9 = int(((df["涨跌幅"] >= 5) & (df["涨跌幅"] < 9)).sum())
            surge_3_5 = int(((df["涨跌幅"] >= 3) & (df["涨跌幅"] < 5)).sum())
            up_0_3 = int(((df["涨跌幅"] > 0) & (df["涨跌幅"] < 3)).sum())
            down_0_3 = int(((df["涨跌幅"] <= 0) & (df["涨跌幅"] > -3)).sum())
            down_3_5 = int(((df["涨跌幅"] <= -3) & (df["涨跌幅"] > -5)).sum())
            down_5_9 = int(((df["涨跌幅"] <= -5) & (df["涨跌幅"] > -9)).sum())
            plunge_9_plus = int((df["涨跌幅"] <= -9).sum())

            # 总成交额
            total_amount = df["成交额"].sum() / 1e8

            # 成交额历史对比
            amount_compare = get_historical_amount()

            return {
                "上涨家数": up,
                "下跌家数": down,
                "平盘家数": flat,
                "总成交额(亿)": round(total_amount, 2),
                "成交额对比": amount_compare,
                "涨幅分布": {
                    "涨停(≥9%)": surge_9_plus,
                    "大涨(5%-9%)": surge_5_9,
                    "中涨(3%-5%)": surge_3_5,
                    "小涨(0-3%)": up_0_3,
                    "小跌(0-3%)": down_0_3,
                    "中跌(3%-5%)": down_3_5,
                    "大跌(5%-9%)": down_5_9,
                    "跌停(≤-9%)": plunge_9_plus
                }
            }
    except Exception as e:
        print(f"⚠️ 获取市场宽度失败: {e}")

    return {
        "上涨家数": 0, "下跌家数": 0, "平盘家数": 0,
        "总成交额(亿)": 0,
        "成交额对比": {"前一交易日成交额(亿)": "N/A", "环比变化(%)": "N/A",
                    "5日均成交额(亿)": "N/A", "与5日均值比(%)": "N/A"},
        "涨幅分布": {}
    }


# ============================================================
# 需求 6：成交额 TOP20 + 占比
# ============================================================

def get_leading_stocks():
    """
    需求6：获取成交额前20的热门个股 + 占比
    """
    print("🔥 获取热门个股（TOP20）...")
    try:
        df = _get_spot_df()
        if df is not None and not df.empty:
            total_amount = df["成交额"].sum()
            top20 = df.nlargest(20, "成交额")
            top20_amount = top20["成交额"].sum()

            result = []
            for _, row in top20.iterrows():
                result.append({
                    "股票代码": str(row["代码"]),
                    "股票名称": str(row["名称"]),
                    "最新价": round(float(row["最新价"]), 2),
                    "涨跌幅(%)": round(float(row["涨跌幅"]), 2),
                    "成交额(亿)": round(float(row["成交额"]) / 1e8, 2),
                    "换手率(%)": round(float(row.get("换手率", 0)), 2) if row.get("换手率") else "N/A",
                    "流通市值(亿)": round(float(row.get("流通市值", 0)) / 1e8, 2) if row.get("流通市值") else "N/A"
                })

            return {
                "top20": result,
                "top20成交额合计(亿)": round(top20_amount / 1e8, 2),
                "top20占比(%)": round(top20_amount / total_amount * 100, 2) if total_amount > 0 else 0
            }
    except Exception as e:
        print(f"⚠️ 获取热门个股失败: {e}")

    return {"top20": [], "top20成交额合计(亿)": 0, "top20占比(%)": 0}


# ============================================================
# 北向资金
# ============================================================

def get_north_flow():
    """
    获取北向资金流向
    """
    print("💰 获取北向资金数据...")
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            return {
                "日期": str(latest.get("date", "")),
                "当日净流入(亿)": round(float(latest.get("value", 0)), 2)
            }
    except Exception as e:
        print(f"⚠️ 获取北向资金失败: {e}")

    return {"日期": "", "当日净流入(亿)": "N/A"}


# ============================================================
# 主入口
# ============================================================

def collect_all_data():
    """收集所有复盘数据"""
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"  📊 A股每日复盘数据采集 v2.0 - {today}")
    print(f"{'='*60}\n")

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

    # 保存 JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR, f"data_{today}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    # 同时保存一份 latest.json
    latest_path = os.path.join(OUTPUT_DIR, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✅ 数据已保存至: {json_path}")
    return data


if __name__ == "__main__":
    data = collect_all_data()

    # 简要输出
    if data["大盘指数"]:
        for idx in data["大盘指数"]:
            direction = "📈" if idx["涨跌幅(%)"] >= 0 else "📉"
            print(f"  {direction} {idx['指数名称']}: {idx['当前点位']} ({idx['涨跌幅(%)']:+.2f}%)")

    if data["市场宽度"]:
        bw = data["市场宽度"]
        print(f"\n  上涨: {bw['上涨家数']} | 下跌: {bw['下跌家数']} | 平盘: {bw['平盘家数']}")
        print(f"  总成交额: {bw['总成交额(亿)']} 亿")
        ac = bw.get("成交额对比", {})
        if ac.get("环比变化(%)") != "N/A":
            print(f"  成交额环比: {ac['环比变化(%)']:+.2f}% | 5日均值: {ac['5日均成交额(亿)']}亿")

    if data["涨跌停统计"]:
        zt = data["涨跌停统计"]
        print(f"  涨停: {zt['涨停数量']} | 跌停: {zt['跌停数量']}")

    if data["热门个股"]:
        hs = data["热门个股"]
        print(f"  成交额TOP20占比: {hs.get('top20占比(%)', 0)}%")

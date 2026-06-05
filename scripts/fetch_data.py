#!/usr/bin/env python3
"""
A股每日复盘 - 数据获取模块
获取大盘指数、行业板块、涨跌停统计、北向资金等核心数据
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import sys

# 输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")


def get_market_index():
    """
    获取主要大盘指数行情：
    - 上证指数 (000001)
    - 深证成指 (399001)
    - 创业板指 (399006)
    - 科创50   (000688)
    """
    print("📊 获取大盘指数数据...")
    try:
        # 获取实时行情
        df = ak.stock_zh_index_spot_em()
        target_codes = ["上证指数", "深证成指", "创业板指", "科创50"]
        
        # 筛选目标指数
        result = df[df["名称"].isin(target_codes)].copy()
        
        # 整理字段
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
        
        return result.to_dict(orient="records")
    except Exception as e:
        print(f"⚠️ 获取大盘指数失败: {e}")
        return []


def get_industry_sectors():
    """
    获取行业板块涨跌情况（东方财富行业板块）
    """
    print("🏭 获取行业板块数据...")
    try:
        df = ak.stock_board_industry_name_em()
        df = df.sort_values("涨跌幅", ascending=False)
        
        result = []
        for _, row in df.iterrows():
            result.append({
                "板块名称": row["板块名称"],
                "涨跌幅(%)": round(row["涨跌幅"], 2),
                "领涨股": row.get("领涨股票-名称", ""),
                "领涨股涨幅(%)": round(row.get("领涨股票-涨跌幅", 0), 2) if row.get("领涨股票-涨跌幅") else ""
            })
        
        # 取前10和后10
        top10 = result[:10]
        bottom10 = result[-10:] if len(result) >= 10 else []
        bottom10.reverse()
        
        return {
            "all": result,
            "top10": top10,
            "bottom10": bottom10
        }
    except Exception as e:
        print(f"⚠️ 获取行业板块失败: {e}")
        return {"all": [], "top10": [], "bottom10": []}


def get_limit_up_down():
    """
    获取涨停/跌停统计
    """
    print("📈 获取涨跌停统计...")
    try:
        # 涨停板
        df_up = ak.stock_zt_pool_em(date=datetime.now().strftime("%Y%m%d"))
        limit_up_count = len(df_up) if df_up is not None else 0
        
        # 跌停板
        df_down = ak.stock_zt_pool_dtgc_em(date=datetime.now().strftime("%Y%m%d"))
        limit_down_count = len(df_down) if df_down is not None else 0
        
        # 涨停明细（前10）
        limit_up_details = []
        if df_up is not None and not df_up.empty:
            for _, row in df_up.head(10).iterrows():
                limit_up_details.append({
                    "股票代码": row.get("代码", ""),
                    "股票名称": row.get("名称", ""),
                    "涨停价": row.get("最新价", ""),
                    "封单金额": row.get("封单金额", ""),
                    "连板数": row.get("连板数", "")
                })
        
        return {
            "涨停数量": limit_up_count,
            "跌停数量": limit_down_count,
            "涨停明细": limit_up_details,
            "炸板率": "数据获取中"  # 部分接口可能不支持
        }
    except Exception as e:
        print(f"⚠️ 获取涨跌停统计失败: {e}")
        return {"涨停数量": 0, "跌停数量": 0, "涨停明细": [], "炸板率": "N/A"}


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
                "当日净流入(亿)": round(latest.get("value", 0), 2)
            }
    except Exception as e:
        print(f"⚠️ 获取北向资金失败: {e}")
    
    return {"日期": "", "当日净流入(亿)": "N/A"}


def get_market_breadth():
    """
    获取市场宽度数据（涨跌家数统计）
    """
    print("📉 获取市场宽度数据...")
    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            total = len(df)
            up = len(df[df["涨跌幅"] > 0])
            down = len(df[df["涨跌幅"] < 0])
            flat = total - up - down
            
            # 按涨跌幅分段统计
            surge_9_plus = len(df[df["涨跌幅"] >= 9])
            surge_5_9 = len(df[(df["涨跌幅"] >= 5) & (df["涨跌幅"] < 9)])
            surge_3_5 = len(df[(df["涨跌幅"] >= 3) & (df["涨跌幅"] < 5)])
            up_0_3 = len(df[(df["涨跌幅"] > 0) & (df["涨跌幅"] < 3)])
            down_0_3 = len(df[(df["涨跌幅"] <= 0) & (df["涨跌幅"] > -3)])
            down_3_5 = len(df[(df["涨跌幅"] <= -3) & (df["涨跌幅"] > -5)])
            down_5_9 = len(df[(df["涨跌幅"] <= -5) & (df["涨跌幅"] > -9)])
            plunge_9_plus = len(df[df["涨跌幅"] <= -9])
            
            # 成交额统计
            total_amount = df["成交额"].sum() / 1e8
            
            return {
                "上涨家数": up,
                "下跌家数": down,
                "平盘家数": flat,
                "总成交额(亿)": round(total_amount, 2),
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
    
    return {"上涨家数": 0, "下跌家数": 0, "平盘家数": 0, "总成交额(亿)": 0, "涨幅分布": {}}


def get_leading_stocks():
    """
    获取成交额前10的热门个股
    """
    print("🔥 获取热门个股...")
    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            top = df.nlargest(10, "成交额")
            result = []
            for _, row in top.iterrows():
                result.append({
                    "股票代码": row["代码"],
                    "股票名称": row["名称"],
                    "最新价": round(row["最新价"], 2),
                    "涨跌幅(%)": round(row["涨跌幅"], 2),
                    "成交额(亿)": round(row["成交额"] / 1e8, 2),
                    "换手率(%)": round(row.get("换手率", 0), 2) if row.get("换手率") else "N/A"
                })
            return result
    except Exception as e:
        print(f"⚠️ 获取热门个股失败: {e}")
    
    return []


def get_concept_sectors():
    """
    获取概念板块涨跌（前5和后5）
    """
    print("💡 获取概念板块数据...")
    try:
        df = ak.stock_board_concept_name_em()
        df = df.sort_values("涨跌幅", ascending=False)
        
        top5 = []
        for _, row in df.head(5).iterrows():
            top5.append({
                "概念名称": row["板块名称"],
                "涨跌幅(%)": round(row["涨跌幅"], 2)
            })
        
        bottom5 = []
        for _, row in df.tail(5).iterrows():
            bottom5.append({
                "概念名称": row["板块名称"],
                "涨跌幅(%)": round(row["涨跌幅"], 2)
            })
        bottom5.reverse()
        
        return {"top5": top5, "bottom5": bottom5}
    except Exception as e:
        print(f"⚠️ 获取概念板块失败: {e}")
        return {"top5": [], "bottom5": []}


def collect_all_data():
    """收集所有复盘数据"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    print(f"\n{'='*60}")
    print(f"  📊 A股每日复盘数据采集 - {today}")
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
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 同时保存一份 latest.json 方便引用
    latest_path = os.path.join(OUTPUT_DIR, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
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
    
    if data["涨跌停统计"]:
        zt = data["涨跌停统计"]
        print(f"  涨停: {zt['涨停数量']} | 跌停: {zt['跌停数量']}")

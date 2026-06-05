#!/usr/bin/env python3
"""
A股每日复盘 - 统一数据源层 v3.0
支持多数据源冗余：东方财富 push2 API（主）、新浪财经（备）、降级兜底

设计原则：
1. 每个数据获取函数都有 try 主源 → except 备源 → finally 兜底
2. 直接使用 requests 而非 akshare，避免中间层带来的不确定性
3. 带 User-Agent 伪装和自动重试
"""

import requests
import json
import re
import time
from datetime import datetime

# ============================================================
# 通用工具
# ============================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn/",
}


def safe_request(url, headers=None, params=None, max_retries=3, timeout=15):
    """带重试的 HTTP 请求"""
    h = headers or HEADERS
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=h, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp
            print(f"  ⚠️ HTTP {resp.status_code}, 重试 {attempt+1}/{max_retries}")
        except Exception as e:
            print(f"  ⚠️ 请求异常: {e}, 重试 {attempt+1}/{max_retries}")
        time.sleep(1 + attempt)
    return None


# ============================================================
# 数据源 1：东方财富 push2 API（主力）
# ============================================================

EM_PUSH2_URL = "https://push2.eastmoney.com/api/qt/clist/get"


def em_push2_get(fs, fields, pn=1, pz=500, sort="f3", order="desc"):
    """
    东方财富 push2 通用数据获取
    fs: 筛选条件，如 "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"（全A股）
    fields: 返回字段，如 "f2,f3,f4,f12,f14"
    """
    params = {
        "pn": pn,
        "pz": pz,
        "po": 1 if order == "asc" else 0,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": sort,
        "fs": fs,
        "fields": fields,
    }
    resp = safe_request(EM_PUSH2_URL, params=params)
    if resp:
        try:
            data = resp.json()
            if data.get("data") and data["data"].get("diff"):
                return data["data"]
        except Exception as e:
            print(f"  ⚠️ JSON 解析失败: {e}")
    return None


def em_all_a_stocks(page_size=500):
    """
    获取全市场A股行情（分页）
    返回所有个股的 DataFrame 兼容格式（list of dict）
    """
    fs = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
    fields = "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21"

    all_data = []
    page = 1
    max_pages = 12  # ~5000只 / 500 = 10页

    while page <= max_pages:
        result = em_push2_get(fs, fields, pn=page, pz=page_size)
        if not result or not result.get("diff"):
            break

        all_data.extend(result["diff"])
        total = result.get("total", 0)
        if page * page_size >= total:
            break
        page += 1
        time.sleep(0.3)  # 避免频率限制

    if not all_data:
        print("  ⚠️ 全市场行情为空，尝试备用接口...")
        return None

    # 转为 DataFrame 友好的格式
    records = []
    for item in all_data:
        records.append({
            "代码": item.get("f12", ""),
            "名称": item.get("f14", ""),
            "最新价": item.get("f2", 0) or 0,
            "涨跌幅": item.get("f3", 0) or 0,
            "涨跌额": item.get("f4", 0) or 0,
            "成交量": item.get("f5", 0) or 0,
            "成交额": item.get("f6", 0) or 0,
            "换手率": item.get("f8", 0) or 0,
            "量比": item.get("f10", 0) or 0,
            "市盈率": item.get("f9", 0) or 0,
            "流通市值": item.get("f20", 0) or 0,
            "总市值": item.get("f21", 0) or 0,
            "振幅": item.get("f7", 0) or 0,
        })

    print(f"  ✅ 全市场行情: {len(records)} 只")
    return records


def em_index_spot():
    """
    获取大盘指数实时行情
    fs=b:1+t:2 是大盘指数分类
    """
    fs = "b:1+t:2"
    fields = "f2,f3,f4,f5,f6,f12,f14"
    result = em_push2_get(fs, fields, pn=1, pz=20)

    if not result:
        return None

    target = {
        "1.000001": "上证指数", "0.399001": "深证成指", "0.399006": "创业板指",
        "1.000688": "科创50", "1.000300": "沪深300", "1.000905": "中证500",
        "1.000852": "中证1000", "1.932000": "中证2000",
    }

    records = []
    for item in result.get("diff", []):
        code = f"{item.get('f13', 0)}.{item.get('f12', '')}"
        name = item.get("f14", "")
        # 匹配目标指数
        matched = False
        for key, label in target.items():
            if key.endswith(item.get("f12", "")) or label == name:
                records.append({
                    "指数名称": label,
                    "当前点位": round(float(item.get("f2", 0) or 0), 2),
                    "涨跌幅(%)": round(float(item.get("f3", 0) or 0), 2),
                    "涨跌额": round(float(item.get("f4", 0) or 0), 2),
                    "成交额(亿)": round(float(item.get("f6", 0) or 0) / 1e8, 2),
                })
                matched = True
                break
        if not matched and name in target.values():
            records.append({
                "指数名称": name,
                "当前点位": round(float(item.get("f2", 0) or 0), 2),
                "涨跌幅(%)": round(float(item.get("f3", 0) or 0), 2),
                "涨跌额": round(float(item.get("f4", 0) or 0), 2),
                "成交额(亿)": round(float(item.get("f6", 0) or 0) / 1e8, 2),
            })

    # 按目标顺序排列
    order = {v: i for i, v in enumerate(target.values())}
    records.sort(key=lambda x: order.get(x["指数名称"], 99))

    print(f"  ✅ 大盘指数: {len(records)} 个")
    return records


def em_industry_boards():
    """
    获取行业板块行情
    fs=m:90+t:2 是行业板块分类
    """
    fs = "m:90+t:2"
    fields = "f2,f3,f4,f5,f6,f12,f14,f104,f105,f128,f129"
    result = em_push2_get(fs, fields, pn=1, pz=100)

    if not result:
        return None

    records = []
    for item in result.get("diff", []):
        records.append({
            "板块名称": item.get("f14", ""),
            "板块代码": item.get("f12", ""),
            "涨跌幅(%)": round(float(item.get("f3", 0) or 0), 2),
            "成交额(亿)": round(float(item.get("f6", 0) or 0) / 1e8, 2),
            "上涨家数": int(item.get("f104", 0) or 0),
            "下跌家数": int(item.get("f105", 0) or 0),
            "领涨股": item.get("f128", ""),
            "领涨股涨幅(%)": round(float(item.get("f129", 0) or 0), 2),
        })

    records.sort(key=lambda x: x["涨跌幅(%)"], reverse=True)
    print(f"  ✅ 行业板块: {len(records)} 个")
    return records


def em_concept_boards():
    """
    获取概念板块行情
    fs=m:90+t:3 是概念板块分类
    """
    fs = "m:90+t:3"
    fields = "f2,f3,f4,f6,f12,f14,f104,f105,f128,f129"
    result = em_push2_get(fs, fields, pn=1, pz=200)

    if not result:
        return None

    records = []
    for item in result.get("diff", []):
        records.append({
            "概念名称": item.get("f14", ""),
            "概念代码": item.get("f12", ""),
            "涨跌幅(%)": round(float(item.get("f3", 0) or 0), 2),
            "成交额(亿)": round(float(item.get("f6", 0) or 0) / 1e8, 2),
            "上涨家数": int(item.get("f104", 0) or 0),
            "下跌家数": int(item.get("f105", 0) or 0),
            "领涨股": item.get("f128", ""),
        })

    records.sort(key=lambda x: x["涨跌幅(%)"], reverse=True)
    print(f"  ✅ 概念板块: {len(records)} 个")
    return records


def em_board_stocks(board_code, board_type="industry"):
    """
    获取板块成分股行情
    board_type: "industry"(行业) 或 "concept"(概念)
    """
    if board_type == "industry":
        fs = f"b:{board_code}+t:2"
    else:
        fs = f"b:{board_code}+t:3"

    fields = "f2,f3,f4,f6,f8,f12,f14,f20"
    result = em_push2_get(fs, fields, pn=1, pz=500)

    if not result:
        return []

    records = []
    for item in result.get("diff", []):
        records.append({
            "代码": item.get("f12", ""),
            "名称": item.get("f14", ""),
            "最新价": float(item.get("f2", 0) or 0),
            "涨跌幅(%)": float(item.get("f3", 0) or 0),
            "成交额(亿)": round(float(item.get("f6", 0) or 0) / 1e8, 2),
            "换手率(%)": float(item.get("f8", 0) or 0),
        })

    return records


def em_index_daily(symbol="1.000001", days=6):
    """
    获取指数日K线（用于历史成交额对比）
    symbol: 1.000001=上证指数
    """
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": symbol,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "klt": "101",  # 日K
        "fqt": "1",
        "end": "20500101",
        "lmt": days,
    }
    resp = safe_request(url, params=params)
    if resp:
        try:
            data = resp.json()
            if data.get("data") and data["data"].get("klines"):
                klines = data["data"]["klines"]
                amounts = []
                for line in klines:
                    parts = line.split(",")
                    if len(parts) >= 7:
                        amounts.append(float(parts[6]) / 1e8)  # 成交额(亿)
                return amounts
        except Exception as e:
            print(f"  ⚠️ 指数K线解析失败: {e}")
    return None


# ============================================================
# 数据源 2：新浪财经 API（备用）
# ============================================================

def sina_index_spot():
    """
    新浪财经大盘指数实时行情（备用数据源）
    """
    codes = "sh000001,sz399001,sz399006,sh000688,sh000300,sh000905,sh000852,sh932000"
    url = f"https://hq.sinajs.cn/list={codes}"

    resp = safe_request(url, headers=SINA_HEADERS)
    if not resp or not resp.text:
        return None

    # 解析 GBK 编码
    resp.encoding = "gbk"

    name_map = {
        "sh000001": "上证指数", "sz399001": "深证成指", "sz399006": "创业板指",
        "sh000688": "科创50", "sh000300": "沪深300", "sh000905": "中证500",
        "sh000852": "中证1000", "sh932000": "中证2000",
    }

    records = []
    for line in resp.text.strip().split("\n"):
        if not line.strip() or "hq_str" not in line:
            continue
        # 提取代码和值
        match = re.search(r'hq_str_(\w+)="(.+)"', line)
        if not match:
            continue
        code = match.group(1)
        values = match.group(2).split(",")
        if len(values) < 6:
            continue

        name = name_map.get(code, values[0])
        try:
            records.append({
                "指数名称": name,
                "当前点位": round(float(values[1]), 2),
                "涨跌额": round(float(values[2]), 2),
                "涨跌幅(%)": round(float(values[3]), 2),
                "成交额(亿)": round(float(values[5]) / 1e8, 2) if values[5] else 0,
            })
        except (ValueError, IndexError):
            continue

    # 排序
    order = {v: i for i, v in enumerate(name_map.values())}
    records.sort(key=lambda x: order.get(x["指数名称"], 99))

    if records:
        print(f"  ✅ 大盘指数(新浪): {len(records)} 个")
    return records


# ============================================================
# 数据源 3：涨停原因增强（东方财富涨停板数据 + 行业/概念归因）
# ============================================================

def em_limit_up_detail(date_str=None):
    """
    获取涨停板详细数据（包含涨停统计等字段用于归因）
    使用 akshare 的 stock_zt_pool_em 接口（该接口在 Actions 中已验证可用）
    """
    try:
        import akshare as ak
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
        df = ak.stock_zt_pool_em(date=date_str)
        if df is None or df.empty:
            return []
        return df
    except Exception as e:
        print(f"  ⚠️ 涨停板数据获取失败: {e}")
        return []


def em_limit_up_detail_strong(date_str=None):
    """
    获取强势股池数据（含入选理由字段，可辅助涨停归因）
    """
    try:
        import akshare as ak
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
        df = ak.stock_zt_pool_strong_em(date=date_str)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass
    return None


# ============================================================
# 数据源 4：涨停原因智能归因引擎
# ============================================================

def analyze_limit_up_reason(stock, industry_ranking, concept_ranking, board_stock_map):
    """
    智能涨停原因归因（不依赖外部文本数据）
    
    参数:
    - stock: 涨停个股信息 dict
    - industry_ranking: 行业板块排名 {板块名: {"rank": 1, "pct": 3.5}}
    - concept_ranking: 概念板块排名 {概念名: {"rank": 1, "pct": 4.2}}
    - board_stock_map: {股票代码: {"行业": "半导体", "概念": ["光刻机","Chiplet"]}}
    
    返回: 详细的涨停原因描述
    """
    reasons = []
    details = {}
    
    stock_code = str(stock.get("代码", ""))
    stock_name = str(stock.get("名称", ""))
    
    # 1. 连板归因
    lb = stock.get("连板数", 0)
    try:
        lb = int(lb)
    except (ValueError, TypeError):
        lb = 0
    
    if lb >= 5:
        reasons.append(f"📌 {lb}连板高标龙头")
        details["连板"] = f"{lb}连板"
    elif lb >= 3:
        reasons.append(f"🔥 {lb}连板")
        details["连板"] = f"{lb}连板"
    elif lb >= 2:
        reasons.append(f"2连板")
        details["连板"] = "2连板"
    else:
        details["连板"] = "首板"
    
    # 2. 封板时间归因
    ft = str(stock.get("首次封板时间", ""))
    if ft and ft != "-" and ft != "nan":
        try:
            parts = ft.split(":")
            hour, minute = int(parts[0]), int(parts[1])
            if hour < 10 or (hour == 10 and minute <= 5):
                reasons.append("⚡ 早盘秒板")
                details["封板特征"] = "早盘秒板"
            elif hour < 11:
                reasons.append("早盘封板")
                details["封板特征"] = "早盘封板"
            else:
                details["封板特征"] = f"{ft}封板"
        except Exception:
            details["封板特征"] = ft
    
    # 3. 封单力度归因
    fd = str(stock.get("封单金额", stock.get("封板资金", "")))
    if fd and fd != "-" and fd != "nan":
        try:
            fd_clean = fd.replace("亿", "").replace("万", "")
            fd_val = float(fd_clean)
            if "万" in fd:
                fd_val /= 10000
            if fd_val > 10:
                reasons.append(f"💪 超大封单({fd})")
                details["封单力度"] = fd
            elif fd_val > 3:
                reasons.append(f"封单({fd})")
                details["封单力度"] = fd
        except Exception:
            pass
    
    # 4. 行业板块归因
    board_info = board_stock_map.get(stock_code, {})
    industry = board_info.get("行业", "")
    if industry and industry in industry_ranking:
        ir = industry_ranking[industry]
        if ir["rank"] <= 3:
            reasons.append(f"🏭 龙头板块「{industry}」(板块+{ir['pct']:+.2f}%)")
            details["行业归因"] = f"{industry}(板块第{ir['rank']}名,+{ir['pct']:.2f}%)"
        elif ir["rank"] <= 10:
            reasons.append(f"板块「{industry}」(行业第{ir['rank']}名,+{ir['pct']:+.2f}%)")
            details["行业归因"] = f"{industry}(板块第{ir['rank']}名,+{ir['pct']:.2f}%)"
        elif ir["pct"] > 0:
            details["行业归因"] = f"{industry}(+{ir['pct']:.2f}%)"
        else:
            details["行业归因"] = f"{industry}"
    
    # 5. 概念板块归因（取最强势的概念）
    concepts = board_info.get("概念", [])
    top_concept = None
    top_concept_rank = 999
    for c in concepts:
        if c in concept_ranking:
            cr = concept_ranking[c]
            if cr["rank"] < top_concept_rank:
                top_concept_rank = cr["rank"]
                top_concept = c
    
    if top_concept and top_concept_rank <= 5:
        cp = concept_ranking[top_concept]
        reasons.append(f"💡 核心概念「{top_concept}」(概念+{cp['pct']:+.2f}%)")
        details["概念归因"] = f"{top_concept}(概念第{top_concept_rank}名,+{cp['pct']:.2f}%)"
    elif top_concept:
        cp = concept_ranking[top_concept]
        details["概念归因"] = f"{top_concept}(+{cp['pct']:.2f}%)"
    
    # 6. 成交额归因
    amt = stock.get("成交额(亿)", stock.get("成交额", 0))
    try:
        amt = float(amt) if amt else 0
        if amt > 100:
            reasons.append(f"📊 巨量成交({amt:.0f}亿)")
            details["成交特征"] = f"巨量{amt:.0f}亿"
        elif amt > 30:
            details["成交特征"] = f"{amt:.0f}亿"
    except (ValueError, TypeError):
        pass
    
    # 如果没有任何原因，给一个基础归因
    if not reasons:
        reasons.append("首板涨停")
    
    summary = " | ".join(reasons)
    return {"summary": summary, "details": details}


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  数据源测试")
    print("=" * 60)

    print("\n1. 测试东方财富 push2 - 大盘指数:")
    idx = em_index_spot()
    if idx:
        for i in idx:
            print(f"   {i['指数名称']}: {i['当前点位']} ({i['涨跌幅(%)']:+.2f}%)")

    print("\n2. 测试东方财富 push2 - 行业板块:")
    ind = em_industry_boards()
    if ind:
        for i in ind[:3]:
            print(f"   {i['板块名称']}: {i['涨跌幅(%)']:+.2f}%")

    print("\n3. 测试东方财富 push2 - 全市场行情:")
    all_stocks = em_all_a_stocks()
    if all_stocks:
        up = sum(1 for s in all_stocks if s["涨跌幅"] > 0)
        down = sum(1 for s in all_stocks if s["涨跌幅"] < 0)
        print(f"   上涨: {up}, 下跌: {down}")

    print("\n4. 测试新浪财经 - 大盘指数(备用):")
    sx = sina_index_spot()
    if sx:
        for i in sx:
            print(f"   {i['指数名称']}: {i['当前点位']} ({i['涨跌幅(%)']:+.2f}%)")

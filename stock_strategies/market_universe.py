"""全市場股票清單模組

提供台股上市/上櫃股票清單，用於全市場掃描模式。
資料來源：FinMind TaiwanStockInfo API（免費）。
快取 24 小時，避免每次掃描都重新抓取。
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

# 快取路徑
_CACHE_PATH = Path(os.environ.get("CACHE_DIR", "/tmp")) / "tw_stock_universe.json"
_CACHE_TTL_HOURS = 24

# FinMind API
_FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")
_FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"

# 排除清單：ETF、特別股、存託憑證等（代號長度 > 4 或含英文字母的通常是 ETF/KY 股）
_EXCLUDE_TYPES = {"ETF", "特別股", "存託憑證", "受益憑證"}


def get_universe(
    market: str = "all",
    exclude_etf: bool = True,
    min_market_cap_billion: float = 0.0,
) -> list[dict]:
    """取得台股股票清單。
    
    Args:
        market: "all" | "twse" (上市) | "tpex" (上櫃)
        exclude_etf: 是否排除 ETF（預設 True）
        min_market_cap_billion: 最低市值（億元，預設 0 = 不篩選）
    
    Returns:
        [{"stock_id": "2330", "name": "台積電", "market": "twse"}, ...]
    """
    cached = _load_cache()
    if cached is None:
        cached = _fetch_universe()
        _save_cache(cached)

    result = []
    for item in cached:
        # 市場篩選
        if market == "twse" and item.get("market") != "twse":
            continue
        if market == "tpex" and item.get("market") != "tpex":
            continue

        # 排除 ETF
        if exclude_etf and item.get("is_etf", False):
            continue

        result.append(item)

    return result


def _fetch_universe() -> list[dict]:
    """從 FinMind 抓取台股清單。"""
    params = {
        "dataset": "TaiwanStockInfo",
        "token": _FINMIND_TOKEN,
    }
    try:
        resp = requests.get(_FINMIND_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != 200:
            return _fallback_universe()
        
        raw = data.get("data", [])
        result = []
        for item in raw:
            sid = str(item.get("stock_id", "")).strip()
            name = str(item.get("stock_name", "")).strip()
            industry = str(item.get("industry_category", "")).strip()
            
            if not sid or not name:
                continue
            
            # 判斷是否為 ETF（代號通常為 4-6 碼數字，或名稱含 ETF/基金）
            is_etf = (
                len(sid) > 4
                or "ETF" in name.upper()
                or "基金" in name
                or "受益" in name
                or any(c.isalpha() and c.isascii() for c in sid)
            )
            
            # 判斷市場（上市/上櫃）
            # FinMind TaiwanStockInfo 有 type 欄位
            item_type = str(item.get("type", "")).strip()
            if "上市" in item_type or "twse" in item_type.lower():
                mkt = "twse"
            elif "上櫃" in item_type or "tpex" in item_type.lower():
                mkt = "tpex"
            else:
                mkt = "other"
            
            result.append({
                "stock_id": sid,
                "name": name,
                "industry": industry,
                "market": mkt,
                "is_etf": is_etf,
            })
        
        # 只保留純數字 4 碼代號（正常股票）
        result = [
            r for r in result
            if r["stock_id"].isdigit() and 4 <= len(r["stock_id"]) <= 4
        ]
        
        return result if result else _fallback_universe()
    
    except Exception:
        return _fallback_universe()


def _fallback_universe() -> list[dict]:
    """FinMind 失敗時的備用清單（台灣前 50 大市值股票）。"""
    stocks = [
        ("2330", "台積電"), ("2317", "鴻海"), ("2454", "聯發科"), ("2308", "台達電"),
        ("2382", "廣達"), ("2412", "中華電"), ("3711", "日月光投控"), ("2303", "聯電"),
        ("2881", "富邦金"), ("2882", "國泰金"), ("2886", "兆豐金"), ("2891", "中信金"),
        ("2884", "玉山金"), ("2885", "元大金"), ("2892", "第一金"), ("2880", "華南金"),
        ("2883", "開發金"), ("5880", "合庫金"), ("2887", "台新金"), ("2888", "新光金"),
        ("2002", "中鋼"), ("1301", "台塑"), ("1303", "南亞"), ("1326", "台化"),
        ("6505", "台塑化"), ("2207", "和泰車"), ("2105", "正新"), ("2201", "裕隆"),
        ("2357", "華碩"), ("2376", "技嘉"), ("2377", "微星"), ("3034", "聯詠"),
        ("3008", "大立光"), ("2344", "華邦電"), ("2408", "南亞科"), ("2409", "友達"),
        ("3481", "群創"), ("2352", "佳世達"), ("2324", "仁寶"), ("2312", "金寶"),
        ("2474", "可成"), ("4938", "和碩"), ("2395", "研華"), ("3045", "台灣大"),
        ("4904", "遠傳"), ("2498", "宏達電"), ("2615", "萬海"), ("2603", "長榮"),
        ("2609", "陽明"), ("5871", "中租-KY"),
    ]
    return [{"stock_id": s[0], "name": s[1], "industry": "", "market": "twse", "is_etf": False}
            for s in stocks]


def _load_cache() -> Optional[list]:
    if not _CACHE_PATH.exists():
        return None
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        saved_at = datetime.fromisoformat(data["saved_at"])
        if datetime.now() - saved_at > timedelta(hours=_CACHE_TTL_HOURS):
            return None
        return data["stocks"]
    except Exception:
        return None


def _save_cache(stocks: list) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"saved_at": datetime.now().isoformat(), "stocks": stocks}, f, ensure_ascii=False)
    except Exception:
        pass

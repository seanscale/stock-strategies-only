"""FastAPI 後端

啟動：
  uv run uvicorn api.main:app --reload --port 8000

提供：
  GET    /api/health
  GET    /api/strategies              列出所有策略
  GET    /api/strategies/defaults     回傳預設參數 schema
  GET    /api/strategies/{id}         取單一策略
  POST   /api/strategies              新增 / 更新策略
  DELETE /api/strategies/{id}         刪除
  POST   /api/strategies/generate     AI 生策略 (Gemini)
  GET    /api/market                  目前大盤狀態
  GET    /api/watchlist               讀 watchlist
  GET    /api/universe                取得全市場股票清單
  POST   /api/run                     用指定策略跑 watchlist 或全市場
  GET    /api/last-result             取得最近一次掃描結果（自動排程用）
"""

from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path
from typing import Any, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


def numpy_safe(obj):
    """Recursively convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: numpy_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [numpy_safe(i) for i in obj]
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from stock_strategies import loader
from stock_strategies.evaluate import evaluate
from stock_strategies.market import apply_market_filter, get_market_state
from stock_strategies.sheet import read_watchlist
from stock_strategies.market_universe import get_universe
from api.services.ai_generator import generate_strategy_with_ai

app = FastAPI(title="Stock Strategies API", version="2.0.0")

# CORS
_origins_env = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins_env.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 最近一次掃描結果快取路徑
_LAST_RESULT_PATH = Path(os.environ.get("CACHE_DIR", "/tmp")) / "last_scan_result.json"


# ---------- Schemas ----------

class StrategyIn(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = ""
    source: Optional[str] = "manual"
    params: dict[str, Any] = Field(default_factory=dict)


class AIGenerateIn(BaseModel):
    prompt: str = Field(..., description="使用者用自然語言描述想要的策略風格")
    name: Optional[str] = None


class RunIn(BaseModel):
    strategy_id: str
    limit: Optional[int] = Field(None, description="只跑前 N 檔（debug 用）")
    scan_mode: Optional[str] = Field("watchlist", description="'watchlist' | 'universe'")
    universe_market: Optional[str] = Field("all", description="全市場模式：'all' | 'twse' | 'tpex'")
    exclude_etf: Optional[bool] = Field(True, description="全市場模式：是否排除 ETF")


# ---------- Helper ----------

def _run_scan(strategy: dict, stock_list: list[dict], market_state: dict) -> dict:
    """共用掃描邏輯：對 stock_list 逐一 evaluate，回傳結果 dict。"""
    results = []
    for row in stock_list:
        sid = str(row["stock_id"])
        name = row.get("name", "")
        r = evaluate(sid, name, strategy=strategy)
        if r:
            results.append(r)
        time.sleep(0.3)

    params = strategy.get("params", {})
    market_filter_on = params.get("market_filter_enabled", True)
    if market_filter_on:
        downgraded = apply_market_filter(results, market_state)
    else:
        downgraded = 0

    order = {"BUY": 0, "WATCH": 1, "SKIP": 2, "ERROR": 3}
    results.sort(key=lambda x: (order.get(x.get("action"), 4), -x.get("signal_score", 0)))

    return {
        "strategy": {"id": strategy["id"], "name": strategy["name"]},
        "market": market_state,
        "downgraded": downgraded,
        "summary": {
            "total": len(results),
            "buy": sum(1 for r in results if r.get("action") == "BUY"),
            "watch": sum(1 for r in results if r.get("action") == "WATCH"),
            "skip": sum(1 for r in results if r.get("action") == "SKIP"),
            "error": sum(1 for r in results if r.get("action") == "ERROR"),
        },
        "results": results,
        "scan_mode": "watchlist",
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


# ---------- Routes ----------

@app.get("/api/health")
def health():
    return {"ok": True, "ts": int(time.time()), "version": "2.0.0"}


@app.get("/api/strategies")
def list_strategies():
    return {"strategies": loader.list_strategies()}


@app.get("/api/strategies/defaults")
def defaults():
    return {"params": loader.param_defaults()}


@app.get("/api/strategies/{sid}")
def get_strategy(sid: str):
    s = loader.get_strategy(sid)
    if not s:
        raise HTTPException(404, f"找不到策略 {sid}")
    return s


@app.post("/api/strategies")
def save_strategy(payload: StrategyIn):
    try:
        clean = loader.save_strategy(payload.model_dump())
        return clean
    except loader.StrategyError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/strategies/{sid}")
def delete_strategy(sid: str):
    if sid in ("default", "conservative"):
        raise HTTPException(400, "預設策略不可刪除")
    ok = loader.delete_strategy(sid)
    if not ok:
        raise HTTPException(404, f"找不到策略 {sid}")
    return {"ok": True}


@app.post("/api/strategies/generate")
def generate_strategy(payload: AIGenerateIn):
    try:
        strategy = generate_strategy_with_ai(payload.prompt, name=payload.name)
        return strategy
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"AI 生策略失敗：{e}")


@app.get("/api/market")
def market():
    return get_market_state()


@app.get("/api/watchlist")
def watchlist():
    try:
        return {"items": read_watchlist()}
    except Exception as e:
        return {"items": [], "error": str(e)}


@app.get("/api/universe")
def universe(
    market: str = Query("all", description="'all' | 'twse' | 'tpex'"),
    exclude_etf: bool = Query(True, description="是否排除 ETF"),
):
    """取得全市場股票清單（快取 24 小時）。"""
    try:
        stocks = get_universe(market=market, exclude_etf=exclude_etf)
        return {"total": len(stocks), "stocks": stocks}
    except Exception as e:
        raise HTTPException(500, f"取得股票清單失敗：{e}")


@app.post("/api/run")
def run(payload: RunIn):
    strategy = loader.get_strategy(payload.strategy_id)
    if not strategy:
        raise HTTPException(404, f"找不到策略 {payload.strategy_id}")

    params = strategy.get("params", {})
    market_filter_on = params.get("market_filter_enabled", True)
    if market_filter_on:
        market_state = get_market_state(int(params.get("market_filter_ma_period", 20)))
    else:
        market_state = {"bullish": True, "note": "已關閉大盤濾鏡"}

    # 決定掃描清單
    scan_mode = payload.scan_mode or "watchlist"
    if scan_mode == "universe":
        try:
            stock_list = get_universe(
                market=payload.universe_market or "all",
                exclude_etf=payload.exclude_etf if payload.exclude_etf is not None else True,
            )
        except Exception as e:
            raise HTTPException(500, f"取得全市場清單失敗：{e}")
    else:
        try:
            stock_list = read_watchlist()
        except Exception as e:
            raise HTTPException(500, f"讀取 watchlist 失敗：{e}")

    if payload.limit:
        stock_list = stock_list[: payload.limit]

    result = _run_scan(strategy, stock_list, market_state)
    result["scan_mode"] = scan_mode

    # 儲存最近一次掃描結果（供 /api/last-result 使用）
    try:
        _LAST_RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_LAST_RESULT_PATH, "w", encoding="utf-8") as f:
            json.dump(numpy_safe(result), f, ensure_ascii=False)
    except Exception:
        pass

    return JSONResponse(content=numpy_safe(result))


@app.get("/api/last-result")
def last_result():
    """取得最近一次掃描結果（用於自動排程後的前端顯示）。"""
    if not _LAST_RESULT_PATH.exists():
        return {"ok": False, "message": "尚無掃描結果"}
    try:
        with open(_LAST_RESULT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"ok": True, "result": data}
    except Exception as e:
        raise HTTPException(500, f"讀取最近結果失敗：{e}")


@app.post("/api/schedule/run")
def schedule_run(
    strategy_id: str = Query("default", description="要執行的策略 ID"),
    scan_mode: str = Query("watchlist", description="'watchlist' | 'universe'"),
    secret: str = Query("", description="排程保護 token"),
):
    """供 GitHub Actions / cron 呼叫的排程執行端點。
    
    需要設定環境變數 SCHEDULE_SECRET 來保護此端點。
    """
    expected_secret = os.environ.get("SCHEDULE_SECRET", "")
    if expected_secret and secret != expected_secret:
        raise HTTPException(403, "排程 token 不正確")

    strategy = loader.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(404, f"找不到策略 {strategy_id}")

    params = strategy.get("params", {})
    market_filter_on = params.get("market_filter_enabled", True)
    if market_filter_on:
        market_state = get_market_state(int(params.get("market_filter_ma_period", 20)))
    else:
        market_state = {"bullish": True, "note": "已關閉大盤濾鏡"}

    if scan_mode == "universe":
        stock_list = get_universe()
    else:
        try:
            stock_list = read_watchlist()
        except Exception as e:
            raise HTTPException(500, f"讀取 watchlist 失敗：{e}")

    result = _run_scan(strategy, stock_list, market_state)
    result["scan_mode"] = scan_mode
    result["triggered_by"] = "schedule"

    try:
        _LAST_RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_LAST_RESULT_PATH, "w", encoding="utf-8") as f:
            json.dump(numpy_safe(result), f, ensure_ascii=False)
    except Exception:
        pass

    return JSONResponse(content=numpy_safe({
        "ok": True,
        "summary": result["summary"],
        "scanned_at": result.get("scanned_at"),
        "buy_stocks": [
            {"stock_id": r["stock_id"], "name": r["name"], "score": r.get("signal_score")}
            for r in result["results"] if r.get("action") == "BUY"
        ],
    }))

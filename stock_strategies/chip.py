"""籌碼面分析模組
計算三大法人買超分數與月營收成長分數，整合進 evaluate.py 的評分系統。

chip_score_for(stock_id, params) → dict:
  {
    "chip_score": 0-100,
    "chip_signals": ["外資連買3日", "投信買超"],
    "chip_details": {
      "foreign_net_3d": 1234567,
      "trust_net_3d": 234567,
      "foreign_consecutive_buy_days": 3,
      "trust_consecutive_buy_days": 2,
    },
    "revenue_score": 0-100,
    "revenue_signals": ["月營收YoY+15%", "連3月成長"],
    "revenue_details": {
      "latest_yoy": 0.15,
      "latest_mom": 0.03,
      "consecutive_yoy_positive": 3,
    },
  }
"""
from __future__ import annotations
import pandas as pd
from datetime import datetime, timedelta
from .datasources import get_institutional, get_month_revenue


def chip_score_for(stock_id: str, params: dict) -> dict:
    """計算籌碼面分數（法人買超 + 月營收）。
    
    params 相關鍵：
      use_chip_score: bool (預設 True)
      chip_foreign_days: int  外資連買天數門檻 (預設 3)
      chip_trust_days: int    投信連買天數門檻 (預設 2)
      use_revenue_score: bool (預設 True)
      revenue_yoy_threshold: float  YoY 門檻 (預設 0.05 = 5%)
      revenue_consecutive_months: int 連續成長月數門檻 (預設 2)
    """
    result = {
        "chip_score": 50,  # 無資料時給中性分
        "chip_signals": [],
        "chip_details": {},
        "revenue_score": 50,
        "revenue_signals": [],
        "revenue_details": {},
    }

    use_chip = params.get("use_chip_score", True)
    use_rev = params.get("use_revenue_score", True)

    # ── 籌碼面：三大法人 ──────────────────────────────────────────
    if use_chip:
        try:
            start = (datetime.today() - timedelta(days=60)).strftime("%Y-%m-%d")
            inst_df = get_institutional(stock_id, start)
            if not inst_df.empty and len(inst_df) >= 3:
                recent = inst_df.tail(20)  # 最近 20 個交易日
                latest3 = inst_df.tail(3)

                foreign_net_3d = int(latest3["foreign_net"].sum())
                trust_net_3d = int(latest3["trust_net"].sum())
                total_net_3d = int(latest3["total_net"].sum())

                # 計算連續買超天數（外資）
                foreign_consec = _consecutive_positive(inst_df["foreign_net"])
                trust_consec = _consecutive_positive(inst_df["trust_net"])

                foreign_days_thresh = int(params.get("chip_foreign_days", 3))
                trust_days_thresh = int(params.get("chip_trust_days", 2))

                chip_score = 50.0
                signals = []

                # 外資連買加分
                if foreign_consec >= foreign_days_thresh:
                    chip_score += 25
                    signals.append(f"外資連買{foreign_consec}日")
                elif foreign_net_3d > 0:
                    chip_score += 10
                    signals.append("外資近3日買超")
                elif foreign_net_3d < 0:
                    chip_score -= 15
                    signals.append("外資近3日賣超")

                # 投信連買加分
                if trust_consec >= trust_days_thresh:
                    chip_score += 20
                    signals.append(f"投信連買{trust_consec}日")
                elif trust_net_3d > 0:
                    chip_score += 8
                    signals.append("投信近3日買超")

                # 三大法人合計
                if total_net_3d > 0 and foreign_net_3d > 0 and trust_net_3d > 0:
                    chip_score += 5
                    signals.append("三大法人齊買")

                result["chip_score"] = max(0, min(100, int(round(chip_score))))
                result["chip_signals"] = signals
                result["chip_details"] = {
                    "foreign_net_3d": foreign_net_3d,
                    "trust_net_3d": trust_net_3d,
                    "total_net_3d": total_net_3d,
                    "foreign_consecutive_buy_days": foreign_consec,
                    "trust_consecutive_buy_days": trust_consec,
                }
        except Exception:
            pass  # 籌碼資料失敗不影響整體評分

    # ── 月營收成長 ────────────────────────────────────────────────
    if use_rev:
        try:
            start = (datetime.today() - timedelta(days=400)).strftime("%Y-%m-%d")
            rev_df = get_month_revenue(stock_id, start)
            if not rev_df.empty and len(rev_df) >= 3:
                latest = rev_df.iloc[-1]
                yoy = latest.get("yoy")
                mom = latest.get("mom")

                yoy_thresh = float(params.get("revenue_yoy_threshold", 0.05))
                consec_thresh = int(params.get("revenue_consecutive_months", 2))

                # 計算連續 YoY 正成長月數
                consec_yoy = _consecutive_positive_series(rev_df["yoy"])

                rev_score = 50.0
                signals = []

                if pd.notna(yoy):
                    if yoy >= yoy_thresh * 2:  # 超過門檻 2 倍（例如 >10%）
                        rev_score += 30
                        signals.append(f"月營收YoY+{yoy*100:.0f}%")
                    elif yoy >= yoy_thresh:
                        rev_score += 15
                        signals.append(f"月營收YoY+{yoy*100:.0f}%")
                    elif yoy < -0.10:
                        rev_score -= 20
                        signals.append(f"月營收YoY{yoy*100:.0f}%")

                if consec_yoy >= consec_thresh:
                    rev_score += 15
                    signals.append(f"連{consec_yoy}月YoY成長")

                if pd.notna(mom) and mom > 0.05:
                    rev_score += 5
                    signals.append(f"月增率+{mom*100:.0f}%")

                result["revenue_score"] = max(0, min(100, int(round(rev_score))))
                result["revenue_signals"] = signals
                result["revenue_details"] = {
                    "latest_yoy": float(yoy) if pd.notna(yoy) else None,
                    "latest_mom": float(mom) if pd.notna(mom) else None,
                    "consecutive_yoy_positive": consec_yoy,
                    "latest_revenue": int(latest["revenue"]) if pd.notna(latest.get("revenue")) else None,
                    "revenue_period": f"{int(latest['revenue_year'])}/{int(latest['revenue_month']):02d}" 
                                     if pd.notna(latest.get("revenue_year")) else None,
                }
        except Exception:
            pass  # 月營收資料失敗不影響整體評分

    return result


def _consecutive_positive(series: pd.Series) -> int:
    """從最後一筆往前計算連續正值天數。"""
    count = 0
    for val in reversed(series.tolist()):
        if pd.notna(val) and val > 0:
            count += 1
        else:
            break
    return count


def _consecutive_positive_series(series: pd.Series) -> int:
    """從最後一筆往前計算連續正值月數（用於 YoY）。"""
    count = 0
    vals = [v for v in series.tolist() if pd.notna(v)]
    for val in reversed(vals):
        if val > 0:
            count += 1
        else:
            break
    return count

"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Strategy, RunResult } from "@/lib/api";
import { ActionBadge, SourceBadge } from "@/components/ActionBadge";

function ScoreBar({ score, max = 100, color }: { score: number; max?: number; color: string }) {
  const pct = Math.max(0, Math.min(100, (score / max) * 100));
  return (
    <div className="w-full bg-panel2 rounded-full h-1.5 mt-1">
      <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function StockRow({ r }: { r: any }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <div
        className="bg-panel2 border border-line rounded-lg p-3 cursor-pointer hover:border-line/80"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <ActionBadge action={r.action} />
          <div className="font-mono w-14 text-sm">{r.stock_id}</div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{r.name}</div>
            <div className="text-xs text-muted mt-0.5 truncate">
              {r.components?.tech_signals?.join(" · ") || "—"}
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className="font-mono text-sm">{r.signal_score}</div>
            <div className="text-xs text-muted">
              勝率 {r.components?.backtest_winrate != null
                ? `${(r.components.backtest_winrate * 100).toFixed(0)}%` : "—"}
            </div>
          </div>
          <div className="text-muted text-xs ml-1">{expanded ? "▲" : "▼"}</div>
        </div>
      </div>

      {expanded && (
        <div className="bg-panel2/50 border border-line border-t-0 rounded-b-lg px-4 py-3 -mt-1 space-y-3">
          {/* 評分細項 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div>
              <div className="text-muted mb-1">基本面</div>
              <div className={r.components?.fundamental_pass ? "text-buy" : "text-err"}>
                {r.components?.fundamental_pass ? "✓ 通過" : "✗ 未過"}
              </div>
              <div className="text-muted mt-0.5">
                EPS {r.components?.eps_min?.toFixed(1) ?? "—"} · ROE {r.components?.roe_min?.toFixed(1) ?? "—"}%
              </div>
            </div>
            <div>
              <div className="text-muted mb-1">技術面 {r.components?.tech_score ?? "—"}</div>
              <ScoreBar score={r.components?.tech_score ?? 0} color="bg-blue-500" />
            </div>
            <div>
              <div className="text-muted mb-1">籌碼面 {r.components?.chip_score ?? "—"}</div>
              <ScoreBar score={r.components?.chip_score ?? 50} color="bg-purple-500" />
              {r.components?.chip_signals?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {r.components.chip_signals.map((s: string) => (
                    <span key={s} className="text-[10px] bg-purple-900/40 text-purple-300 border border-purple-700/40 px-1.5 py-0.5 rounded">{s}</span>
                  ))}
                </div>
              )}
            </div>
            <div>
              <div className="text-muted mb-1">月營收 {r.components?.revenue_score ?? "—"}</div>
              <ScoreBar score={r.components?.revenue_score ?? 50} color="bg-green-500" />
              {r.components?.revenue_signals?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {r.components.revenue_signals.map((s: string) => (
                    <span key={s} className="text-[10px] bg-green-900/40 text-green-300 border border-green-700/40 px-1.5 py-0.5 rounded">{s}</span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 籌碼細節 */}
          {r.components?.chip_details && (
            <div className="text-xs text-muted">
              外資近3日：{r.components.chip_details.foreign_net_3d?.toLocaleString() ?? "—"} 股 ·
              投信近3日：{r.components.chip_details.trust_net_3d?.toLocaleString() ?? "—"} 股
            </div>
          )}

          {/* 月營收細節 */}
          {r.components?.revenue_details?.revenue_period && (
            <div className="text-xs text-muted">
              {r.components.revenue_details.revenue_period} 月營收
              {r.components.revenue_details.latest_revenue
                ? ` ${(r.components.revenue_details.latest_revenue / 1e8).toFixed(1)} 億`
                : ""}
              {r.components.revenue_details.latest_yoy != null
                ? ` · YoY ${(r.components.revenue_details.latest_yoy * 100).toFixed(1)}%`
                : ""}
            </div>
          )}

          {/* 趨勢 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div>
              <div className="text-muted">5日漲跌</div>
              <div className={r.trend?.chg_5d >= 0 ? "text-buy" : "text-err"}>
                {r.trend?.chg_5d >= 0 ? "+" : ""}{r.trend?.chg_5d?.toFixed(2)}%
              </div>
            </div>
            <div>
              <div className="text-muted">20日漲跌</div>
              <div className={r.trend?.chg_20d >= 0 ? "text-buy" : "text-err"}>
                {r.trend?.chg_20d >= 0 ? "+" : ""}{r.trend?.chg_20d?.toFixed(2)}%
              </div>
            </div>
            <div>
              <div className="text-muted">量比(5/20日)</div>
              <div>{r.trend?.vol_ratio?.toFixed(2)}x</div>
            </div>
            <div>
              <div className="text-muted">距52週高點</div>
              <div className={r.trend?.pct_from_high >= -10 ? "text-buy" : "text-muted"}>
                {r.trend?.pct_from_high?.toFixed(1)}%
              </div>
            </div>
          </div>

          <div className="text-xs bg-panel2 border border-line rounded p-2">
            <span className="text-muted">進場規則：</span>{r.entry_rule}
            <span className="ml-2 text-muted">
              目標 {r.target_price} · 停損 {r.stop_loss_price} · R/R {r.risk_reward_ratio}
            </span>
          </div>

          {r.risk_notes?.length > 0 && (
            <div className="text-xs text-yellow-400/80">⚠ {r.risk_notes.join(" · ")}</div>
          )}

          {/* 外部連結 */}
          <div className="flex gap-3 text-xs">
            <a href={`https://goodinfo.tw/tw/StockDetail.aspx?STOCK_ID=${r.stock_id}`}
              target="_blank" rel="noopener noreferrer"
              className="text-blue-400 hover:underline" onClick={(e) => e.stopPropagation()}>
              Goodinfo ↗
            </a>
            <a href={`https://tw.stock.yahoo.com/quote/${r.stock_id}`}
              target="_blank" rel="noopener noreferrer"
              className="text-blue-400 hover:underline" onClick={(e) => e.stopPropagation()}>
              Yahoo 股市 ↗
            </a>
            <a href={`https://www.twse.com.tw/zh/stock/code/${r.stock_id}`}
              target="_blank" rel="noopener noreferrer"
              className="text-blue-400 hover:underline" onClick={(e) => e.stopPropagation()}>
              公開資訊 ↗
            </a>
          </div>
        </div>
      )}
    </>
  );
}

export default function Dashboard() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [picked, setPicked] = useState<string>("default");
  const [market, setMarket] = useState<any>(null);
  const [watchCount, setWatchCount] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanMode, setScanMode] = useState<"watchlist" | "universe">("watchlist");
  const [lastResult, setLastResult] = useState<RunResult | null>(null);
  const [showLastResult, setShowLastResult] = useState(false);

  useEffect(() => {
    api.listStrategies().then((d) => {
      setStrategies(d.strategies);
      if (d.strategies.find((s) => s.id === "default")) setPicked("default");
      else if (d.strategies[0]) setPicked(d.strategies[0].id);
    });
    api.getMarket().then(setMarket).catch(() => setMarket(null));
    api.getWatchlist().then((w) => setWatchCount(w.items?.length ?? 0)).catch(() => setWatchCount(null));
    api.getLastResult().then((r) => {
      if (r.ok && r.result) setLastResult(r.result);
    }).catch(() => {});
  }, []);

  async function doRun() {
    setRunning(true);
    setError(null);
    setRun(null);
    setShowLastResult(false);
    try {
      const r = await api.run(picked, { scan_mode: scanMode });
      setRun(r);
      setLastResult(r);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  const selected = strategies.find((s) => s.id === picked);
  const displayResult = showLastResult ? lastResult : run;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted mt-1">選一個策略，按下執行即可掃描股票清單。</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="text-xs text-muted">大盤狀態</div>
          {market ? (
            <>
              <div className={"text-2xl font-semibold mt-2 " + (market.bullish ? "text-buy" : "text-err")}>
                {market.bullish ? "🟢 多頭" : "🔴 空頭"}
              </div>
              <div className="text-xs text-muted mt-2 leading-relaxed">{market.note}</div>
            </>
          ) : (
            <div className="text-muted mt-2 text-sm">載入中…</div>
          )}
        </div>
        <div className="card">
          <div className="text-xs text-muted">Watchlist</div>
          <div className="text-2xl font-semibold mt-2">{watchCount ?? "—"} 檔</div>
          <div className="text-xs text-muted mt-2">來自 Google Sheet</div>
        </div>
        <div className="card">
          <div className="text-xs text-muted">可用策略</div>
          <div className="text-2xl font-semibold mt-2">{strategies.length}</div>
          <div className="text-xs text-muted mt-2">
            <Link href="/strategies/ai" className="hover:text-text underline-offset-4 hover:underline">+ AI 生一個</Link>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="font-medium mb-4">執行今日選股</h2>

        {/* 掃描模式切換 */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setScanMode("watchlist")}
            className={`text-xs px-3 py-1.5 rounded border transition-colors ${
              scanMode === "watchlist"
                ? "bg-blue-600/30 border-blue-500/60 text-blue-300"
                : "border-line text-muted hover:text-text"
            }`}
          >
            📋 Watchlist（{watchCount ?? "—"} 檔）
          </button>
          <button
            onClick={() => setScanMode("universe")}
            className={`text-xs px-3 py-1.5 rounded border transition-colors ${
              scanMode === "universe"
                ? "bg-orange-600/30 border-orange-500/60 text-orange-300"
                : "border-line text-muted hover:text-text"
            }`}
          >
            🌐 全市場掃描
          </button>
        </div>

        {scanMode === "universe" && (
          <div className="text-xs text-yellow-400/80 bg-yellow-900/20 border border-yellow-700/30 rounded p-2 mb-4">
            ⚠ 全市場掃描約 1,700+ 支股票，預計需要 30-60 分鐘，建議使用排程功能。
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-end">
          <div>
            <label className="label">選擇策略</label>
            <select className="input" value={picked} onChange={(e) => setPicked(e.target.value)}>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>{s.name}（{s.id}）</option>
              ))}
            </select>
            {selected && (
              <div className="flex items-center gap-2 mt-2 text-xs">
                <SourceBadge source={selected.source} />
                <span className="text-muted">{selected.description}</span>
              </div>
            )}
          </div>
          <button onClick={doRun} disabled={running || !picked} className="btn-primary h-10">
            {running
              ? scanMode === "universe" ? "全市場掃描中…" : "執行中…可能要一兩分鐘"
              : "▶ 執行"}
          </button>
        </div>
        {error && <div className="text-sm text-err mt-3">錯誤：{error}</div>}

        {/* 最近一次結果提示 */}
        {!run && lastResult && (
          <div className="mt-3 text-xs text-muted">
            最近一次掃描：{lastResult.scanned_at || "—"}（{lastResult.strategy?.name}）
            <button
              onClick={() => setShowLastResult(!showLastResult)}
              className="ml-2 text-blue-400 hover:underline"
            >
              {showLastResult ? "隱藏" : "查看結果"}
            </button>
          </div>
        )}
      </div>

      {/* 結果顯示 */}
      {displayResult && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-medium">
              執行結果
              {showLastResult && <span className="text-xs text-muted ml-2">（最近一次）</span>}
            </h2>
            <div className="flex gap-2 text-xs">
              <span className="badge-buy">BUY {displayResult.summary.buy}</span>
              <span className="badge-watch">WATCH {displayResult.summary.watch}</span>
              <span className="badge-skip">SKIP {displayResult.summary.skip}</span>
              {displayResult.summary.error > 0 && (
                <span className="badge-err">ERR {displayResult.summary.error}</span>
              )}
            </div>
          </div>
          <div className="text-xs text-muted mb-3">
            {displayResult.market.note}
            {displayResult.scan_mode === "universe" && (
              <span className="ml-2 text-orange-400">· 全市場掃描</span>
            )}
          </div>

          {/* BUY 股票優先展示 */}
          {displayResult.results.filter((r) => r.action === "BUY").length > 0 && (
            <div className="mb-4">
              <div className="text-xs text-muted mb-2 font-medium">🟢 BUY 訊號</div>
              <div className="space-y-2">
                {displayResult.results
                  .filter((r) => r.action === "BUY")
                  .map((r) => <StockRow key={r.stock_id} r={r} />)}
              </div>
            </div>
          )}

          {/* WATCH 股票 */}
          {displayResult.results.filter((r) => r.action === "WATCH").length > 0 && (
            <div className="mb-4">
              <div className="text-xs text-muted mb-2 font-medium">🟡 WATCH 觀察</div>
              <div className="space-y-2">
                {displayResult.results
                  .filter((r) => r.action === "WATCH")
                  .map((r) => <StockRow key={r.stock_id} r={r} />)}
              </div>
            </div>
          )}

          {/* SKIP 股票（摺疊） */}
          {displayResult.results.filter((r) => r.action === "SKIP").length > 0 && (
            <details className="mt-2">
              <summary className="text-xs text-muted cursor-pointer hover:text-text">
                ⬜ SKIP {displayResult.results.filter((r) => r.action === "SKIP").length} 檔（點擊展開）
              </summary>
              <div className="space-y-2 mt-2">
                {displayResult.results
                  .filter((r) => r.action === "SKIP")
                  .map((r) => <StockRow key={r.stock_id} r={r} />)}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

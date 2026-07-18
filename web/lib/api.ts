// 若設了 NEXT_PUBLIC_API_BASE 就直接打 FastAPI（避開 Next dev proxy 的 socket hang up），
// 否則走 next.config rewrites 代理。長請求如 /api/run 強烈建議走直連。
const BASE = process.env.NEXT_PUBLIC_API_BASE || "";

export type Strategy = {
  id: string;
  name: string;
  description?: string;
  source?: "default" | "manual" | "ai";
  created_at?: string;
  updated_at?: string;
  params: Record<string, any>;
};

export type StockResult = {
  stock_id: string;
  name: string;
  date: string;
  action: "BUY" | "WATCH" | "SKIP" | "ERROR";
  signal_score: number;
  strategy_id: string;
  risk_notes: string[];
  components: {
    fundamental_pass: boolean;
    eps_min: number | null;
    roe_min: number | null;
    tech_score: number;
    tech_signals: string[];
    backtest_winrate: number;
    backtest_samples: number;
    volume_patterns: string[];
    volume_verdict: string;
    volume_bonus: number;
    // 新增：籌碼面
    chip_score?: number;
    chip_signals?: string[];
    chip_details?: {
      foreign_net_3d?: number;
      trust_net_3d?: number;
      total_net_3d?: number;
      foreign_consecutive_buy_days?: number;
      trust_consecutive_buy_days?: number;
    };
    // 新增：月營收
    revenue_score?: number;
    revenue_signals?: string[];
    revenue_details?: {
      latest_yoy?: number | null;
      latest_mom?: number | null;
      consecutive_yoy_positive?: number;
      latest_revenue?: number | null;
      revenue_period?: string | null;
    };
  };
  trend: {
    chg_5d: number;
    chg_20d: number;
    vol_ratio: number;
    pct_from_high: number;
    above_ma20: boolean;
    above_ma60: boolean;
  };
  entry_price: number;
  stop_loss_price: number;
  target_price: number;
  risk_reward_ratio: number;
  position_size_pct: number;
  entry_rule: string;
};

export type RunResult = {
  strategy: { id: string; name: string };
  market: { bullish: boolean; close: number | null; ma20: number | null; note: string };
  downgraded: number;
  summary: { total: number; buy: number; watch: number; skip: number; error: number };
  results: StockResult[];
  scan_mode?: string;
  scanned_at?: string;
};

async function jfetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail || ""; } catch {}
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listStrategies: () => jfetch<{ strategies: Strategy[] }>("/api/strategies"),
  getDefaults: () => jfetch<{ params: Record<string, any> }>("/api/strategies/defaults"),
  getStrategy: (id: string) => jfetch<Strategy>(`/api/strategies/${id}`),
  saveStrategy: (s: Partial<Strategy>) =>
    jfetch<Strategy>("/api/strategies", { method: "POST", body: JSON.stringify(s) }),
  deleteStrategy: (id: string) =>
    jfetch<{ ok: boolean }>(`/api/strategies/${id}`, { method: "DELETE" }),
  generateAI: (prompt: string, name?: string) =>
    jfetch<Strategy>("/api/strategies/generate", {
      method: "POST",
      body: JSON.stringify({ prompt, name }),
    }),
  getMarket: () => jfetch<any>("/api/market"),
  getWatchlist: () => jfetch<{ items: any[]; error?: string }>("/api/watchlist"),
  getUniverse: (market?: string) =>
    jfetch<{ total: number; stocks: any[] }>(`/api/universe?market=${market || "all"}`),
  getLastResult: () =>
    jfetch<{ ok: boolean; result?: RunResult; message?: string }>("/api/last-result"),
  run: (
    strategy_id: string,
    options?: { limit?: number; scan_mode?: "watchlist" | "universe"; universe_market?: string }
  ) =>
    jfetch<RunResult>("/api/run", {
      method: "POST",
      body: JSON.stringify({
        strategy_id,
        limit: options?.limit,
        scan_mode: options?.scan_mode || "watchlist",
        universe_market: options?.universe_market || "all",
      }),
    }),
};

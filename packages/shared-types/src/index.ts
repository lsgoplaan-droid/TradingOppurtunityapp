// ─── Core market data ────────────────────────────────────────────────────────

export interface OHLCVBar {
  timestamp: number; // Unix ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ─── Options ─────────────────────────────────────────────────────────────────

export interface OptionsContract {
  strike: number;
  expiry: string; // ISO date
  optionType: 'CE' | 'PE';
  ltp: number;
  iv: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  oi: number;
  volume: number;
}

export interface OptionsChain {
  underlying: string;
  expiry: string;
  spot: number;
  calls: OptionsContract[];
  puts: OptionsContract[];
}

// ─── Scan ─────────────────────────────────────────────────────────────────────

export type Market = 'US' | 'INDIA';
export type AssetClass = 'EQUITY' | 'EQUITY_OPTIONS';

export interface ScanResult {
  id: string;
  symbol: string;
  market: Market;
  assetClass: AssetClass;
  signalName: string;
  templateId: string;
  timeframe: string;
  triggeredTimeframes?: string[]; // for MTF scans
  strengthScore: number; // 0–100
  timestamp: number; // Unix ms
  indicatorValues: Record<string, number>;
  // options-specific (optional)
  ivRank?: number;
  ivPercentile?: number;
  pcr?: number;
  maxPain?: number;
}

// ─── Backtest ─────────────────────────────────────────────────────────────────

export interface Trade {
  entryDate: string;
  exitDate: string;
  direction: 'LONG' | 'SHORT';
  entryPrice: number;
  exitPrice: number;
  pnl: number;
  pnlPct: number;
}

export interface BacktestResult {
  id: string;
  symbol: string;
  strategyName: string;
  startDate: string;
  endDate: string;
  totalReturn: number;
  cagr: number;
  sharpe: number;
  sortino: number;
  maxDrawdown: number;
  winRate: number;
  profitFactor: number;
  avgTradeDuration: number; // days
  equityCurve: { timestamp: number; value: number }[];
  drawdownCurve: { timestamp: number; value: number }[];
  trades: Trade[];
}

// ─── Watchlist ────────────────────────────────────────────────────────────────

export interface Watchlist {
  id: string;
  name: string;
  symbols: string[];
  market: Market | 'ALL';
}

// ─── API request/response shapes ──────────────────────────────────────────────

export interface ScanRunRequest {
  templateId: string;
  universe?: string[]; // if empty, use default universe
  watchlistId?: string;
}

export interface BacktestRunRequest {
  symbol: string;
  templateId: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  positionSizing: 'fixed' | 'pct_equity' | 'kelly';
  commissionPct: number;
}

export interface BacktestJobStatus {
  jobId: string;
  status: 'pending' | 'running' | 'complete' | 'failed';
  resultId?: string;
  error?: string;
}

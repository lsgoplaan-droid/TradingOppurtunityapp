import { Platform } from 'react-native';

// Android emulator routes localhost to 10.0.2.2 (the host machine)
const API_BASE =
  Platform.OS === 'android'
    ? 'http://10.0.2.2:8000'
    : 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Shared interfaces (mirror of web/src/api/client.ts)
// ---------------------------------------------------------------------------

export interface ScanTemplate {
  id: string;
  name: string;
  description: string;
  market: 'US' | 'INDIA';
  assetClass: 'EQUITY' | 'EQUITY_OPTIONS';
  timeframe: string;
  type?: 'standard' | 'mtf';
  timeframes?: string[];
}

export interface ScanResult {
  id: string;
  symbol: string;
  market: string;
  assetClass: string;
  signalName: string;
  templateId: string;
  timeframe: string;
  strengthScore: number;
  timestamp: number;
  indicatorValues: Record<string, number>;
  direction?: 'BUY' | 'SELL' | 'NEUTRAL';
  entryPrice?: number;
  strikePrice?: number;
  optionPremium?: number;
  profitProbability?: number;
  suggestedSpread?: 'LONG_CALL_SPREAD' | 'LONG_PUT_SPREAD' | null;
  spreadDebit?: number;
  spreadWidth?: number;
  spreadMaxProfit?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  ivRank?: number;
  ivRecommendation?: 'BUY_PREMIUM' | 'SELL_PREMIUM' | 'NEUTRAL' | null;
  ivPercentile?: number;
  pcr?: number;
  maxPain?: number;
  signalCount?: number;
  stopLoss?: number;
  targetPrice?: number;
  riskReward?: number;
  supportLevels?: number[];
  resistanceLevels?: number[];
  recentCandles?: { t: number; c: number }[];
  triggeredTimeframes?: string[];
  expectedValue?: number;
}

export interface ScanRunRequest {
  templateId: string;
  symbols?: string[];
}

export interface BacktestStrategy {
  id: string;
  name: string;
  description: string;
  assetClass?: 'EQUITY' | 'EQUITY_OPTIONS';
}

export interface BacktestJobStatus {
  jobId: string;
  status: 'pending' | 'running' | 'complete' | 'failed';
  resultId?: string;
  error?: string;
}

export interface Trade {
  entryDate: string;
  exitDate: string;
  direction: 'LONG' | 'SHORT';
  entryPrice: number;
  exitPrice: number;
  pnl: number;
  pnlPct: number;
  stockPrice?: number;
  strikePrice?: number;
  strikePrice2?: number;
  strikeLong1?: number;
  strikeLong2?: number;
  leg1Premium?: number;
  leg2Premium?: number;
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
  avgTradeDuration: number;
  pctExpiredWorthless?: number;
  avgDteAtExit?: number;
  equityCurve: { timestamp: number; value: number }[];
  drawdownCurve: { timestamp: number; value: number }[];
  trades: Trade[];
}

export interface BacktestRunRequest {
  symbol: string;
  templateId: string;
  startDate: string;
  endDate: string;
  initialCapital: number;
  positionSizing: 'fixed' | 'pct_equity' | 'kelly';
  commissionPct: number;
  market: 'US' | 'INDIA';
  assetClass: 'EQUITY' | 'EQUITY_OPTIONS';
  optionsStrategy?: string;
  expiryDays?: number;
  strikeOffsetPct?: number;
  wingWidthPct?: number;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function fetchTemplates(market?: string): Promise<ScanTemplate[]> {
  const url =
    market === 'INDIA'
      ? `${API_BASE}/api/india-scan/templates`
      : `${API_BASE}/api/scan/templates`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch templates: ${res.status}`);
  return res.json();
}

export async function runScan(
  request: ScanRunRequest,
  market?: string
): Promise<ScanResult[]> {
  const url =
    market === 'INDIA'
      ? `${API_BASE}/api/india-scan/run`
      : `${API_BASE}/api/scan/run`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error(`Scan failed: ${res.status}`);
  return res.json();
}

export async function runMTFScan(
  templateId: string,
  market?: string
): Promise<ScanResult[]> {
  const url =
    market === 'INDIA'
      ? `${API_BASE}/api/india-scan/run-mtf`
      : `${API_BASE}/api/scan/run-mtf`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ templateId }),
  });
  if (!res.ok) throw new Error(`MTF scan failed: ${res.status}`);
  return res.json();
}

export async function fetchStrategies(): Promise<BacktestStrategy[]> {
  const res = await fetch(`${API_BASE}/api/backtest/strategies`);
  if (!res.ok) throw new Error(`Failed to fetch strategies: ${res.status}`);
  return res.json();
}

export async function submitBacktest(
  request: BacktestRunRequest
): Promise<BacktestJobStatus> {
  const res = await fetch(`${API_BASE}/api/backtest/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error(`Failed to submit backtest: ${res.status}`);
  return res.json();
}

export async function pollBacktestStatus(
  jobId: string
): Promise<BacktestJobStatus> {
  const res = await fetch(`${API_BASE}/api/backtest/status/${jobId}`);
  if (!res.ok) throw new Error(`Failed to poll status: ${res.status}`);
  return res.json();
}

export async function fetchBacktestResult(
  jobId: string
): Promise<BacktestResult> {
  const res = await fetch(`${API_BASE}/api/backtest/result/${jobId}`);
  if (!res.ok) throw new Error(`Failed to fetch result: ${res.status}`);
  return res.json();
}

import { useState } from 'react';
import { BacktestResult, Trade } from '../api/client';
import { EquityCurveChart } from './EquityCurveChart';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const fmt = (v: number, dec = 2) => `$${v.toFixed(dec)}`;

// ---------------------------------------------------------------------------
// Options execution panel — per-strategy legs with actual strike + premium
// ---------------------------------------------------------------------------

const OPTS_STRATEGIES = new Set([
  'long_call', 'long_put', 'straddle', 'strangle',
  'iron_condor', 'covered_call', 'zero_dte_straddle', 'zero_dte_strangle',
]);

function LegRow({ label, strike, premium, action, color = 'text-gray-700' }: {
  label: string; strike: number; premium: number; action: string; color?: string;
}) {
  return (
    <div className="flex items-center gap-2 py-1 border-b border-gray-100 last:border-0">
      <span className={`text-xs font-semibold w-16 shrink-0 ${color}`}>{action}</span>
      <span className="text-xs text-gray-600 flex-1">{label}</span>
      <span className="text-xs font-mono text-gray-800 w-16 text-right">K = {fmt(strike)}</span>
      <span className="text-xs font-mono text-purple-700 w-20 text-right">{fmt(premium)}/sh</span>
    </div>
  );
}

function ExitRow({ label, exitPremium, note }: { label: string; exitPremium: number; note: string }) {
  return (
    <div className="flex items-start gap-2 py-1 border-b border-gray-100 last:border-0">
      <span className="text-xs font-semibold w-16 shrink-0 text-green-700">{label}</span>
      <span className="text-xs text-gray-600 flex-1">{note}</span>
      <span className="text-xs font-mono text-green-700 w-20 text-right">{fmt(exitPremium)}/sh</span>
    </div>
  );
}

function OptionsExecutionPanel({ stratKey, trade, symbol }: {
  stratKey: string; trade: Trade; symbol: string;
}) {
  const S  = trade.stockPrice   ?? 0;
  const K  = trade.strikePrice  ?? 0;
  const K2 = trade.strikePrice2 ?? 0;
  const KL1 = trade.strikeLong1 ?? 0;
  const KL2 = trade.strikeLong2 ?? 0;
  const ep  = trade.entryPrice;   // total premium per share (or net credit)
  const l1  = trade.leg1Premium ?? 0;
  const l2  = trade.leg2Premium ?? 0;
  const profitTarget = ep * 1.5;     // 50% profit = exit at 1.5× for long; 0.5× for short
  const stopLoss     = ep * 0.5;     // 50% stop for long options
  const condorBuyback = ep * 0.5;    // buy back at 50% of credit for condor

  if (stratKey === 'long_call') {
    return (
      <div className="text-xs space-y-1">
        <LegRow label={`${symbol} ATM Call`} strike={K} premium={ep} action="BUY" color="text-blue-700" />
        <ExitRow label="Target" exitPremium={profitTarget}
          note={`Sell call when premium ≥ ${fmt(profitTarget)}/sh (+50% profit)`} />
        <ExitRow label="Stop" exitPremium={stopLoss}
          note={`Exit if premium falls to ${fmt(stopLoss)}/sh (50% loss on premium)`} />
        {S > 0 && <p className="text-gray-400 pt-1">Underlying at entry: {fmt(S)} · Strike: {fmt(K)}</p>}
      </div>
    );
  }

  if (stratKey === 'long_put') {
    return (
      <div className="text-xs space-y-1">
        <LegRow label={`${symbol} ATM Put`} strike={K} premium={ep} action="BUY" color="text-blue-700" />
        <ExitRow label="Target" exitPremium={profitTarget}
          note={`Sell put when premium ≥ ${fmt(profitTarget)}/sh (+50% profit)`} />
        <ExitRow label="Stop" exitPremium={stopLoss}
          note={`Exit if premium falls to ${fmt(stopLoss)}/sh (50% loss on premium)`} />
        {S > 0 && <p className="text-gray-400 pt-1">Underlying at entry: {fmt(S)} · Strike: {fmt(K)}</p>}
      </div>
    );
  }

  if (stratKey === 'straddle' || stratKey === 'zero_dte_straddle') {
    const breakeven = K + ep;
    const breakeven2 = K - ep;
    return (
      <div className="text-xs space-y-1">
        <LegRow label={`${symbol} ATM Call`} strike={K} premium={l1 || ep / 2} action="BUY" color="text-blue-700" />
        <LegRow label={`${symbol} ATM Put`}  strike={K} premium={l2 || ep / 2} action="BUY" color="text-blue-700" />
        <ExitRow label="Target" exitPremium={profitTarget}
          note={`Exit both legs when combined ≥ ${fmt(profitTarget)}/sh`} />
        <ExitRow label="Stop" exitPremium={stopLoss}
          note={`Exit if combined value ≤ ${fmt(stopLoss)}/sh`} />
        {S > 0 && (
          <p className="text-gray-400 pt-1">
            Break-even: above {fmt(breakeven)} or below {fmt(breakeven2)}
            {stratKey === 'zero_dte_straddle' ? ' · Same-day expiry' : ''}
          </p>
        )}
      </div>
    );
  }

  if (stratKey === 'strangle' || stratKey === 'zero_dte_strangle') {
    return (
      <div className="text-xs space-y-1">
        <LegRow label={`${symbol} OTM Call`} strike={K} premium={l1 || ep / 2} action="BUY" color="text-blue-700" />
        <LegRow label={`${symbol} OTM Put`}  strike={K2 || K * 0.98} premium={l2 || ep / 2} action="BUY" color="text-blue-700" />
        <ExitRow label="Target" exitPremium={profitTarget}
          note={`Exit both legs when combined ≥ ${fmt(profitTarget)}/sh`} />
        <ExitRow label="Stop" exitPremium={stopLoss}
          note={`Exit if combined value ≤ ${fmt(stopLoss)}/sh`} />
        {S > 0 && (
          <p className="text-gray-400 pt-1">
            Underlying at entry: {fmt(S)}
            {stratKey === 'zero_dte_strangle' ? ' · Same-day expiry' : ''}
          </p>
        )}
      </div>
    );
  }

  if (stratKey === 'iron_condor') {
    const wingWidth = KL1 > 0 ? KL1 - K : K * 0.05;
    const maxLoss = wingWidth - ep;
    return (
      <div className="text-xs space-y-1">
        <LegRow label={`${symbol} OTM Call (SELL)`} strike={K}  premium={ep / 2} action="SELL" color="text-red-600" />
        <LegRow label={`${symbol} OTM Call (BUY)`}  strike={KL1 || K * 1.05} premium={0} action="BUY" color="text-blue-700" />
        <LegRow label={`${symbol} OTM Put (SELL)`}  strike={K2 || K * 0.95} premium={ep / 2} action="SELL" color="text-red-600" />
        <LegRow label={`${symbol} OTM Put (BUY)`}   strike={KL2 || K * 0.90} premium={0} action="BUY" color="text-blue-700" />
        <ExitRow label="Target" exitPremium={condorBuyback}
          note={`Buy back all 4 legs when condor ≤ ${fmt(condorBuyback)}/sh (50% profit)`} />
        <ExitRow label="Stop" exitPremium={ep * 2}
          note={`Exit if condor value exceeds ${fmt(ep * 2)}/sh (2× credit received)`} />
        {S > 0 && (
          <p className="text-gray-400 pt-1">
            Net credit: {fmt(ep)}/sh · Max loss: {maxLoss > 0 ? fmt(maxLoss) : 'N/A'}/sh · Profit zone: {fmt(K2 || K * 0.95)}–{fmt(K)}
          </p>
        )}
      </div>
    );
  }

  if (stratKey === 'covered_call') {
    const monthlyIncomePct = S > 0 ? ((l1 || ep) / S * 100).toFixed(1) : '?';
    return (
      <div className="text-xs space-y-1">
        <LegRow label={`Buy 100 × ${symbol} shares`} strike={S} premium={S} action="BUY" color="text-blue-700" />
        <LegRow label={`${symbol} OTM Call (SELL)`}  strike={K} premium={l1 || ep} action="SELL" color="text-red-600" />
        <div className="flex items-start gap-2 py-1 border-b border-gray-100">
          <span className="text-xs font-semibold w-16 shrink-0 text-green-700">Expiry</span>
          <span className="text-xs text-gray-600 flex-1">
            If {symbol} &lt; {fmt(K)} at expiry: keep shares + {fmt(l1 || ep)}/sh premium income
          </span>
        </div>
        <div className="flex items-start gap-2 py-1">
          <span className="text-xs font-semibold w-16 shrink-0 text-orange-600">Called</span>
          <span className="text-xs text-gray-600 flex-1">
            If {symbol} ≥ {fmt(K)} at expiry: shares called away at {fmt(K)} — upside capped
          </span>
        </div>
        {S > 0 && (
          <p className="text-gray-400 pt-1">
            Monthly income: ~{fmt(l1 || ep)}/sh ({monthlyIncomePct}% of stock price)
          </p>
        )}
      </div>
    );
  }

  // Fallback for equity strategies with no options data
  return null;
}

// ---------------------------------------------------------------------------
// Equity entry rules (static lookup)
// ---------------------------------------------------------------------------

const EQUITY_ENTRY: Record<string, string> = {
  golden_cross:        'Enter when the 50-day EMA crosses above the 200-day EMA. Confirm with a daily close above both EMAs.',
  rsi_mean_reversion:  'Enter when RSI(14) drops below 30 and then crosses back above 30 on the next bar. Confirm with a bullish candle.',
  macd_trend:          'Enter when the MACD line crosses above the signal line. Strongest when the histogram turns positive.',
  bollinger_reversion: 'Enter when price touches or pierces the lower Bollinger Band and closes back inside the band.',
};

function TradingInstructions({ result }: { result: BacktestResult }) {
  const stratKey = result.strategyName.toLowerCase().replace(/[^a-z0-9]/g, '_');
  const isOptions = OPTS_STRATEGIES.has(stratKey);
  const equityEntryText = !isOptions
    ? (EQUITY_ENTRY[stratKey] ?? `Apply the ${result.strategyName} entry rules on ${result.symbol}.`)
    : null;

  // Representative trade — last trade with options data (or last trade overall)
  const repTrade: Trade | undefined = isOptions
    ? (result.trades.slice().reverse().find(t => t.strikePrice != null) ?? result.trades[result.trades.length - 1])
    : undefined;

  const winPct = (result.winRate * 100).toFixed(0);
  const pf = result.profitFactor.toFixed(2);
  const n = result.trades.length;

  // Edge — derived from actual profitFactor + winRate
  const edge = result.profitFactor >= 1.5 && result.winRate >= 0.5 ? 'strong'
    : result.profitFactor >= 1.0 && result.winRate >= 0.4 ? 'moderate'
    : 'weak';

  const edgeBg = edge === 'strong' ? 'bg-green-50 border-green-200 text-green-800'
    : edge === 'moderate' ? 'bg-yellow-50 border-yellow-200 text-yellow-800'
    : 'bg-red-50 border-red-200 text-red-700';
  const edgeIcon = edge === 'strong' ? '✅' : edge === 'moderate' ? '⚠️' : '❌';
  const edgeLabel = edge === 'strong' ? 'Strong edge' : edge === 'moderate' ? 'Moderate edge — trade small' : 'Weak edge — paper trade only';

  // Position sizing — half-kelly
  const avgRR = result.profitFactor > 0 ? result.profitFactor : 1.0;
  const kelly = result.winRate - (1 - result.winRate) / avgRR;
  const suggestedRisk = Math.min(Math.max(kelly * 0.5 * 100, 0.5), 3.0).toFixed(1);

  const stopPct = (result.maxDrawdown * 0.6 * 100).toFixed(1);

  // Average hold time
  const avgDuration = result.avgTradeDuration != null
    ? result.avgTradeDuration < 2
      ? 'intraday'
      : `${result.avgTradeDuration.toFixed(0)} bars`
    : 'varies';

  // Trade frequency — approximate trades per month from date range
  let tradesPerMonth = '';
  if (n > 0 && result.startDate && result.endDate) {
    const ms = new Date(result.endDate).getTime() - new Date(result.startDate).getTime();
    const months = ms / (1000 * 60 * 60 * 24 * 30.4);
    if (months > 0) tradesPerMonth = `~${(n / months).toFixed(1)}/mo`;
  }

  // Winning / losing trade stats from trade list
  const winners = result.trades.filter(t => t.pnl >= 0);
  const losers  = result.trades.filter(t => t.pnl < 0);
  const avgWinPct = winners.length
    ? (winners.reduce((s, t) => s + t.pnlPct, 0) / winners.length).toFixed(1)
    : null;
  const avgLossPct = losers.length
    ? (Math.abs(losers.reduce((s, t) => s + t.pnlPct, 0) / losers.length)).toFixed(1)
    : null;

  return (
    <div className="mt-4 border border-gray-200 rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
          Trading Plan — {result.symbol} · {result.strategyName}
        </span>
      </div>
      <div className="px-4 py-3 space-y-3 text-sm">

        {/* Edge banner with live numbers */}
        <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-xs ${edgeBg}`}>
          <span className="text-base leading-none mt-0.5">{edgeIcon}</span>
          <div>
            <span className="font-semibold">{edgeLabel}.</span>{' '}
            {n} trades · {winPct}% win rate · {pf}× profit factor
            {tradesPerMonth ? ` · ${tradesPerMonth}` : ''}
          </div>
        </div>

        {/* Win / loss averages */}
        {(avgWinPct !== null || avgLossPct !== null) && (
          <div className="flex gap-4 text-xs">
            {avgWinPct !== null && (
              <span className="text-green-700">Avg win: <strong>+{avgWinPct}%</strong></span>
            )}
            {avgLossPct !== null && (
              <span className="text-red-600">Avg loss: <strong>-{avgLossPct}%</strong></span>
            )}
            {avgWinPct !== null && avgLossPct !== null && (
              <span className="text-gray-500">
                Payoff: <strong>{(parseFloat(avgWinPct) / parseFloat(avgLossPct)).toFixed(2)}×</strong>
              </span>
            )}
          </div>
        )}

        {/* Entry / execution instructions */}
        {isOptions && repTrade ? (
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Execution — last trade ({repTrade.entryDate})</div>
            <div className="bg-gray-50 border border-gray-200 rounded px-3 py-2">
              <OptionsExecutionPanel stratKey={stratKey} trade={repTrade} symbol={result.symbol} />
            </div>
          </div>
        ) : equityEntryText ? (
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Entry rule</div>
            <div className="text-gray-600">{equityEntryText}</div>
          </div>
        ) : null}

        {/* Risk management grid */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-2">
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide">Risk per trade</div>
            <div className="font-medium text-gray-800">{suggestedRisk}% of capital</div>
            <div className="text-xs text-gray-400">(half-Kelly sizing)</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide">Initial stop</div>
            <div className="font-medium text-red-700">{stopPct}% from entry</div>
            <div className="text-xs text-gray-400">(60% of max DD)</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide">Avg hold time</div>
            <div className="font-medium text-gray-800">{avgDuration}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide">Profit target</div>
            <div className="font-medium text-green-700">{(avgRR * 1.5).toFixed(1)}× initial risk</div>
          </div>
        </div>

        {/* Warnings */}
        {result.maxDrawdown > 0.25 && (
          <div className="text-xs bg-amber-50 border border-amber-200 text-amber-800 px-3 py-2 rounded">
            ⚠️ Max drawdown was {(result.maxDrawdown * 100).toFixed(1)}%. Size conservatively and use a portfolio-level stop at 2× the per-trade stop.
          </div>
        )}
        {n < 10 && (
          <div className="text-xs bg-blue-50 border border-blue-200 text-blue-700 px-3 py-2 rounded">
            ℹ️ Only {n} trades in this period — results may not be statistically reliable. Extend the date range.
          </div>
        )}
        {edge === 'weak' && n >= 10 && (
          <div className="text-xs bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded">
            ℹ️ Profit factor {pf} and win rate {winPct}% are below acceptable thresholds. Consider a different strategy or timeframe for {result.symbol}.
          </div>
        )}
      </div>
    </div>
  );
}

interface Props {
  result: BacktestResult | null;
  loading?: boolean;
  error?: string | null;
}

function Metric({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  const color = positive === undefined ? 'text-gray-900'
    : positive ? 'text-green-700' : 'text-red-600';
  return (
    <div className="text-center">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-sm font-bold ${color}`}>{value}</div>
    </div>
  );
}

export function BacktestResultPanel({ result, loading, error }: Props) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-400">
        <svg className="animate-spin h-6 w-6 mr-2" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        Running backtest...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">{error}</div>
    );
  }

  if (!result) {
    return (
      <div className="text-center py-12 text-gray-400 text-sm">
        Configure a backtest and click Run Backtest
      </div>
    );
  }

  const totalReturnPositive = result.totalReturn >= 0;
  const [selectedTrade, setSelectedTrade] = useState<Trade | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-bold text-gray-900 font-mono">{result.symbol}</span>
          <span className="ml-2 text-sm text-gray-500">{result.strategyName}</span>
        </div>
        <span className="text-xs text-gray-400">{result.startDate} &rarr; {result.endDate}</span>
      </div>

      {/* Key metrics grid */}
      <div className="grid grid-cols-4 gap-2 bg-gray-50 rounded-lg p-3">
        <Metric label="Total Return" value={`${result.totalReturn.toFixed(1)}%`} positive={totalReturnPositive} />
        <Metric label="CAGR" value={`${(result.cagr * 100).toFixed(1)}%`} positive={result.cagr >= 0} />
        <Metric label="Sharpe" value={result.sharpe.toFixed(2)} positive={result.sharpe >= 1} />
        <Metric label="Max DD" value={`${(result.maxDrawdown * 100).toFixed(1)}%`} positive={false} />
      </div>

      <div className="grid grid-cols-4 gap-2 bg-gray-50 rounded-lg p-3">
        <Metric label="Win Rate" value={`${(result.winRate * 100).toFixed(0)}%`} positive={result.winRate >= 0.5} />
        <Metric label="Prof. Factor" value={result.profitFactor.toFixed(2)} positive={result.profitFactor >= 1} />
        <Metric label="Sortino" value={result.sortino.toFixed(2)} positive={result.sortino >= 1} />
        <Metric label="Trades" value={String(result.trades.length)} />
      </div>

      {/* Options-specific metrics */}
      {(result.pctExpiredWorthless != null || result.avgDteAtExit != null) && (
        <div className="grid grid-cols-4 gap-2 bg-purple-50 rounded-lg p-3 border border-purple-100">
          {result.pctExpiredWorthless != null && (
            <Metric
              label="Expired Worthless"
              value={`${result.pctExpiredWorthless.toFixed(1)}%`}
              positive={result.pctExpiredWorthless < 20}
            />
          )}
          {result.avgDteAtExit != null && (
            <Metric
              label="Avg DTE at Exit"
              value={`${result.avgDteAtExit.toFixed(0)} days`}
            />
          )}
        </div>
      )}

      {/* Equity curve + drawdown */}
      <EquityCurveChart result={result} height={180} selectedTrade={selectedTrade} />

      {/* Trading instructions */}
      <TradingInstructions result={result} />

      {/* Trades table */}
      {result.trades.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Trades {selectedTrade && <span className="text-blue-500 normal-case font-normal">— click row to highlight on chart</span>}
            </div>
            {selectedTrade && (
              <button onClick={() => setSelectedTrade(null)}
                className="text-xs text-gray-400 hover:text-gray-600 underline">clear</button>
            )}
          </div>
          <div className="max-h-48 overflow-y-auto">
            <table className="min-w-full text-xs divide-y divide-gray-100">
              <thead className="sticky top-0 bg-white">
                <tr>
                  <th className="text-left px-2 py-1 text-gray-500 font-medium">Entry</th>
                  <th className="text-left px-2 py-1 text-gray-500 font-medium">Exit</th>
                  <th className="text-right px-2 py-1 text-gray-500 font-medium">Entry $</th>
                  <th className="text-right px-2 py-1 text-gray-500 font-medium">Exit $</th>
                  <th className="text-right px-2 py-1 text-gray-500 font-medium">PnL%</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {result.trades.map((t, i) => {
                  const isSelected = selectedTrade === t;
                  return (
                  <tr key={i}
                    onClick={() => setSelectedTrade(isSelected ? null : t)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-blue-50 ring-1 ring-blue-300 ring-inset'
                        : t.pnl >= 0
                          ? 'text-green-700 hover:bg-green-50'
                          : 'text-red-600 hover:bg-red-50'
                    }`}
                  >
                    <td className="px-2 py-1 font-mono">{t.entryDate}</td>
                    <td className="px-2 py-1 font-mono">{t.exitDate}</td>
                    <td className="px-2 py-1 text-right">{t.entryPrice.toFixed(2)}</td>
                    <td className="px-2 py-1 text-right">{t.exitPrice.toFixed(2)}</td>
                    <td className="px-2 py-1 text-right font-medium">{t.pnlPct.toFixed(2)}%</td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

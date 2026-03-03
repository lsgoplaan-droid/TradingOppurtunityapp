import { ScanResult } from '../api/client';

interface Props {
  results: ScanResult[];
  onSelect?: (result: ScanResult) => void;
  selectedId?: string | null;
}

function StrengthBadge({ score }: { score: number }) {
  const color = score >= 80 ? 'bg-green-100 text-green-800'
    : score >= 60 ? 'bg-yellow-100 text-yellow-800'
    : 'bg-red-100 text-red-800';
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {score.toFixed(0)}%
    </span>
  );
}

function DirectionBadge({ direction }: { direction?: string }) {
  if (!direction) return null;
  const styles = direction === 'BUY'
    ? 'bg-green-100 text-green-800 border border-green-200'
    : direction === 'SELL'
    ? 'bg-red-100 text-red-800 border border-red-200'
    : 'bg-gray-100 text-gray-600 border border-gray-200';
  const arrow = direction === 'BUY' ? '▲' : direction === 'SELL' ? '▼' : '↔';
  return (
    <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-bold ${styles}`}>
      <span>{arrow}</span>
      <span>{direction}</span>
    </span>
  );
}

function ProbBadge({ prob }: { prob: number }) {
  const color = prob >= 60 ? 'text-green-700' : prob >= 45 ? 'text-yellow-700' : 'text-red-600';
  return <span className={`text-xs font-semibold ${color}`}>{prob.toFixed(0)}%</span>;
}

function fmt(price: number | undefined): string {
  if (price == null) return '—';
  return price >= 100 ? price.toFixed(2) : price.toFixed(4);
}

/** Banner showing symbols that fired 2+ signals — high-confluence picks */
function ConfluenceBanner({ symbolSignals }: { symbolSignals: Map<string, string[]> }) {
  const multi = Array.from(symbolSignals.entries())
    .filter(([, sigs]) => sigs.length >= 2)
    .sort((a, b) => b[1].length - a[1].length);

  if (multi.length === 0) return null;

  return (
    <div className="px-4 py-3 bg-gradient-to-r from-purple-50 to-indigo-50 border-b border-purple-100">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold text-purple-700 uppercase tracking-wide">High Confluence</span>
        <span className="text-xs text-purple-500">— tickers with multiple signals</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {multi.map(([symbol, sigs]) => (
          <div key={symbol} className="flex items-center gap-1 bg-white border border-purple-200 rounded-lg px-2.5 py-1 shadow-sm">
            <span className="font-mono font-bold text-sm text-gray-900">{symbol}</span>
            <span className="bg-purple-600 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">×{sigs.length}</span>
            <span className="text-xs text-gray-400 max-w-[140px] truncate" title={sigs.join(', ')}>{sigs.join(', ')}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ScanResultsTable({ results, onSelect, selectedId }: Props) {
  if (results.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <div className="text-4xl mb-2">📊</div>
        <div className="text-sm">No scan results yet. Select a template and run a scan.</div>
      </div>
    );
  }

  // Build symbol → [signalName, ...] map for confluence detection
  const symbolSignals = new Map<string, string[]>();
  for (const r of results) {
    const existing = symbolSignals.get(r.symbol) ?? [];
    if (!existing.includes(r.signalName)) symbolSignals.set(r.symbol, [...existing, r.signalName]);
  }

  // Sort: multi-signal rows first, then by strength
  const sorted = [...results].sort((a, b) => {
    const ca = symbolSignals.get(a.symbol)?.length ?? 1;
    const cb = symbolSignals.get(b.symbol)?.length ?? 1;
    if (cb !== ca) return cb - ca;
    return b.strengthScore - a.strengthScore;
  });

  return (
    <div>
      <ConfluenceBanner symbolSignals={symbolSignals} />
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead>
            <tr className="bg-gray-50">
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Symbol</th>
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Dir</th>
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Signal</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Entry / Prem</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Stop ↓</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Target ↑</th>
              <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">R:R / Prob</th>
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Strength</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-100">
            {sorted.map(r => {
              const signalCount = symbolSignals.get(r.symbol)?.length ?? 1;
              const isMulti = signalCount >= 2;
              const isOptions = r.assetClass === 'EQUITY_OPTIONS';
              const displayPrice = isOptions ? r.optionPremium : r.entryPrice;

              return (
                <tr
                  key={r.id}
                  onClick={() => onSelect?.(r)}
                  className={`cursor-pointer transition-colors ${
                    selectedId === r.id
                      ? 'bg-blue-50'
                      : isMulti
                      ? 'hover:bg-purple-50 bg-purple-50/30'
                      : 'hover:bg-gray-50'
                  }`}
                >
                  {/* Symbol */}
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-medium text-gray-900">{r.symbol}</span>
                      {isMulti && (
                        <span className="bg-purple-600 text-white text-xs font-bold px-1.5 py-0.5 rounded-full leading-none">
                          ×{signalCount}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {r.market === 'INDIA'
                        ? <span className="text-orange-600">NSE</span>
                        : <span className="text-blue-600">US</span>
                      }
                      {isOptions && <span className="ml-1 text-purple-600">OPT</span>}
                    </div>
                  </td>

                  {/* Direction */}
                  <td className="px-3 py-2.5">
                    <DirectionBadge direction={r.direction} />
                  </td>

                  {/* Signal */}
                  <td className="px-3 py-2.5 text-gray-600 text-xs max-w-[130px]">
                    <div className="truncate" title={r.signalName}>{r.signalName}</div>
                    <div className="text-gray-400 mt-0.5">{r.timeframe}</div>
                  </td>

                  {/* Entry price or option premium */}
                  <td className="px-3 py-2.5 text-right">
                    <div className="font-mono font-semibold text-gray-900">{fmt(displayPrice)}</div>
                    {isOptions && (
                      <div className="text-xs text-purple-500 mt-0.5">opt prem</div>
                    )}
                  </td>

                  {/* Stop loss */}
                  <td className="px-3 py-2.5 text-right">
                    {r.stopLoss != null ? (
                      <div className="font-mono text-red-600">{fmt(r.stopLoss)}</div>
                    ) : <span className="text-gray-300">—</span>}
                  </td>

                  {/* Target price */}
                  <td className="px-3 py-2.5 text-right">
                    {r.targetPrice != null ? (
                      <div className="font-mono text-green-700">{fmt(r.targetPrice)}</div>
                    ) : <span className="text-gray-300">—</span>}
                  </td>

                  {/* R:R for equity; profit probability for options */}
                  <td className="px-3 py-2.5 text-right">
                    {isOptions && r.profitProbability != null ? (
                      <div>
                        <ProbBadge prob={r.profitProbability} />
                        <div className="text-xs text-gray-400 mt-0.5">prob</div>
                      </div>
                    ) : r.riskReward != null ? (
                      <div className={`text-xs font-semibold ${
                        r.riskReward >= 2 ? 'text-green-700' : r.riskReward >= 1 ? 'text-yellow-700' : 'text-red-600'
                      }`}>
                        {r.riskReward.toFixed(1)}×
                      </div>
                    ) : <span className="text-gray-300">—</span>}
                  </td>

                  {/* Strength */}
                  <td className="px-3 py-2.5">
                    <StrengthBadge score={r.strengthScore} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

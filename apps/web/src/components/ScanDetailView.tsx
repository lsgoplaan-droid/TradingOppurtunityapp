import { ScanResult } from '../api/client';
import { MiniPriceChart } from './MiniPriceChart';

interface Props {
  result: ScanResult | null;
}

function fmt(price: number | undefined): string {
  if (price == null) return '—';
  return price >= 100 ? price.toFixed(2) : price.toFixed(4);
}


function OptionsPanel({ result }: { result: ScanResult }) {
  const S = result.entryPrice ?? 0;
  const spreadLabel = result.suggestedSpread === 'LONG_CALL_SPREAD' ? 'Long Call Spread'
    : result.suggestedSpread === 'LONG_PUT_SPREAD' ? 'Long Put Spread'
    : null;
  const spreadColor = result.direction === 'BUY' ? 'border-green-200 bg-green-50'
    : result.direction === 'SELL' ? 'border-red-200 bg-red-50'
    : 'border-purple-200 bg-purple-50';
  const labelColor = result.direction === 'BUY' ? 'text-green-700'
    : result.direction === 'SELL' ? 'text-red-700'
    : 'text-purple-700';

  return (
    <div className="space-y-3">
      {/* Strike + Premium row */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-purple-50 rounded-lg p-2.5">
          <div className="text-xs font-medium text-purple-500 uppercase tracking-wide mb-0.5">ATM Strike</div>
          <div className="font-bold font-mono text-purple-900 text-sm">{fmt(result.strikePrice)}</div>
        </div>
        <div className="bg-purple-50 rounded-lg p-2.5">
          <div className="text-xs font-medium text-purple-500 uppercase tracking-wide mb-0.5">Option Premium</div>
          <div className="font-bold font-mono text-purple-900 text-sm">{fmt(result.optionPremium)}</div>
          {S > 0 && result.optionPremium != null && (
            <div className="text-xs text-purple-400 mt-0.5">
              {((result.optionPremium / S) * 100).toFixed(1)}% of stock
            </div>
          )}
        </div>
        {result.profitProbability != null && (
          <div className="col-span-2 bg-gray-50 rounded-lg px-3 py-2 flex items-center justify-between">
            <span className="text-xs text-gray-500 font-medium">Profit Probability</span>
            <span className={`text-sm font-bold ${
              result.profitProbability >= 60 ? 'text-green-700'
              : result.profitProbability >= 45 ? 'text-yellow-700'
              : 'text-red-600'
            }`}>{result.profitProbability.toFixed(0)}%</span>
          </div>
        )}
      </div>

      {/* Spread suggestion */}
      {spreadLabel && result.spreadDebit != null && (
        <div className={`rounded-lg border p-3 ${spreadColor}`}>
          <div className={`text-xs font-semibold uppercase tracking-wide mb-2 ${labelColor}`}>
            Suggested: {spreadLabel}
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <div className="text-gray-400 uppercase tracking-wide">Net Debit</div>
              <div className="font-bold font-mono text-gray-800 mt-0.5">{fmt(result.spreadDebit)}</div>
              <div className="text-gray-400">(max loss)</div>
            </div>
            <div>
              <div className="text-gray-400 uppercase tracking-wide">Width</div>
              <div className="font-bold font-mono text-gray-800 mt-0.5">{fmt(result.spreadWidth)}</div>
              <div className="text-gray-400">5% spread</div>
            </div>
            <div>
              <div className="text-gray-400 uppercase tracking-wide">Max Profit</div>
              <div className={`font-bold font-mono mt-0.5 ${result.spreadMaxProfit != null && result.spreadMaxProfit > 0 ? 'text-green-700' : 'text-gray-800'}`}>
                {fmt(result.spreadMaxProfit)}
              </div>
              {result.spreadDebit != null && result.spreadMaxProfit != null && result.spreadDebit > 0 && (
                <div className="text-gray-400">
                  {(result.spreadMaxProfit / result.spreadDebit).toFixed(1)}× R:R
                </div>
              )}
            </div>
          </div>
          <div className="mt-2 text-xs text-gray-500">
            {result.suggestedSpread === 'LONG_CALL_SPREAD'
              ? `Buy ATM call @ ${fmt(result.strikePrice)}, sell OTM call @ ${fmt(result.strikePrice != null ? result.strikePrice * 1.05 : undefined)}`
              : `Buy ATM put @ ${fmt(result.strikePrice)}, sell OTM put @ ${fmt(result.strikePrice != null ? result.strikePrice * 0.95 : undefined)}`
            }
          </div>
        </div>
      )}

      {/* Greeks */}
      {(result.delta != null || result.gamma != null || result.theta != null || result.vega != null) && (
        <div className="grid grid-cols-4 gap-2 bg-gray-50 rounded-lg p-2.5">
          {result.delta != null && (
            <div>
              <div className="text-xs font-medium text-gray-400 uppercase tracking-wide">Δ Delta</div>
              <div className="font-bold font-mono text-gray-800 text-sm">{result.delta.toFixed(3)}</div>
              <div className="text-xs text-gray-400 mt-0.5">directional</div>
            </div>
          )}
          {result.gamma != null && (
            <div>
              <div className="text-xs font-medium text-gray-400 uppercase tracking-wide">Γ Gamma</div>
              <div className="font-bold font-mono text-gray-800 text-sm">{result.gamma.toFixed(4)}</div>
              <div className="text-xs text-gray-400 mt-0.5">delta rate</div>
            </div>
          )}
          {result.theta != null && (
            <div>
              <div className="text-xs font-medium text-gray-400 uppercase tracking-wide">Θ Theta</div>
              <div className="font-bold font-mono text-gray-800 text-sm">{result.theta.toFixed(4)}</div>
              <div className="text-xs text-gray-400 mt-0.5">daily decay</div>
            </div>
          )}
          {result.vega != null && (
            <div>
              <div className="text-xs font-medium text-gray-400 uppercase tracking-wide">ν Vega</div>
              <div className="font-bold font-mono text-gray-800 text-sm">{result.vega.toFixed(4)}</div>
              <div className="text-xs text-gray-400 mt-0.5">IV change</div>
            </div>
          )}
        </div>
      )}

      {/* IV Rank + Recommendation */}
      {(result.ivRank != null || result.expectedValue != null) && (
        <div className="grid grid-cols-2 gap-2">
          {result.ivRank != null && (
            <div className={`rounded-lg p-2.5 ${
              result.ivRank >= 70 ? 'bg-red-50 border border-red-100'
              : result.ivRank <= 30 ? 'bg-green-50 border border-green-100'
              : 'bg-yellow-50 border border-yellow-100'
            }`}>
              <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-0.5">IV Rank</div>
              <div className="flex items-baseline gap-1">
                <div className="font-bold font-mono text-gray-800 text-sm">{result.ivRank.toFixed(0)}%</div>
                {result.ivRecommendation && (
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                    result.ivRecommendation === 'SELL_PREMIUM' ? 'bg-red-100 text-red-700'
                    : result.ivRecommendation === 'BUY_PREMIUM' ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-700'
                  }`}>
                    {result.ivRecommendation === 'SELL_PREMIUM' ? 'Sell'
                    : result.ivRecommendation === 'BUY_PREMIUM' ? 'Buy'
                    : 'Neutral'}
                  </span>
                )}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {result.ivRank >= 70 ? 'High IV → sell premium'
                : result.ivRank <= 30 ? 'Low IV → buy premium'
                : 'Mid range'}
              </div>
            </div>
          )}
          {result.expectedValue != null && (
            <div className={`rounded-lg p-2.5 ${result.expectedValue > 0 ? 'bg-green-50 border border-green-100' : 'bg-gray-50'}`}>
              <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-0.5">Expected Value</div>
              <div className={`font-bold font-mono text-sm ${result.expectedValue > 0 ? 'text-green-700' : 'text-gray-600'}`}>
                {fmt(result.expectedValue)}
              </div>
              <div className="text-xs text-gray-400 mt-1">per trade</div>
            </div>
          )}
        </div>
      )}

      {/* Neutral strategies hint */}
      {result.direction === 'NEUTRAL' && result.optionPremium != null && (
        <div className="rounded-lg border border-purple-200 bg-purple-50 p-3 text-xs text-purple-700">
          <div className="font-semibold mb-1">Straddle / Strangle</div>
          <div>Combined premium (ATM call + put): <span className="font-mono font-bold">{fmt(result.optionPremium)}</span></div>
          <div className="text-purple-500 mt-0.5">
            Break-even: {fmt(S - result.optionPremium)} ↓ / {fmt(S + result.optionPremium)} ↑
          </div>
        </div>
      )}
    </div>
  );
}

export function ScanDetailView({ result }: Props) {
  if (!result) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 text-sm">
        Select a result to view details
      </div>
    );
  }

  const isOptions = result.assetClass === 'EQUITY_OPTIONS';
  const indicators = Object.entries(result.indicatorValues || {});

  return (
    <div className="p-4 space-y-4 overflow-y-auto">

      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-2xl font-bold font-mono text-gray-900">{result.symbol}</span>
          <span className={`px-2 py-0.5 rounded text-xs ${
            result.market === 'INDIA' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'
          }`}>{result.market}</span>
          <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs">{result.assetClass}</span>
        </div>
        <div className="text-sm text-gray-500">{result.signalName} · {result.timeframe}</div>
      </div>

      {/* Options-specific panel: strike, premium, spread */}
      {isOptions && <OptionsPanel result={result} />}

      {/* Mini price chart */}
      {result.recentCandles && result.recentCandles.length > 2 && (
        <div className="rounded-lg border border-gray-100 overflow-hidden bg-gray-50 p-2">
          <MiniPriceChart
            candles={result.recentCandles}
            support={result.supportLevels}
            resistance={result.resistanceLevels}
            entryPrice={result.entryPrice}
          />
        </div>
      )}

      {/* Entry / Stop / Target / R:R row */}
      {result.entryPrice != null && (
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-blue-50 rounded-lg p-2.5 col-span-2 flex items-center justify-between">
            <span className="text-xs font-medium text-blue-600 uppercase tracking-wide">Entry Price</span>
            <span className="text-lg font-bold font-mono text-blue-800">{fmt(result.entryPrice)}</span>
          </div>
          {result.stopLoss != null && (
            <div className="bg-red-50 rounded-lg p-2.5">
              <div className="text-xs font-medium text-red-500 uppercase tracking-wide mb-0.5">Stop Loss</div>
              <div className="font-bold font-mono text-red-800 text-sm">{fmt(result.stopLoss)}</div>
              <div className="text-xs text-red-400 mt-0.5">
                -{((result.entryPrice - result.stopLoss) / result.entryPrice * 100).toFixed(1)}%
              </div>
            </div>
          )}
          {result.targetPrice != null && (
            <div className="bg-green-50 rounded-lg p-2.5">
              <div className="text-xs font-medium text-green-600 uppercase tracking-wide mb-0.5">Target Price</div>
              <div className="font-bold font-mono text-green-800 text-sm">{fmt(result.targetPrice)}</div>
              <div className="text-xs text-green-500 mt-0.5">
                +{((result.targetPrice - result.entryPrice) / result.entryPrice * 100).toFixed(1)}%
              </div>
            </div>
          )}
          {result.riskReward != null && (
            <div className="col-span-2 bg-gray-50 rounded-lg px-3 py-2 flex items-center justify-between">
              <span className="text-xs text-gray-500 font-medium">Risk : Reward</span>
              <span className={`text-sm font-bold ${
                result.riskReward >= 2 ? 'text-green-700' : result.riskReward >= 1 ? 'text-yellow-700' : 'text-red-700'
              }`}>
                1 : {result.riskReward.toFixed(1)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Support / Resistance */}
      {((result.supportLevels?.length ?? 0) > 0 || (result.resistanceLevels?.length ?? 0) > 0) && (
        <div className="grid grid-cols-2 gap-2">
          <div>
            <div className="text-xs font-medium text-green-600 uppercase tracking-wide mb-1.5">Support</div>
            <div className="space-y-1">
              {(result.supportLevels ?? []).map((s, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />
                  <span className="text-sm font-mono text-gray-800 font-medium">{fmt(s)}</span>
                  {result.entryPrice != null && (
                    <span className="text-xs text-green-600 ml-auto">
                      -{((result.entryPrice - s) / result.entryPrice * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
              ))}
              {(result.supportLevels?.length ?? 0) === 0 && (
                <span className="text-xs text-gray-400">None detected</span>
              )}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-red-600 uppercase tracking-wide mb-1.5">Resistance</div>
            <div className="space-y-1">
              {(result.resistanceLevels ?? []).map((r, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                  <span className="text-sm font-mono text-gray-800 font-medium">{fmt(r)}</span>
                  {result.entryPrice != null && (
                    <span className="text-xs text-red-600 ml-auto">
                      +{((r - result.entryPrice) / result.entryPrice * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
              ))}
              {(result.resistanceLevels?.length ?? 0) === 0 && (
                <span className="text-xs text-gray-400">None detected</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Strength score */}
      <div className="bg-gray-50 rounded-lg p-3">
        <div className="text-xs text-gray-500 mb-1">Signal Strength</div>
        <div className="flex items-center gap-2">
          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-2 rounded-full ${
                result.strengthScore >= 80 ? 'bg-green-500'
                : result.strengthScore >= 60 ? 'bg-yellow-500'
                : 'bg-red-500'
              }`}
              style={{ width: `${result.strengthScore}%` }}
            />
          </div>
          <span className="text-sm font-medium">{result.strengthScore.toFixed(0)}%</span>
        </div>
      </div>

      {/* F&O metrics (India options) */}
      {(result.ivRank !== undefined || result.pcr !== undefined) && (
        <div className="grid grid-cols-2 gap-2">
          {result.ivRank !== undefined && (
            <div className="bg-purple-50 rounded p-2 text-xs">
              <div className="text-purple-500 font-medium">IV Rank</div>
              <div className="text-gray-900 font-bold text-lg">{result.ivRank?.toFixed(1)}%</div>
            </div>
          )}
          {result.pcr !== undefined && (
            <div className="bg-teal-50 rounded p-2 text-xs">
              <div className="text-teal-500 font-medium">PCR (OI)</div>
              <div className="text-gray-900 font-bold text-lg">{result.pcr?.toFixed(2)}</div>
            </div>
          )}
          {result.maxPain !== undefined && (
            <div className="bg-red-50 rounded p-2 text-xs">
              <div className="text-red-500 font-medium">Max Pain</div>
              <div className="text-gray-900 font-bold text-lg">{result.maxPain?.toFixed(0)}</div>
            </div>
          )}
        </div>
      )}

      {/* Key indicators */}
      {indicators.length > 0 && (
        <div>
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Indicators</div>
          <div className="grid grid-cols-2 gap-1">
            {indicators.map(([key, val]) => (
              <div key={key} className="flex justify-between text-xs py-1 border-b border-gray-100">
                <span className="text-gray-500 font-mono">{key}</span>
                <span className="text-gray-900 font-medium">
                  {typeof val === 'number' ? val.toFixed(2) : String(val)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* MTF triggered timeframes */}
      {(result.triggeredTimeframes?.length ?? 0) > 0 && (
        <div>
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1.5">Confirmed Timeframes</div>
          <div className="flex flex-wrap gap-1.5">
            {result.triggeredTimeframes!.map(tf => (
              <span key={tf} className="bg-indigo-100 text-indigo-700 text-xs px-2 py-0.5 rounded-full font-medium">
                {tf}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="text-xs text-gray-400">
        Scanned at {new Date(result.timestamp).toLocaleString()}
      </div>
    </div>
  );
}

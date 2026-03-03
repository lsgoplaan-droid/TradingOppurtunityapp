import { useState, useEffect } from 'react';
import { BacktestRunRequest, BacktestStrategy } from '../api/client';

interface Props {
  strategies: BacktestStrategy[];
  onSubmit: (request: BacktestRunRequest) => void;
  loading?: boolean;
  prefilledSymbol?: string;
  prefilledTemplateId?: string;
  prefilledTemplateName?: string;
  prefilledMarket?: 'US' | 'INDIA';
  prefilledAssetClass?: 'EQUITY' | 'EQUITY_OPTIONS';
  onClearPrefill?: () => void;
}

export function BacktestForm({
  strategies,
  onSubmit,
  loading,
  prefilledSymbol,
  prefilledTemplateId,
  prefilledTemplateName,
  prefilledMarket,
  prefilledAssetClass,
  onClearPrefill,
}: Props) {
  const [symbol, setSymbol] = useState(prefilledSymbol ?? 'AAPL');
  const [templateId, setTemplateId] = useState(
    prefilledTemplateId ?? strategies[0]?.id ?? 'golden_cross'
  );
  const [startDate, setStartDate] = useState('2021-01-01');
  const [endDate, setEndDate] = useState('2023-12-31');
  const [initialCapital, setInitialCapital] = useState(100000);
  const [positionSizing, setPositionSizing] = useState<'fixed' | 'pct_equity' | 'kelly'>('pct_equity');
  const [commissionPct, setCommissionPct] = useState(0.001);

  const assetClass = prefilledAssetClass ?? 'EQUITY';
  const isOptions = assetClass === 'EQUITY_OPTIONS';
  const optionsStrategies = strategies.filter(s => s.assetClass === 'EQUITY_OPTIONS');
  const equityStrategies = strategies.filter(s => s.assetClass !== 'EQUITY_OPTIONS');

  const [optionsStrategy, setOptionsStrategy] = useState(optionsStrategies[0]?.id ?? 'long_call');
  const [expiryDays, setExpiryDays] = useState(30);
  const [strikeOffsetPct, setStrikeOffsetPct] = useState(0.0);
  const [wingWidthPct, setWingWidthPct] = useState(0.05);

  useEffect(() => { if (prefilledSymbol) setSymbol(prefilledSymbol); }, [prefilledSymbol]);
  useEffect(() => { if (prefilledTemplateId) setTemplateId(prefilledTemplateId); }, [prefilledTemplateId]);
  useEffect(() => {
    if (optionsStrategies.length > 0 && !optionsStrategies.find(s => s.id === optionsStrategy)) {
      setOptionsStrategy(optionsStrategies[0].id);
    }
  }, [strategies]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      symbol,
      templateId,
      startDate,
      endDate,
      initialCapital,
      positionSizing,
      commissionPct,
      market: prefilledMarket ?? 'US',
      assetClass,
      ...(isOptions && { optionsStrategy, expiryDays, strikeOffsetPct, wingWidthPct }),
    });
  };

  const isPrefilled = Boolean(prefilledTemplateId);

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <h3 className="font-semibold text-gray-900">Backtest Configuration</h3>

      {isOptions && (
        <div className="text-xs bg-purple-50 border border-purple-200 text-purple-700 px-2.5 py-1.5 rounded">
          Options Backtest — Black-Scholes simulation with realized vol
        </div>
      )}

      {/* Symbol */}
      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">Symbol</label>
        <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())}
          className="w-full border border-gray-200 rounded px-2.5 py-1.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-blue-400"
          placeholder="AAPL" />
      </div>

      {/* Strategy */}
      {isOptions ? (
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Options Strategy</label>
          <select value={optionsStrategy} onChange={e => setOptionsStrategy(e.target.value)}
            className="w-full border border-gray-200 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-purple-400">
            {optionsStrategies.map(s => (
              <option key={s.id} value={s.id}>{s.name} — {s.description}</option>
            ))}
          </select>
        </div>
      ) : (
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Scan Template</label>
          {isPrefilled ? (
            <div className="flex items-center gap-2 px-2.5 py-1.5 border border-blue-200 bg-blue-50 rounded text-sm">
              <span className="flex-1 text-blue-800 font-medium truncate">
                {prefilledTemplateName ?? prefilledTemplateId}
              </span>
              {onClearPrefill && (
                <button type="button" onClick={onClearPrefill}
                  className="text-blue-400 hover:text-blue-600 text-xs flex-shrink-0">&#x2715;</button>
              )}
            </div>
          ) : (
            <select value={templateId} onChange={e => setTemplateId(e.target.value)}
              className="w-full border border-gray-200 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400">
              {equityStrategies.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          )}
        </div>
      )}

      {/* Options params */}
      {isOptions && (
        <div className="space-y-2 border border-purple-100 rounded-lg p-2.5 bg-purple-50/40">
          <div className="text-xs font-semibold text-purple-600 uppercase tracking-wide">Option Parameters</div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Expiry (days)</label>
              <input type="number" min={7} max={90} value={expiryDays}
                onChange={e => setExpiryDays(Number(e.target.value))}
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-purple-400" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Strike offset %</label>
              <input type="number" step="0.01" min={0} max={0.2} value={strikeOffsetPct}
                onChange={e => setStrikeOffsetPct(Number(e.target.value))}
                className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-purple-400" />
            </div>
            {optionsStrategy === 'iron_condor' && (
              <div className="col-span-2">
                <label className="block text-xs text-gray-500 mb-1">Wing width % (Iron Condor)</label>
                <input type="number" step="0.01" min={0.02} max={0.2} value={wingWidthPct}
                  onChange={e => setWingWidthPct(Number(e.target.value))}
                  className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-purple-400" />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Date range */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Start Date</label>
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
            className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">End Date</label>
          <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
            className="w-full border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">Initial Capital ($)</label>
        <input type="number" value={initialCapital} onChange={e => setInitialCapital(Number(e.target.value))}
          className="w-full border border-gray-200 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400" />
      </div>

      {!isOptions && (
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Position Sizing</label>
          <select value={positionSizing}
            onChange={e => setPositionSizing(e.target.value as 'fixed' | 'pct_equity' | 'kelly')}
            className="w-full border border-gray-200 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400">
            <option value="pct_equity">% of Equity (10%)</option>
            <option value="fixed">Fixed ($10k)</option>
            <option value="kelly">Half-Kelly</option>
          </select>
        </div>
      )}

      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">Commission (%)</label>
        <input type="number" step="0.0001" value={commissionPct}
          onChange={e => setCommissionPct(Number(e.target.value))}
          className="w-full border border-gray-200 rounded px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400" />
      </div>

      <button type="submit" disabled={loading}
        className={`w-full py-2 rounded-lg text-sm font-medium transition-colors ${
          loading ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
          : isOptions ? 'bg-purple-600 hover:bg-purple-700 text-white'
          : 'bg-green-600 hover:bg-green-700 text-white'
        }`}>
        {loading ? 'Running...' : isOptions ? 'Run Options Backtest' : 'Run Backtest'}
      </button>
    </form>
  );
}

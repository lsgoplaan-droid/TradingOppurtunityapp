import { useState, useEffect, useCallback, useRef } from 'react';
import {
  fetchTemplates,
  runScan,
  runMTFScan,
  runMultiScan,
  ScanTemplate,
  ScanResult,
  fetchStrategies,
  submitBacktest,
  pollBacktestStatus,
  fetchBacktestResult,
  BacktestStrategy,
  BacktestResult,
  BacktestRunRequest,
  WatchlistItem,
} from '../api/client';
import { MarketAssetSelector } from '../components/MarketAssetSelector';
import { ScanTemplateSelector } from '../components/ScanTemplateSelector';
import { RunScanButton } from '../components/RunScanButton';
import { ScanResultsTable } from '../components/ScanResultsTable';
import { ScanDetailView } from '../components/ScanDetailView';
import { BacktestForm } from '../components/BacktestForm';
import { BacktestResultPanel } from '../components/BacktestResultPanel';
import { WatchlistManager } from '../components/WatchlistManager';

type Tab = 'scanner' | 'backtest';
type Market = 'US' | 'INDIA';
type AssetClass = 'EQUITY' | 'EQUITY_OPTIONS';

/** Context carried from a scan result into the backtest tab */
interface BacktestPrefill {
  symbol: string;
  templateId: string;
  templateName: string;
  market: 'US' | 'INDIA';
  assetClass: 'EQUITY' | 'EQUITY_OPTIONS';
}

export function App() {
  const [activeTab, setActiveTab] = useState<Tab>('scanner');

  // --- Market / asset filter ---
  const [market, setMarket] = useState<Market>('US');
  const [assetClass, setAssetClass] = useState<AssetClass>('EQUITY');

  // --- Scanner state ---
  const [allTemplates, setAllTemplates] = useState<ScanTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [results, setResults] = useState<ScanResult[]>([]);
  const [selectedResult, setSelectedResult] = useState<ScanResult | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  // --- Backtest state ---
  const [strategies, setStrategies] = useState<BacktestStrategy[]>([]);
  const [backtestPrefill, setBacktestPrefill] = useState<BacktestPrefill | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [watchlists, setWatchlists] = useState<WatchlistItem[]>([]);
  const pollInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  // Templates filtered to current market + asset class
  const visibleTemplates = allTemplates.filter(
    t => t.market === market && t.assetClass === assetClass
  );

  // Reset selected template when market or asset class changes
  useEffect(() => {
    setSelectedTemplateId(null);
    setResults([]);
    setSelectedResult(null);
  }, [market, assetClass]);

  // Load scan templates from both endpoints
  useEffect(() => {
    async function loadTemplates() {
      setTemplatesLoading(true);
      try {
        const [usRes, indiaRes] = await Promise.allSettled([
          fetchTemplates('US'),
          fetchTemplates('INDIA'),
        ]);
        const all: ScanTemplate[] = [];
        if (usRes.status === 'fulfilled') all.push(...usRes.value);
        if (indiaRes.status === 'fulfilled') all.push(...indiaRes.value);
        setAllTemplates(all);
      } catch {
        setScanError('Failed to load templates');
      } finally {
        setTemplatesLoading(false);
      }
    }
    loadTemplates();
  }, []);

  // Load backtest strategy list (for the manual fallback dropdown)
  useEffect(() => {
    fetchStrategies().catch(() => {/* non-critical */});
    fetchStrategies().then(setStrategies).catch(() => {});
  }, []);

  // Cleanup polling on unmount
  useEffect(() => () => {
    if (pollInterval.current) clearInterval(pollInterval.current);
  }, []);

  const handleRunScan = useCallback(async () => {
    if (!selectedTemplateId) return;
    setScanLoading(true);
    setScanError(null);
    try {
      const tpl = allTemplates.find(t => t.id === selectedTemplateId);
      const isMTF = tpl?.type === 'mtf';
      const newResults = isMTF
        ? await runMTFScan(selectedTemplateId, tpl?.market)
        : await runScan({ templateId: selectedTemplateId }, tpl?.market);
      setResults(prev => [...newResults, ...prev]);
    } catch (err) {
      setScanError(err instanceof Error ? err.message : 'Scan failed');
    } finally {
      setScanLoading(false);
    }
  }, [selectedTemplateId, allTemplates]);

  /** Run ALL visible templates at once and surface multi-signal confluence */
  const handleRunAllScans = useCallback(async () => {
    if (visibleTemplates.length === 0) return;
    setScanLoading(true);
    setScanError(null);
    setResults([]);
    setSelectedResult(null);
    try {
      const ids = visibleTemplates.map(t => t.id);
      const newResults = await runMultiScan(ids, market);
      setResults(newResults);
    } catch (err) {
      setScanError(err instanceof Error ? err.message : 'Multi-scan failed');
    } finally {
      setScanLoading(false);
    }
  }, [visibleTemplates, market]);

  /** Switch to Backtest tab pre-filled with the selected signal */
  const handleBacktestSignal = useCallback(() => {
    if (!selectedResult) return;
    // Use the template carried on the result itself; fall back to the sidebar selection
    const tid = selectedResult.templateId ?? selectedTemplateId;
    if (!tid) return;
    const tpl = allTemplates.find(t => t.id === tid);
    setBacktestPrefill({
      symbol: selectedResult.symbol,
      templateId: tid,
      templateName: tpl?.name ?? tid,
      market: (selectedResult.market as 'US' | 'INDIA') ?? market,
      assetClass: (selectedResult.assetClass as 'EQUITY' | 'EQUITY_OPTIONS') ?? assetClass,
    });
    setActiveTab('backtest');
  }, [selectedResult, selectedTemplateId, allTemplates, market]);

  const handleRunBacktest = useCallback(async (request: BacktestRunRequest) => {
    if (pollInterval.current) {
      clearInterval(pollInterval.current);
      pollInterval.current = null;
    }
    setBacktestLoading(true);
    setBacktestError(null);
    setBacktestResult(null);

    let jobId: string;
    try {
      const jobStatus = await submitBacktest(request);
      jobId = jobStatus.jobId;
    } catch (err) {
      setBacktestError(err instanceof Error ? err.message : 'Failed to submit backtest');
      setBacktestLoading(false);
      return;
    }

    pollInterval.current = setInterval(async () => {
      try {
        const status = await pollBacktestStatus(jobId);
        if (status.status === 'complete') {
          clearInterval(pollInterval.current!);
          pollInterval.current = null;
          try {
            setBacktestResult(await fetchBacktestResult(jobId));
          } catch (err) {
            setBacktestError(err instanceof Error ? err.message : 'Failed to fetch result');
          }
          setBacktestLoading(false);
        } else if (status.status === 'failed') {
          clearInterval(pollInterval.current!);
          pollInterval.current = null;
          setBacktestError(status.error ?? 'Backtest failed');
          setBacktestLoading(false);
        }
      } catch (err) {
        clearInterval(pollInterval.current!);
        pollInterval.current = null;
        setBacktestError(err instanceof Error ? err.message : 'Poll failed');
        setBacktestLoading(false);
      }
    }, 1500);
  }, []);

  const handleAddWatchlist = useCallback(
    (name: string, symbols: string[], wlMarket: 'US' | 'INDIA' | 'ALL') => {
      setWatchlists(prev => [...prev, { id: `wl-${Date.now()}`, name, symbols, market: wlMarket }]);
    },
    []
  );

  const selectedTemplateName = allTemplates.find(t => t.id === selectedTemplateId)?.name;

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="max-w-screen-xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Trading Opportunity Scanner</h1>
            <p className="text-sm text-gray-500">US Equities &middot; US Options &middot; India NSE &middot; India F&amp;O</p>
          </div>
          <nav className="flex gap-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setActiveTab('scanner')}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'scanner' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Scanner
            </button>
            <button
              onClick={() => setActiveTab('backtest')}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'backtest' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Backtest
              {backtestPrefill && (
                <span className="ml-1.5 bg-blue-100 text-blue-700 text-xs px-1.5 py-0.5 rounded-full">
                  {backtestPrefill.symbol}
                </span>
              )}
            </button>
          </nav>
          {activeTab === 'scanner' && results.length > 0 && (
            <div className="text-sm text-gray-500">{results.length} signals</div>
          )}
        </div>
      </header>

      {/* ── SCANNER TAB ─────────────────────────────────────────────────── */}
      {activeTab === 'scanner' && (
        <div className="max-w-screen-xl mx-auto p-6 flex gap-6">
          {/* Left sidebar */}
          <aside className="w-64 flex-shrink-0 space-y-3">
            {/* Market + Asset selector */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
              <MarketAssetSelector
                market={market}
                assetClass={assetClass}
                onMarketChange={m => setMarket(m)}
                onAssetClassChange={a => setAssetClass(a)}
              />
              <div className="border-t border-gray-100 pt-3">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                  {visibleTemplates.length} template{visibleTemplates.length !== 1 ? 's' : ''}
                </p>
                <ScanTemplateSelector
                  templates={visibleTemplates}
                  selectedId={selectedTemplateId}
                  onSelect={setSelectedTemplateId}
                  loading={templatesLoading}
                />
              </div>
            </div>

            <RunScanButton
              disabled={!selectedTemplateId}
              loading={scanLoading}
              onClick={handleRunScan}
            />

            {/* Run all templates simultaneously to find multi-signal confluence */}
            <button
              onClick={handleRunAllScans}
              disabled={scanLoading || visibleTemplates.length === 0}
              className="w-full py-2.5 rounded-xl text-sm font-medium border-2 border-purple-300 text-purple-700 hover:bg-purple-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {scanLoading ? 'Scanning…' : `Run All ${visibleTemplates.length} Signals`}
            </button>

            {scanError && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
                {scanError}
              </div>
            )}
          </aside>

          {/* Results table */}
          <main className="flex-1 min-w-0">
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                <h2 className="font-semibold text-gray-900">
                  Scan Results
                  {selectedTemplateName && (
                    <span className="ml-2 text-sm font-normal text-gray-400">— {selectedTemplateName}</span>
                  )}
                </h2>
                {results.length > 0 && (
                  <span className="text-xs text-gray-400">{results.length} signals</span>
                )}
              </div>
              <ScanResultsTable
                results={results}
                onSelect={setSelectedResult}
                selectedId={selectedResult?.id}
              />
            </div>
          </main>

          {/* Right detail panel */}
          {selectedResult && (
            <aside className="w-72 flex-shrink-0">
              <div className="bg-white rounded-xl border border-gray-200 flex flex-col">
                <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                  <h2 className="font-semibold text-gray-900">Signal Detail</h2>
                  <button
                    onClick={() => setSelectedResult(null)}
                    className="text-gray-400 hover:text-gray-600 text-sm"
                  >
                    &#x2715;
                  </button>
                </div>
                <ScanDetailView result={selectedResult} />
                {/* Backtest this signal */}
                <div className="px-4 pb-4 pt-2 border-t border-gray-100">
                  <button
                    onClick={handleBacktestSignal}
                    disabled={!selectedResult}
                    className="w-full py-2 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-700 text-white transition-colors disabled:bg-gray-100 disabled:text-gray-400"
                  >
                    Backtest this signal
                  </button>
                </div>
              </div>
            </aside>
          )}
        </div>
      )}

      {/* ── BACKTEST TAB ─────────────────────────────────────────────────── */}
      {activeTab === 'backtest' && (
        <div className="max-w-screen-xl mx-auto p-6 flex gap-6">
          {/* Left sidebar */}
          <aside className="w-72 flex-shrink-0 space-y-4">
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <BacktestForm
                strategies={strategies}
                onSubmit={handleRunBacktest}
                loading={backtestLoading}
                prefilledSymbol={backtestPrefill?.symbol}
                prefilledTemplateId={backtestPrefill?.templateId}
                prefilledTemplateName={backtestPrefill?.templateName}
                prefilledMarket={backtestPrefill?.market}
                prefilledAssetClass={backtestPrefill?.assetClass}
                onClearPrefill={() => setBacktestPrefill(null)}
              />
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <WatchlistManager
                watchlists={watchlists}
                onAddWatchlist={handleAddWatchlist}
                onSelectWatchlist={() => {}}
              />
            </div>
          </aside>

          {/* Result panel */}
          <main className="flex-1 min-w-0">
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <BacktestResultPanel
                result={backtestResult}
                loading={backtestLoading}
                error={backtestError}
              />
            </div>
          </main>
        </div>
      )}
    </div>
  );
}

export default App;

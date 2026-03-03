import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Alert,
  Dimensions,
} from 'react-native';
import Svg, { Path, Line, Text as SvgText } from 'react-native-svg';

import {
  fetchStrategies,
  submitBacktest,
  pollBacktestStatus,
  fetchBacktestResult,
  BacktestStrategy,
  BacktestResult,
  Trade,
} from '../api/client';
import { MetricsGrid, MetricItem } from '../components/MetricsGrid';

// -----------------------------------------------------------------------
// Equity curve chart (SVG — mirrors web EquityCurveChart logic)
// -----------------------------------------------------------------------

interface CurveProps {
  result: BacktestResult;
}

function EquityCurveChart({ result }: CurveProps) {
  const { equityCurve } = result;
  const screenWidth = Dimensions.get('window').width - 48; // 24px margin each side

  if (!equityCurve || equityCurve.length < 2) {
    return (
      <View style={chartStyles.placeholder}>
        <Text style={chartStyles.placeholderText}>No equity data</Text>
      </View>
    );
  }

  const values = equityCurve.map((p) => p.value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  const W = screenWidth;
  const H = 160;
  const pad = { top: 10, right: 8, bottom: 20, left: 52 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;

  const toX = (i: number) => pad.left + (i / (values.length - 1)) * innerW;
  const toY = (v: number) => pad.top + innerH - ((v - minVal) / range) * innerH;

  const lineParts = values.map((v, i) => {
    const x = toX(i).toFixed(1);
    const y = toY(v).toFixed(1);
    return i === 0 ? `M${x},${y}` : `L${x},${y}`;
  });
  const linePath = lineParts.join(' ');
  const fillPath =
    linePath +
    ` L${toX(values.length - 1).toFixed(1)},${(pad.top + innerH).toFixed(1)}` +
    ` L${pad.left},${(pad.top + innerH).toFixed(1)} Z`;

  const yTicks = [minVal, (minVal + maxVal) / 2, maxVal];

  return (
    <View>
      <Text style={chartStyles.title}>Equity Curve</Text>
      <Svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
        {yTicks.map((tick, i) => {
          const y = toY(tick).toFixed(1);
          const label =
            tick >= 1000 ? `${(tick / 1000).toFixed(0)}k` : tick.toFixed(0);
          return (
            <React.Fragment key={i}>
              <Line
                x1={pad.left}
                x2={W - pad.right}
                y1={y}
                y2={y}
                stroke="#e5e7eb"
                strokeWidth="1"
              />
              <SvgText
                x={pad.left - 4}
                y={parseFloat(y) + 4}
                textAnchor="end"
                fontSize="9"
                fill="#9ca3af"
              >
                {label}
              </SvgText>
            </React.Fragment>
          );
        })}
        <Path d={fillPath} fill="#3b82f6" fillOpacity="0.1" />
        <Path d={linePath} fill="none" stroke="#3b82f6" strokeWidth="1.5" />
      </Svg>
    </View>
  );
}

const chartStyles = StyleSheet.create({
  placeholder: {
    height: 80,
    alignItems: 'center',
    justifyContent: 'center',
  },
  placeholderText: {
    color: '#9ca3af',
    fontSize: 13,
  },
  title: {
    fontSize: 11,
    fontWeight: '600',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 6,
  },
});

// -----------------------------------------------------------------------
// Trade row
// -----------------------------------------------------------------------

function TradeRow({ trade }: { trade: Trade }) {
  const positive = trade.pnl >= 0;
  return (
    <View style={tradeStyles.row}>
      <View style={tradeStyles.dates}>
        <Text style={tradeStyles.date}>{trade.entryDate}</Text>
        <Text style={tradeStyles.sep}>→</Text>
        <Text style={tradeStyles.date}>{trade.exitDate}</Text>
      </View>
      <View style={tradeStyles.prices}>
        <Text style={tradeStyles.price}>
          {trade.entryPrice.toFixed(2)} → {trade.exitPrice.toFixed(2)}
        </Text>
      </View>
      <Text
        style={[tradeStyles.pnl, { color: positive ? '#16a34a' : '#dc2626' }]}
      >
        {positive ? '+' : ''}
        {trade.pnl.toFixed(2)} ({positive ? '+' : ''}
        {trade.pnlPct.toFixed(1)}%)
      </Text>
    </View>
  );
}

const tradeStyles = StyleSheet.create({
  row: {
    paddingVertical: 9,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#f3f4f6',
  },
  dates: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 2,
  },
  date: { fontSize: 11, color: '#6b7280', fontFamily: 'monospace' },
  sep: { fontSize: 10, color: '#d1d5db' },
  prices: { marginBottom: 2 },
  price: {
    fontSize: 12,
    color: '#374151',
    fontFamily: 'monospace',
    fontWeight: '500',
  },
  pnl: {
    fontSize: 13,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
});

// -----------------------------------------------------------------------
// Strategy picker (simple scrollable list)
// -----------------------------------------------------------------------

interface StratPickerProps {
  strategies: BacktestStrategy[];
  selected: string;
  onSelect: (id: string) => void;
  filter?: 'EQUITY' | 'EQUITY_OPTIONS';
}

function StrategyPicker({
  strategies,
  selected,
  onSelect,
  filter,
}: StratPickerProps) {
  const filtered = filter
    ? strategies.filter((s) =>
        filter === 'EQUITY_OPTIONS'
          ? s.assetClass === 'EQUITY_OPTIONS'
          : s.assetClass !== 'EQUITY_OPTIONS'
      )
    : strategies;

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={pickerStyles.scroll}
      contentContainerStyle={pickerStyles.content}
    >
      {filtered.map((s) => (
        <TouchableOpacity
          key={s.id}
          style={[
            pickerStyles.chip,
            selected === s.id && pickerStyles.chipActive,
          ]}
          onPress={() => onSelect(s.id)}
          activeOpacity={0.7}
        >
          <Text
            style={[
              pickerStyles.chipText,
              selected === s.id && pickerStyles.chipTextActive,
            ]}
          >
            {s.name}
          </Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}

const pickerStyles = StyleSheet.create({
  scroll: { marginHorizontal: -14, marginTop: 4 },
  content: { paddingHorizontal: 14, gap: 6 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: '#f3f4f6',
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  chipActive: {
    backgroundColor: '#4f46e5',
    borderColor: '#4f46e5',
  },
  chipText: {
    fontSize: 12,
    color: '#374151',
    fontWeight: '500',
  },
  chipTextActive: {
    color: '#ffffff',
    fontWeight: '600',
  },
});

// -----------------------------------------------------------------------
// Result panel
// -----------------------------------------------------------------------

function ResultPanel({ result }: { result: BacktestResult }) {
  const metrics: MetricItem[] = [
    {
      label: 'Total Return',
      value: `${(result.totalReturn * 100).toFixed(1)}%`,
      positive: result.totalReturn >= 0,
    },
    {
      label: 'Sharpe',
      value: result.sharpe.toFixed(2),
      positive: result.sharpe >= 1,
    },
    {
      label: 'Win Rate',
      value: `${(result.winRate * 100).toFixed(1)}%`,
      positive: result.winRate >= 0.5,
    },
    {
      label: 'Max Drawdown',
      value: `${(result.maxDrawdown * 100).toFixed(1)}%`,
      positive: false,
    },
  ];

  const moreMetrics: MetricItem[] = [
    {
      label: 'CAGR',
      value: `${(result.cagr * 100).toFixed(1)}%`,
      positive: result.cagr >= 0,
    },
    {
      label: 'Sortino',
      value: result.sortino.toFixed(2),
      positive: result.sortino >= 1,
    },
    {
      label: 'Profit Factor',
      value: result.profitFactor.toFixed(2),
      positive: result.profitFactor >= 1,
    },
    {
      label: 'Avg Duration',
      value: `${result.avgTradeDuration.toFixed(0)}d`,
    },
  ];

  return (
    <ScrollView style={resultStyles.container}>
      {/* Summary */}
      <View style={resultStyles.section}>
        <Text style={resultStyles.sectionTitle}>
          {result.symbol} · {result.strategyName}
        </Text>
        <Text style={resultStyles.dateRange}>
          {result.startDate} → {result.endDate}
        </Text>
      </View>

      {/* Key metrics */}
      <View style={resultStyles.section}>
        <Text style={resultStyles.label}>Key Metrics</Text>
        <MetricsGrid metrics={metrics} columns={2} />
      </View>

      {/* More metrics */}
      <View style={resultStyles.section}>
        <Text style={resultStyles.label}>More Stats</Text>
        <MetricsGrid metrics={moreMetrics} columns={2} />
      </View>

      {/* Options extra */}
      {result.pctExpiredWorthless != null && (
        <View style={resultStyles.section}>
          <Text style={resultStyles.label}>Options Stats</Text>
          <MetricsGrid
            metrics={[
              {
                label: '% Expired Worthless',
                value: `${(result.pctExpiredWorthless * 100).toFixed(1)}%`,
                positive: result.pctExpiredWorthless >= 0.5,
              },
              {
                label: 'Avg DTE at Exit',
                value:
                  result.avgDteAtExit != null
                    ? `${result.avgDteAtExit.toFixed(1)}d`
                    : '—',
              },
            ]}
            columns={2}
          />
        </View>
      )}

      {/* Equity curve */}
      <View style={resultStyles.section}>
        <EquityCurveChart result={result} />
      </View>

      {/* Trades */}
      {result.trades.length > 0 && (
        <View style={resultStyles.tradesSection}>
          <Text style={[resultStyles.label, { padding: 14, paddingBottom: 6 }]}>
            Trades ({result.trades.length})
          </Text>
          {result.trades.map((t, i) => (
            <TradeRow key={i} trade={t} />
          ))}
        </View>
      )}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const resultStyles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  section: {
    backgroundColor: '#ffffff',
    marginHorizontal: 12,
    marginTop: 10,
    borderRadius: 12,
    padding: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 2,
  },
  dateRange: {
    fontSize: 12,
    color: '#6b7280',
    fontFamily: 'monospace',
  },
  label: {
    fontSize: 11,
    fontWeight: '700',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 10,
  },
  tradesSection: {
    backgroundColor: '#ffffff',
    marginHorizontal: 12,
    marginTop: 10,
    borderRadius: 12,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1,
  },
});

// -----------------------------------------------------------------------
// Main screen
// -----------------------------------------------------------------------

type Phase = 'FORM' | 'LOADING' | 'RESULT';

export function BacktestScreen() {
  const [strategies, setStrategies] = useState<BacktestStrategy[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(false);

  const [assetClass, setAssetClass] = useState<'EQUITY' | 'EQUITY_OPTIONS'>('EQUITY');
  const [symbol, setSymbol] = useState('AAPL');
  const [startDate, setStartDate] = useState('2021-01-01');
  const [endDate, setEndDate] = useState('2023-12-31');
  const [initialCapital, setInitialCapital] = useState('100000');
  const [positionSizing, setPositionSizing] = useState<'fixed' | 'pct_equity' | 'kelly'>('pct_equity');
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [optionsStrategy, setOptionsStrategy] = useState('');
  const [expiryDays, setExpiryDays] = useState('30');

  const [phase, setPhase] = useState<Phase>('FORM');
  const [statusMsg, setStatusMsg] = useState('Submitting…');
  const [result, setResult] = useState<BacktestResult | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isOptions = assetClass === 'EQUITY_OPTIONS';
  const equityStrategies = strategies.filter((s) => s.assetClass !== 'EQUITY_OPTIONS');
  const optionStrategies = strategies.filter((s) => s.assetClass === 'EQUITY_OPTIONS');

  const loadStrategies = useCallback(async () => {
    setStrategiesLoading(true);
    try {
      const data = await fetchStrategies();
      setStrategies(data);
      const eq = data.find((s) => s.assetClass !== 'EQUITY_OPTIONS');
      const opt = data.find((s) => s.assetClass === 'EQUITY_OPTIONS');
      if (eq && !selectedStrategy) setSelectedStrategy(eq.id);
      if (opt && !optionsStrategy) setOptionsStrategy(opt.id);
    } catch (err: unknown) {
      // Non-fatal: user can still type strategy id manually
    } finally {
      setStrategiesLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadStrategies();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadStrategies]);

  const startPolling = (jobId: string) => {
    setStatusMsg('Running backtest…');
    pollRef.current = setInterval(async () => {
      try {
        const status = await pollBacktestStatus(jobId);
        if (status.status === 'complete') {
          clearInterval(pollRef.current!);
          setStatusMsg('Fetching results…');
          const res = await fetchBacktestResult(jobId);
          setResult(res);
          setPhase('RESULT');
        } else if (status.status === 'failed') {
          clearInterval(pollRef.current!);
          Alert.alert('Backtest Failed', status.error ?? 'Unknown error');
          setPhase('FORM');
        }
      } catch (err: unknown) {
        clearInterval(pollRef.current!);
        const msg = err instanceof Error ? err.message : String(err);
        Alert.alert('Error', msg);
        setPhase('FORM');
      }
    }, 1500);
  };

  const handleRun = async () => {
    if (!symbol.trim()) {
      Alert.alert('Validation', 'Symbol is required.');
      return;
    }
    setPhase('LOADING');
    setStatusMsg('Submitting…');
    try {
      const req = {
        symbol: symbol.toUpperCase(),
        templateId: isOptions ? optionsStrategy : selectedStrategy,
        startDate,
        endDate,
        initialCapital: Number(initialCapital) || 100000,
        positionSizing,
        commissionPct: 0.001,
        market: 'US' as const,
        assetClass,
        ...(isOptions && {
          optionsStrategy,
          expiryDays: Number(expiryDays) || 30,
          strikeOffsetPct: 0.0,
          wingWidthPct: 0.05,
        }),
      };
      const job = await submitBacktest(req);
      startPolling(job.jobId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      Alert.alert('Submit Failed', msg);
      setPhase('FORM');
    }
  };

  if (phase === 'RESULT' && result) {
    return (
      <View style={styles.container}>
        <View style={styles.resultHeader}>
          <TouchableOpacity
            style={styles.backBtn}
            onPress={() => {
              setPhase('FORM');
              setResult(null);
            }}
          >
            <Text style={styles.backBtnText}>← New Backtest</Text>
          </TouchableOpacity>
        </View>
        <ResultPanel result={result} />
      </View>
    );
  }

  if (phase === 'LOADING') {
    return (
      <View style={[styles.container, styles.centered]}>
        <ActivityIndicator size="large" color="#4f46e5" />
        <Text style={styles.loadingMsg}>{statusMsg}</Text>
      </View>
    );
  }

  // FORM phase
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.formScroll}>
      {/* Asset class toggle */}
      <View style={styles.card}>
        <Text style={styles.fieldLabel}>Asset Class</Text>
        <View style={styles.segmented}>
          <TouchableOpacity
            style={[styles.segBtn, assetClass === 'EQUITY' && styles.segBtnActive]}
            onPress={() => setAssetClass('EQUITY')}
          >
            <Text style={[styles.segBtnText, assetClass === 'EQUITY' && styles.segBtnTextActive]}>
              Equity
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.segBtn,
              assetClass === 'EQUITY_OPTIONS' && styles.segBtnOptionsActive,
            ]}
            onPress={() => setAssetClass('EQUITY_OPTIONS')}
          >
            <Text
              style={[
                styles.segBtnText,
                assetClass === 'EQUITY_OPTIONS' && styles.segBtnTextActive,
              ]}
            >
              Options
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {isOptions && (
        <View style={styles.optionsInfoBanner}>
          <Text style={styles.optionsInfoText}>
            Options Backtest — Black-Scholes simulation with realized vol
          </Text>
        </View>
      )}

      <View style={styles.card}>
        {/* Symbol */}
        <Text style={styles.fieldLabel}>Symbol</Text>
        <TextInput
          style={styles.input}
          value={symbol}
          onChangeText={(t) => setSymbol(t.toUpperCase())}
          placeholder="AAPL"
          placeholderTextColor="#9ca3af"
          autoCapitalize="characters"
        />

        {/* Strategy */}
        <Text style={[styles.fieldLabel, { marginTop: 14 }]}>
          {isOptions ? 'Options Strategy' : 'Scan Template / Strategy'}
        </Text>
        {strategiesLoading ? (
          <ActivityIndicator color="#4f46e5" style={{ marginVertical: 6 }} />
        ) : isOptions ? (
          <StrategyPicker
            strategies={strategies}
            selected={optionsStrategy}
            onSelect={setOptionsStrategy}
            filter="EQUITY_OPTIONS"
          />
        ) : (
          <StrategyPicker
            strategies={strategies}
            selected={selectedStrategy}
            onSelect={setSelectedStrategy}
            filter="EQUITY"
          />
        )}

        {/* Options: expiry days */}
        {isOptions && (
          <>
            <Text style={[styles.fieldLabel, { marginTop: 14 }]}>
              Expiry (days)
            </Text>
            <TextInput
              style={styles.input}
              value={expiryDays}
              onChangeText={setExpiryDays}
              keyboardType="numeric"
              placeholder="30"
              placeholderTextColor="#9ca3af"
            />
          </>
        )}
      </View>

      <View style={styles.card}>
        {/* Date range */}
        <View style={styles.row}>
          <View style={styles.halfField}>
            <Text style={styles.fieldLabel}>Start Date</Text>
            <TextInput
              style={styles.input}
              value={startDate}
              onChangeText={setStartDate}
              placeholder="YYYY-MM-DD"
              placeholderTextColor="#9ca3af"
            />
          </View>
          <View style={styles.halfField}>
            <Text style={styles.fieldLabel}>End Date</Text>
            <TextInput
              style={styles.input}
              value={endDate}
              onChangeText={setEndDate}
              placeholder="YYYY-MM-DD"
              placeholderTextColor="#9ca3af"
            />
          </View>
        </View>

        {/* Initial capital */}
        <Text style={[styles.fieldLabel, { marginTop: 14 }]}>
          Initial Capital ($)
        </Text>
        <TextInput
          style={styles.input}
          value={initialCapital}
          onChangeText={setInitialCapital}
          keyboardType="numeric"
          placeholder="100000"
          placeholderTextColor="#9ca3af"
        />

        {/* Position sizing — equity only */}
        {!isOptions && (
          <>
            <Text style={[styles.fieldLabel, { marginTop: 14 }]}>
              Position Sizing
            </Text>
            <View style={styles.sizingRow}>
              {(
                [
                  { id: 'pct_equity', label: '% Equity' },
                  { id: 'fixed', label: 'Fixed' },
                  { id: 'kelly', label: 'Half-Kelly' },
                ] as const
              ).map((opt) => (
                <TouchableOpacity
                  key={opt.id}
                  style={[
                    styles.sizingBtn,
                    positionSizing === opt.id && styles.sizingBtnActive,
                  ]}
                  onPress={() => setPositionSizing(opt.id)}
                >
                  <Text
                    style={[
                      styles.sizingBtnText,
                      positionSizing === opt.id && styles.sizingBtnTextActive,
                    ]}
                  >
                    {opt.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </>
        )}
      </View>

      {/* Submit */}
      <TouchableOpacity
        style={[styles.runBtn, isOptions && styles.runBtnOptions]}
        onPress={handleRun}
        activeOpacity={0.8}
      >
        <Text style={styles.runBtnText}>
          {isOptions ? 'Run Options Backtest' : 'Run Backtest'}
        </Text>
      </TouchableOpacity>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  formScroll: { padding: 16, gap: 12 },
  centered: { alignItems: 'center', justifyContent: 'center', gap: 12 },
  loadingMsg: { color: '#6b7280', fontSize: 14, marginTop: 8 },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 3,
    elevation: 1,
  },
  fieldLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 6,
  },
  input: {
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: '#111827',
    backgroundColor: '#fafafa',
    fontFamily: 'monospace',
  },
  row: { flexDirection: 'row', gap: 10 },
  halfField: { flex: 1 },
  segmented: {
    flexDirection: 'row',
    backgroundColor: '#f3f4f6',
    borderRadius: 8,
    padding: 3,
    gap: 3,
  },
  segBtn: {
    flex: 1,
    paddingVertical: 7,
    borderRadius: 6,
    alignItems: 'center',
  },
  segBtnActive: { backgroundColor: '#4f46e5' },
  segBtnOptionsActive: { backgroundColor: '#7e22ce' },
  segBtnText: { fontSize: 13, fontWeight: '600', color: '#6b7280' },
  segBtnTextActive: { color: '#ffffff' },
  sizingRow: { flexDirection: 'row', gap: 6 },
  sizingBtn: {
    flex: 1,
    paddingVertical: 7,
    borderRadius: 7,
    alignItems: 'center',
    backgroundColor: '#f3f4f6',
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  sizingBtnActive: {
    backgroundColor: '#eef2ff',
    borderColor: '#818cf8',
  },
  sizingBtnText: { fontSize: 12, color: '#6b7280', fontWeight: '500' },
  sizingBtnTextActive: { color: '#4f46e5', fontWeight: '700' },
  runBtn: {
    backgroundColor: '#16a34a',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    shadowColor: '#16a34a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 2,
  },
  runBtnOptions: {
    backgroundColor: '#7e22ce',
    shadowColor: '#7e22ce',
  },
  runBtnText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '700',
  },
  resultHeader: {
    backgroundColor: '#ffffff',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  backBtn: {
    alignSelf: 'flex-start',
  },
  backBtnText: {
    color: '#4f46e5',
    fontSize: 14,
    fontWeight: '600',
  },
  optionsInfoBanner: {
    backgroundColor: '#faf5ff',
    borderWidth: 1,
    borderColor: '#e9d5ff',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  optionsInfoText: {
    fontSize: 12,
    color: '#7e22ce',
    fontWeight: '500',
  },
});

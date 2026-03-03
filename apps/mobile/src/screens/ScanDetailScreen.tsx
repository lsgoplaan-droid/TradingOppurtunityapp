import React from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
} from 'react-native';
import type { ScanDetailScreenProps } from '../navigation/types';
import type { ScanResult } from '../api/client';

function fmt(price: number | undefined): string {
  if (price == null) return '—';
  return price >= 100 ? price.toFixed(2) : price.toFixed(4);
}

// -----------------------------------------------------------------------
// Small reusable cells
// -----------------------------------------------------------------------

function InfoCell({
  label,
  value,
  accent,
  span,
}: {
  label: string;
  value: string;
  accent?: string;
  span?: boolean;
}) {
  return (
    <View style={[styles.infoCell, span && styles.infoCellSpan]}>
      <Text style={styles.infoCellLabel}>{label}</Text>
      <Text style={[styles.infoCellValue, accent ? { color: accent } : undefined]}>
        {value}
      </Text>
    </View>
  );
}

// -----------------------------------------------------------------------
// Options panel (strike, premium, Greeks, IV rank, EV)
// -----------------------------------------------------------------------

function OptionsPanel({ result }: { result: ScanResult }) {
  const S = result.entryPrice ?? 0;
  const spreadLabel =
    result.suggestedSpread === 'LONG_CALL_SPREAD'
      ? 'Long Call Spread'
      : result.suggestedSpread === 'LONG_PUT_SPREAD'
      ? 'Long Put Spread'
      : null;

  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Options Details</Text>

      {/* Strike + Premium */}
      <View style={styles.twoCol}>
        <InfoCell label="ATM Strike" value={fmt(result.strikePrice)} accent="#7e22ce" />
        <InfoCell
          label="Option Premium"
          value={fmt(result.optionPremium)}
          accent="#7e22ce"
        />
      </View>

      {result.profitProbability != null && (
        <View style={styles.infoRow}>
          <Text style={styles.infoRowLabel}>Profit Probability</Text>
          <Text
            style={[
              styles.infoRowValue,
              {
                color:
                  result.profitProbability >= 60
                    ? '#16a34a'
                    : result.profitProbability >= 45
                    ? '#d97706'
                    : '#dc2626',
              },
            ]}
          >
            {result.profitProbability.toFixed(0)}%
          </Text>
        </View>
      )}

      {/* Suggested spread */}
      {spreadLabel && result.spreadDebit != null && (
        <View style={styles.spreadBox}>
          <Text style={styles.spreadTitle}>{spreadLabel}</Text>
          <View style={styles.twoCol}>
            <InfoCell label="Net Debit (Max Loss)" value={fmt(result.spreadDebit)} />
            <InfoCell label="Max Profit" value={fmt(result.spreadMaxProfit)} accent="#16a34a" />
          </View>
          {result.spreadDebit != null &&
            result.spreadMaxProfit != null &&
            result.spreadDebit > 0 && (
              <View style={styles.infoRow}>
                <Text style={styles.infoRowLabel}>R:R</Text>
                <Text style={styles.infoRowValue}>
                  {(result.spreadMaxProfit / result.spreadDebit).toFixed(1)}×
                </Text>
              </View>
            )}
        </View>
      )}

      {/* Greeks 2×2 */}
      {(result.delta != null ||
        result.gamma != null ||
        result.theta != null ||
        result.vega != null) && (
        <View>
          <Text style={styles.subTitle}>Greeks</Text>
          <View style={styles.greeksGrid}>
            {result.delta != null && (
              <View style={styles.greekCell}>
                <Text style={styles.greekLabel}>Delta (Δ)</Text>
                <Text style={styles.greekValue}>{result.delta.toFixed(3)}</Text>
              </View>
            )}
            {result.gamma != null && (
              <View style={styles.greekCell}>
                <Text style={styles.greekLabel}>Gamma (Γ)</Text>
                <Text style={styles.greekValue}>{result.gamma.toFixed(4)}</Text>
              </View>
            )}
            {result.theta != null && (
              <View style={styles.greekCell}>
                <Text style={styles.greekLabel}>Theta (Θ)</Text>
                <Text style={styles.greekValue}>{result.theta.toFixed(4)}</Text>
              </View>
            )}
            {result.vega != null && (
              <View style={styles.greekCell}>
                <Text style={styles.greekLabel}>Vega (ν)</Text>
                <Text style={styles.greekValue}>{result.vega.toFixed(4)}</Text>
              </View>
            )}
          </View>
        </View>
      )}

      {/* IV rank */}
      {result.ivRank != null && (
        <View
          style={[
            styles.ivRankBox,
            {
              backgroundColor:
                result.ivRank >= 70
                  ? '#fef2f2'
                  : result.ivRank <= 30
                  ? '#f0fdf4'
                  : '#fefce8',
              borderColor:
                result.ivRank >= 70
                  ? '#fecaca'
                  : result.ivRank <= 30
                  ? '#bbf7d0'
                  : '#fef08a',
            },
          ]}
        >
          <View style={styles.ivRankRow}>
            <Text style={styles.infoCellLabel}>IV Rank</Text>
            <Text
              style={[
                styles.ivRankValue,
                {
                  color:
                    result.ivRank >= 70
                      ? '#dc2626'
                      : result.ivRank <= 30
                      ? '#16a34a'
                      : '#ca8a04',
                },
              ]}
            >
              {result.ivRank.toFixed(0)}%
            </Text>
            {result.ivRecommendation && (
              <View
                style={[
                  styles.ivRecBadge,
                  {
                    backgroundColor:
                      result.ivRecommendation === 'SELL_PREMIUM'
                        ? '#fee2e2'
                        : result.ivRecommendation === 'BUY_PREMIUM'
                        ? '#dcfce7'
                        : '#f3f4f6',
                  },
                ]}
              >
                <Text
                  style={[
                    styles.ivRecText,
                    {
                      color:
                        result.ivRecommendation === 'SELL_PREMIUM'
                          ? '#b91c1c'
                          : result.ivRecommendation === 'BUY_PREMIUM'
                          ? '#15803d'
                          : '#374151',
                    },
                  ]}
                >
                  {result.ivRecommendation === 'SELL_PREMIUM'
                    ? 'Sell Premium'
                    : result.ivRecommendation === 'BUY_PREMIUM'
                    ? 'Buy Premium'
                    : 'Neutral'}
                </Text>
              </View>
            )}
          </View>
          <Text style={styles.ivRankHint}>
            {result.ivRank >= 70
              ? 'High IV — consider selling premium'
              : result.ivRank <= 30
              ? 'Low IV — consider buying premium'
              : 'Mid range IV'}
          </Text>
        </View>
      )}

      {/* Expected value */}
      {result.expectedValue != null && (
        <View style={styles.infoRow}>
          <Text style={styles.infoRowLabel}>Expected Value (per trade)</Text>
          <Text
            style={[
              styles.infoRowValue,
              { color: result.expectedValue > 0 ? '#16a34a' : '#6b7280' },
            ]}
          >
            {fmt(result.expectedValue)}
          </Text>
        </View>
      )}

      {/* Straddle hint */}
      {result.direction === 'NEUTRAL' && result.optionPremium != null && S > 0 && (
        <View style={styles.straddleBox}>
          <Text style={styles.straddleTitle}>Straddle / Strangle</Text>
          <Text style={styles.straddleText}>
            Combined ATM premium: {fmt(result.optionPremium)}
          </Text>
          <Text style={styles.straddleText}>
            Break-even: {fmt(S - result.optionPremium)} ↓ / {fmt(S + result.optionPremium)} ↑
          </Text>
        </View>
      )}
    </View>
  );
}

// -----------------------------------------------------------------------
// Main screen
// -----------------------------------------------------------------------

export function ScanDetailScreen({ route }: ScanDetailScreenProps) {
  const { result } = route.params;
  const isOptions = result.assetClass === 'EQUITY_OPTIONS';
  const indicators = Object.entries(result.indicatorValues || {});

  const dirColor =
    result.direction === 'BUY'
      ? '#16a34a'
      : result.direction === 'SELL'
      ? '#dc2626'
      : '#7e22ce';

  const strengthColor =
    result.strengthScore >= 80
      ? '#22c55e'
      : result.strengthScore >= 60
      ? '#f59e0b'
      : '#ef4444';

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.scrollContent}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerRow}>
          <Text style={styles.symbol}>{result.symbol}</Text>
          {result.direction && (
            <View
              style={[
                styles.dirBadge,
                {
                  backgroundColor:
                    result.direction === 'BUY'
                      ? '#dcfce7'
                      : result.direction === 'SELL'
                      ? '#fee2e2'
                      : '#f3e8ff',
                },
              ]}
            >
              <Text style={[styles.dirText, { color: dirColor }]}>
                {result.direction}
              </Text>
            </View>
          )}
          <View
            style={[
              styles.marketBadge,
              {
                backgroundColor:
                  result.market === 'INDIA' ? '#ffedd5' : '#dbeafe',
              },
            ]}
          >
            <Text
              style={[
                styles.marketBadgeText,
                {
                  color: result.market === 'INDIA' ? '#c2410c' : '#1d4ed8',
                },
              ]}
            >
              {result.market}
            </Text>
          </View>
        </View>
        <Text style={styles.signalMeta}>
          {result.signalName} · {result.timeframe}
        </Text>
        <Text style={styles.timestamp}>
          Scanned at {new Date(result.timestamp).toLocaleString()}
        </Text>
      </View>

      {/* Options panel */}
      {isOptions && <OptionsPanel result={result} />}

      {/* Entry / Stop / Target / R:R */}
      {result.entryPrice != null && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Price Levels</Text>
          <View
            style={[
              styles.entryRow,
              { backgroundColor: '#eff6ff', borderColor: '#bfdbfe' },
            ]}
          >
            <Text style={styles.entryLabel}>Entry Price</Text>
            <Text style={styles.entryValue}>{fmt(result.entryPrice)}</Text>
          </View>
          <View style={styles.twoCol}>
            {result.stopLoss != null && (
              <InfoCell
                label={`Stop Loss (−${((result.entryPrice - result.stopLoss) / result.entryPrice * 100).toFixed(1)}%)`}
                value={fmt(result.stopLoss)}
                accent="#dc2626"
              />
            )}
            {result.targetPrice != null && (
              <InfoCell
                label={`Target (+${((result.targetPrice - result.entryPrice) / result.entryPrice * 100).toFixed(1)}%)`}
                value={fmt(result.targetPrice)}
                accent="#16a34a"
              />
            )}
          </View>
          {result.riskReward != null && (
            <View style={styles.infoRow}>
              <Text style={styles.infoRowLabel}>Risk : Reward</Text>
              <Text
                style={[
                  styles.infoRowValue,
                  {
                    color:
                      result.riskReward >= 2
                        ? '#16a34a'
                        : result.riskReward >= 1
                        ? '#d97706'
                        : '#dc2626',
                  },
                ]}
              >
                1 : {result.riskReward.toFixed(1)}
              </Text>
            </View>
          )}
        </View>
      )}

      {/* Support / Resistance */}
      {((result.supportLevels?.length ?? 0) > 0 ||
        (result.resistanceLevels?.length ?? 0) > 0) && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Key Levels</Text>
          <View style={styles.twoCol}>
            <View style={styles.levelsCol}>
              <Text style={styles.levelsHeader}>Support</Text>
              {(result.supportLevels ?? []).map((s, i) => (
                <View key={i} style={styles.levelRow}>
                  <View style={[styles.levelDot, { backgroundColor: '#4ade80' }]} />
                  <Text style={styles.levelValue}>{fmt(s)}</Text>
                  {result.entryPrice != null && (
                    <Text style={styles.levelPct}>
                      −{((result.entryPrice - s) / result.entryPrice * 100).toFixed(1)}%
                    </Text>
                  )}
                </View>
              ))}
              {(result.supportLevels?.length ?? 0) === 0 && (
                <Text style={styles.levelsEmpty}>None</Text>
              )}
            </View>
            <View style={styles.levelsCol}>
              <Text style={[styles.levelsHeader, { color: '#dc2626' }]}>
                Resistance
              </Text>
              {(result.resistanceLevels ?? []).map((r, i) => (
                <View key={i} style={styles.levelRow}>
                  <View style={[styles.levelDot, { backgroundColor: '#f87171' }]} />
                  <Text style={styles.levelValue}>{fmt(r)}</Text>
                  {result.entryPrice != null && (
                    <Text style={styles.levelPct}>
                      +{((r - result.entryPrice) / result.entryPrice * 100).toFixed(1)}%
                    </Text>
                  )}
                </View>
              ))}
              {(result.resistanceLevels?.length ?? 0) === 0 && (
                <Text style={styles.levelsEmpty}>None</Text>
              )}
            </View>
          </View>
        </View>
      )}

      {/* Signal strength */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Signal Strength</Text>
        <View style={styles.strengthRow}>
          <View style={styles.strengthBarBg}>
            <View
              style={[
                styles.strengthBarFill,
                {
                  width: `${Math.min(100, result.strengthScore)}%` as any,
                  backgroundColor: strengthColor,
                },
              ]}
            />
          </View>
          <Text style={[styles.strengthPct, { color: strengthColor }]}>
            {result.strengthScore.toFixed(0)}%
          </Text>
        </View>
      </View>

      {/* F&O metrics (India options) */}
      {(result.ivRank !== undefined ||
        result.pcr !== undefined ||
        result.maxPain !== undefined) && !isOptions && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>F&O Metrics</Text>
          <View style={styles.twoCol}>
            {result.ivRank !== undefined && (
              <InfoCell
                label="IV Rank"
                value={`${result.ivRank?.toFixed(1)}%`}
                accent="#7e22ce"
              />
            )}
            {result.pcr !== undefined && (
              <InfoCell label="PCR (OI)" value={result.pcr?.toFixed(2) ?? '—'} />
            )}
            {result.maxPain !== undefined && (
              <InfoCell
                label="Max Pain"
                value={result.maxPain?.toFixed(0) ?? '—'}
                accent="#dc2626"
              />
            )}
          </View>
        </View>
      )}

      {/* MTF triggered timeframes */}
      {(result.triggeredTimeframes?.length ?? 0) > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Confirmed Timeframes</Text>
          <View style={styles.tfRow}>
            {result.triggeredTimeframes!.map((tf) => (
              <View key={tf} style={styles.tfBadge}>
                <Text style={styles.tfBadgeText}>{tf}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* Key indicators */}
      {indicators.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Indicators</Text>
          {indicators.map(([key, val]) => (
            <View key={key} style={styles.indicatorRow}>
              <Text style={styles.indicatorKey}>{key}</Text>
              <Text style={styles.indicatorVal}>
                {typeof val === 'number' ? val.toFixed(2) : String(val)}
              </Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f9fafb',
  },
  scrollContent: {
    paddingBottom: 40,
  },
  header: {
    backgroundColor: '#ffffff',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
    marginBottom: 8,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  symbol: {
    fontSize: 26,
    fontWeight: '800',
    color: '#111827',
    fontFamily: 'monospace',
    flex: 1,
  },
  dirBadge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 20,
  },
  dirText: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  marketBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 20,
  },
  marketBadgeText: {
    fontSize: 11,
    fontWeight: '600',
  },
  signalMeta: {
    fontSize: 14,
    color: '#6b7280',
    fontWeight: '500',
    marginBottom: 2,
  },
  timestamp: {
    fontSize: 11,
    color: '#9ca3af',
  },
  section: {
    backgroundColor: '#ffffff',
    marginHorizontal: 12,
    marginVertical: 5,
    borderRadius: 12,
    padding: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: 10,
  },
  subTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: '#9ca3af',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 8,
    marginTop: 8,
  },
  twoCol: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 4,
  },
  infoCell: {
    backgroundColor: '#f9fafb',
    borderRadius: 8,
    padding: 10,
    width: '47%',
    borderWidth: 1,
    borderColor: '#f3f4f6',
  },
  infoCellSpan: {
    width: '100%',
  },
  infoCellLabel: {
    fontSize: 11,
    color: '#9ca3af',
    fontWeight: '500',
    marginBottom: 3,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  infoCellValue: {
    fontSize: 15,
    fontWeight: '700',
    color: '#111827',
    fontFamily: 'monospace',
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 7,
    borderTopWidth: 1,
    borderTopColor: '#f3f4f6',
  },
  infoRowLabel: {
    fontSize: 13,
    color: '#6b7280',
  },
  infoRowValue: {
    fontSize: 14,
    fontWeight: '700',
    color: '#111827',
    fontFamily: 'monospace',
  },
  entryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 8,
  },
  entryLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#1d4ed8',
  },
  entryValue: {
    fontSize: 20,
    fontWeight: '800',
    color: '#1d4ed8',
    fontFamily: 'monospace',
  },
  strengthRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  strengthBarBg: {
    flex: 1,
    height: 8,
    backgroundColor: '#e5e7eb',
    borderRadius: 4,
    overflow: 'hidden',
  },
  strengthBarFill: {
    height: '100%',
    borderRadius: 4,
  },
  strengthPct: {
    fontSize: 14,
    fontWeight: '700',
    width: 42,
    textAlign: 'right',
  },
  greeksGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  greekCell: {
    backgroundColor: '#f9fafb',
    borderRadius: 8,
    padding: 10,
    width: '47%',
    borderWidth: 1,
    borderColor: '#f3f4f6',
  },
  greekLabel: {
    fontSize: 11,
    color: '#9ca3af',
    fontWeight: '500',
    marginBottom: 3,
  },
  greekValue: {
    fontSize: 15,
    fontWeight: '700',
    color: '#111827',
    fontFamily: 'monospace',
  },
  ivRankBox: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    marginTop: 6,
  },
  ivRankRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  ivRankValue: {
    fontSize: 18,
    fontWeight: '800',
    fontFamily: 'monospace',
  },
  ivRecBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 20,
    marginLeft: 'auto',
  },
  ivRecText: {
    fontSize: 11,
    fontWeight: '600',
  },
  ivRankHint: {
    fontSize: 12,
    color: '#6b7280',
  },
  spreadBox: {
    backgroundColor: '#faf5ff',
    borderWidth: 1,
    borderColor: '#e9d5ff',
    borderRadius: 8,
    padding: 10,
    marginVertical: 6,
  },
  spreadTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#7e22ce',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 8,
  },
  straddleBox: {
    backgroundColor: '#faf5ff',
    borderWidth: 1,
    borderColor: '#e9d5ff',
    borderRadius: 8,
    padding: 10,
    marginTop: 6,
  },
  straddleTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#7e22ce',
    marginBottom: 4,
  },
  straddleText: {
    fontSize: 13,
    color: '#6b7280',
    lineHeight: 18,
  },
  levelsCol: {
    flex: 1,
  },
  levelsHeader: {
    fontSize: 12,
    fontWeight: '700',
    color: '#16a34a',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 8,
  },
  levelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  levelDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  levelValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#111827',
    fontFamily: 'monospace',
    flex: 1,
  },
  levelPct: {
    fontSize: 11,
    color: '#9ca3af',
  },
  levelsEmpty: {
    fontSize: 12,
    color: '#9ca3af',
  },
  tfRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  tfBadge: {
    backgroundColor: '#e0e7ff',
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 20,
  },
  tfBadgeText: {
    fontSize: 12,
    color: '#4338ca',
    fontWeight: '600',
  },
  indicatorRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#f3f4f6',
  },
  indicatorKey: {
    fontSize: 13,
    color: '#6b7280',
    fontFamily: 'monospace',
  },
  indicatorVal: {
    fontSize: 13,
    fontWeight: '600',
    color: '#111827',
    fontFamily: 'monospace',
  },
});

import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import type { ScanResult } from '../api/client';

interface Props {
  result: ScanResult;
  onPress: (result: ScanResult) => void;
}

function fmt(price: number | undefined): string {
  if (price == null) return '—';
  return price >= 100 ? price.toFixed(2) : price.toFixed(4);
}

const DIRECTION_COLORS = {
  BUY: { bg: '#dcfce7', text: '#15803d' },
  SELL: { bg: '#fee2e2', text: '#b91c1c' },
  NEUTRAL: { bg: '#f3e8ff', text: '#7e22ce' },
};

export function ResultCard({ result, onPress }: Props) {
  const dirColor = DIRECTION_COLORS[result.direction ?? 'NEUTRAL'] ??
    DIRECTION_COLORS.NEUTRAL;
  const isOptions = result.assetClass === 'EQUITY_OPTIONS';
  const strengthColor =
    result.strengthScore >= 80
      ? '#22c55e'
      : result.strengthScore >= 60
      ? '#f59e0b'
      : '#ef4444';

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => onPress(result)}
      activeOpacity={0.75}
    >
      {/* Symbol row */}
      <View style={styles.headerRow}>
        <Text style={styles.symbol}>{result.symbol}</Text>
        {result.direction && (
          <View style={[styles.dirBadge, { backgroundColor: dirColor.bg }]}>
            <Text style={[styles.dirText, { color: dirColor.text }]}>
              {result.direction}
            </Text>
          </View>
        )}
        {isOptions && (
          <View style={styles.optionsBadge}>
            <Text style={styles.optionsBadgeText}>OPTIONS</Text>
          </View>
        )}
      </View>

      {/* Signal name + timeframe */}
      <Text style={styles.signalName} numberOfLines={1}>
        {result.signalName}
        <Text style={styles.timeframe}> · {result.timeframe}</Text>
      </Text>

      {/* Entry price + stop/target */}
      {result.entryPrice != null && (
        <View style={styles.priceRow}>
          <Text style={styles.priceLabel}>Entry</Text>
          <Text style={styles.priceValue}>{fmt(result.entryPrice)}</Text>
          {result.stopLoss != null && (
            <>
              <Text style={styles.priceLabel}>Stop</Text>
              <Text style={[styles.priceValue, { color: '#ef4444' }]}>
                {fmt(result.stopLoss)}
              </Text>
            </>
          )}
          {result.targetPrice != null && (
            <>
              <Text style={styles.priceLabel}>Target</Text>
              <Text style={[styles.priceValue, { color: '#16a34a' }]}>
                {fmt(result.targetPrice)}
              </Text>
            </>
          )}
          {result.riskReward != null && (
            <>
              <Text style={styles.priceLabel}>R:R</Text>
              <Text style={[styles.priceValue, { color: result.riskReward >= 2 ? '#16a34a' : '#f59e0b' }]}>
                1:{result.riskReward.toFixed(1)}
              </Text>
            </>
          )}
        </View>
      )}

      {/* Options: strike + premium + IV rank */}
      {isOptions && result.strikePrice != null && (
        <View style={styles.priceRow}>
          <Text style={styles.priceLabel}>Strike</Text>
          <Text style={styles.priceValue}>{fmt(result.strikePrice)}</Text>
          {result.optionPremium != null && (
            <>
              <Text style={styles.priceLabel}>Premium</Text>
              <Text style={[styles.priceValue, { color: '#7e22ce' }]}>
                {fmt(result.optionPremium)}
              </Text>
            </>
          )}
          {result.ivRank != null && (
            <>
              <Text style={styles.priceLabel}>IVR</Text>
              <Text
                style={[
                  styles.priceValue,
                  {
                    color:
                      result.ivRank >= 70
                        ? '#ef4444'
                        : result.ivRank <= 30
                        ? '#16a34a'
                        : '#f59e0b',
                  },
                ]}
              >
                {result.ivRank.toFixed(0)}%
              </Text>
            </>
          )}
        </View>
      )}

      {/* Strength score bar */}
      <View style={styles.strengthRow}>
        <Text style={styles.strengthLabel}>Strength</Text>
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
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 14,
    marginHorizontal: 16,
    marginVertical: 5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 3,
    elevation: 2,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  symbol: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
    fontFamily: 'monospace',
    flex: 1,
  },
  dirBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 20,
  },
  dirText: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  optionsBadge: {
    backgroundColor: '#f3e8ff',
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 20,
  },
  optionsBadgeText: {
    fontSize: 10,
    color: '#7e22ce',
    fontWeight: '600',
  },
  signalName: {
    fontSize: 13,
    color: '#374151',
    fontWeight: '500',
    marginBottom: 8,
  },
  timeframe: {
    color: '#9ca3af',
    fontWeight: '400',
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 8,
  },
  priceLabel: {
    fontSize: 11,
    color: '#9ca3af',
    fontWeight: '500',
  },
  priceValue: {
    fontSize: 13,
    color: '#111827',
    fontWeight: '600',
    fontFamily: 'monospace',
    marginRight: 8,
  },
  strengthRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 2,
  },
  strengthLabel: {
    fontSize: 11,
    color: '#9ca3af',
    width: 54,
  },
  strengthBarBg: {
    flex: 1,
    height: 6,
    backgroundColor: '#e5e7eb',
    borderRadius: 3,
    overflow: 'hidden',
  },
  strengthBarFill: {
    height: '100%',
    borderRadius: 3,
  },
  strengthPct: {
    fontSize: 12,
    fontWeight: '600',
    width: 36,
    textAlign: 'right',
  },
});

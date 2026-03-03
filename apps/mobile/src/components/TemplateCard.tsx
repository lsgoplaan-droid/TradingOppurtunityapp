import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';
import type { ScanTemplate } from '../api/client';

interface Props {
  template: ScanTemplate;
  onRun: (template: ScanTemplate) => void;
  loading?: boolean;
}

const MARKET_COLORS: Record<string, { bg: string; text: string }> = {
  US: { bg: '#dbeafe', text: '#1d4ed8' },
  INDIA: { bg: '#ffedd5', text: '#c2410c' },
};

const ASSET_COLORS: Record<string, { bg: string; text: string }> = {
  EQUITY: { bg: '#dcfce7', text: '#15803d' },
  EQUITY_OPTIONS: { bg: '#f3e8ff', text: '#7e22ce' },
};

export function TemplateCard({ template, onRun, loading = false }: Props) {
  const marketStyle = MARKET_COLORS[template.market] ?? { bg: '#f3f4f6', text: '#374151' };
  const assetStyle = ASSET_COLORS[template.assetClass] ?? { bg: '#f3f4f6', text: '#374151' };
  const isMTF = template.type === 'mtf';

  return (
    <View style={styles.card}>
      {/* Header row: market + asset badges */}
      <View style={styles.badgeRow}>
        <View style={[styles.badge, { backgroundColor: marketStyle.bg }]}>
          <Text style={[styles.badgeText, { color: marketStyle.text }]}>
            {template.market}
          </Text>
        </View>
        <View style={[styles.badge, { backgroundColor: assetStyle.bg }]}>
          <Text style={[styles.badgeText, { color: assetStyle.text }]}>
            {template.assetClass === 'EQUITY_OPTIONS' ? 'Options' : 'Equity'}
          </Text>
        </View>
        {isMTF && (
          <View style={[styles.badge, { backgroundColor: '#e0e7ff' }]}>
            <Text style={[styles.badgeText, { color: '#4338ca' }]}>MTF</Text>
          </View>
        )}
        <Text style={styles.timeframe}>{template.timeframe}</Text>
      </View>

      {/* Template name */}
      <Text style={styles.name} numberOfLines={2}>
        {template.name}
      </Text>

      {/* Description */}
      <Text style={styles.description} numberOfLines={3}>
        {template.description}
      </Text>

      {/* MTF timeframes */}
      {isMTF && template.timeframes && template.timeframes.length > 0 && (
        <View style={styles.tfRow}>
          {template.timeframes.map((tf) => (
            <View key={tf} style={styles.tfBadge}>
              <Text style={styles.tfBadgeText}>{tf}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Run button */}
      <TouchableOpacity
        style={[styles.runButton, loading && styles.runButtonDisabled]}
        onPress={() => onRun(template)}
        disabled={loading}
        activeOpacity={0.7}
      >
        {loading ? (
          <ActivityIndicator size="small" color="#ffffff" />
        ) : (
          <Text style={styles.runButtonText}>Run Scan</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 14,
    marginHorizontal: 16,
    marginVertical: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.07,
    shadowRadius: 4,
    elevation: 2,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
    flexWrap: 'wrap',
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 20,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.3,
  },
  timeframe: {
    fontSize: 11,
    color: '#6b7280',
    marginLeft: 'auto',
    fontWeight: '500',
  },
  name: {
    fontSize: 15,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  description: {
    fontSize: 13,
    color: '#6b7280',
    lineHeight: 18,
    marginBottom: 10,
  },
  tfRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
    marginBottom: 10,
  },
  tfBadge: {
    backgroundColor: '#e0e7ff',
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 20,
  },
  tfBadgeText: {
    fontSize: 10,
    color: '#4338ca',
    fontWeight: '600',
  },
  runButton: {
    backgroundColor: '#4f46e5',
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: 'center',
  },
  runButtonDisabled: {
    backgroundColor: '#a5b4fc',
  },
  runButtonText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
  },
});

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

export interface MetricItem {
  label: string;
  value: string;
  /** When true → render value in green; false → red; undefined → neutral */
  positive?: boolean;
}

interface Props {
  metrics: MetricItem[];
  /** Number of columns — defaults to 2 */
  columns?: 2 | 4;
}

export function MetricsGrid({ metrics, columns = 2 }: Props) {
  return (
    <View style={[styles.grid, columns === 4 && styles.grid4]}>
      {metrics.map((m, i) => {
        const valueColor =
          m.positive === true
            ? '#16a34a'
            : m.positive === false
            ? '#dc2626'
            : '#111827';

        return (
          <View key={i} style={[styles.cell, columns === 4 && styles.cell4]}>
            <Text style={styles.label} numberOfLines={1}>
              {m.label}
            </Text>
            <Text style={[styles.value, { color: valueColor }]} numberOfLines={1}>
              {m.value}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  grid4: {
    // 4 columns — each cell takes ~25%
  },
  cell: {
    backgroundColor: '#f9fafb',
    borderRadius: 10,
    padding: 12,
    width: '47.5%',   // 2-col
    borderWidth: 1,
    borderColor: '#f3f4f6',
  },
  cell4: {
    width: '22%',      // 4-col
    padding: 10,
  },
  label: {
    fontSize: 11,
    color: '#6b7280',
    fontWeight: '500',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
    marginBottom: 4,
  },
  value: {
    fontSize: 16,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
});

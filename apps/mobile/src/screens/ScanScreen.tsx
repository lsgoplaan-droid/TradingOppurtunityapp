import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
  SectionList,
  RefreshControl,
  Alert,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import {
  fetchTemplates,
  runScan,
  runMTFScan,
  ScanTemplate,
  ScanResult,
} from '../api/client';
import { TemplateCard } from '../components/TemplateCard';
import { ResultCard } from '../components/ResultCard';
import type { ScanStackParamList } from '../navigation/types';

type NavProp = NativeStackNavigationProp<ScanStackParamList, 'ScanList'>;

// Group templates by "market|assetClass"
type TemplateSection = {
  title: string;
  data: ScanTemplate[];
};

function groupTemplates(templates: ScanTemplate[]): TemplateSection[] {
  const map = new Map<string, ScanTemplate[]>();
  for (const t of templates) {
    const key = `${t.market} · ${t.assetClass === 'EQUITY_OPTIONS' ? 'Options' : 'Equity'}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(t);
  }
  return Array.from(map.entries()).map(([title, data]) => ({ title, data }));
}

type TabId = 'TEMPLATES' | 'RESULTS';

export function ScanScreen() {
  const navigation = useNavigation<NavProp>();

  const [tab, setTab] = useState<TabId>('TEMPLATES');
  const [market, setMarket] = useState<'US' | 'INDIA'>('US');

  const [templates, setTemplates] = useState<ScanTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templatesError, setTemplatesError] = useState<string | null>(null);

  const [runningId, setRunningId] = useState<string | null>(null);
  const [results, setResults] = useState<ScanResult[]>([]);

  // Load templates whenever market changes
  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    setTemplatesError(null);
    try {
      const data = await fetchTemplates(market);
      setTemplates(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setTemplatesError(msg);
    } finally {
      setTemplatesLoading(false);
    }
  }, [market]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const handleRunTemplate = useCallback(
    async (template: ScanTemplate) => {
      setRunningId(template.id);
      try {
        const data =
          template.type === 'mtf'
            ? await runMTFScan(template.id, market)
            : await runScan({ templateId: template.id }, market);
        setResults(data);
        setTab('RESULTS');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        Alert.alert('Scan Failed', msg);
      } finally {
        setRunningId(null);
      }
    },
    [market]
  );

  const handleResultPress = useCallback(
    (result: ScanResult) => {
      navigation.navigate('ScanDetail', { result });
    },
    [navigation]
  );

  // -----------------------------------------------------------------------
  // Render helpers
  // -----------------------------------------------------------------------

  const sections = groupTemplates(templates);

  const renderTemplateItem = ({ item }: { item: ScanTemplate }) => (
    <TemplateCard
      template={item}
      onRun={handleRunTemplate}
      loading={runningId === item.id}
    />
  );

  const renderSectionHeader = ({ section }: { section: TemplateSection }) => (
    <View style={styles.sectionHeader}>
      <Text style={styles.sectionHeaderText}>{section.title}</Text>
    </View>
  );

  return (
    <View style={styles.container}>
      {/* Market toggle */}
      <View style={styles.marketToggle}>
        <TouchableOpacity
          style={[styles.marketBtn, market === 'US' && styles.marketBtnActive]}
          onPress={() => setMarket('US')}
        >
          <Text
            style={[
              styles.marketBtnText,
              market === 'US' && styles.marketBtnTextActive,
            ]}
          >
            US Markets
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.marketBtn, market === 'INDIA' && styles.marketBtnActive]}
          onPress={() => setMarket('INDIA')}
        >
          <Text
            style={[
              styles.marketBtnText,
              market === 'INDIA' && styles.marketBtnTextActive,
            ]}
          >
            India (NSE)
          </Text>
        </TouchableOpacity>
      </View>

      {/* Tab bar */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabBtn, tab === 'TEMPLATES' && styles.tabBtnActive]}
          onPress={() => setTab('TEMPLATES')}
        >
          <Text
            style={[
              styles.tabBtnText,
              tab === 'TEMPLATES' && styles.tabBtnTextActive,
            ]}
          >
            Templates
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tabBtn, tab === 'RESULTS' && styles.tabBtnActive]}
          onPress={() => setTab('RESULTS')}
        >
          <Text
            style={[
              styles.tabBtnText,
              tab === 'RESULTS' && styles.tabBtnTextActive,
            ]}
          >
            Results {results.length > 0 ? `(${results.length})` : ''}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Content */}
      {tab === 'TEMPLATES' && (
        <>
          {templatesLoading && templates.length === 0 ? (
            <View style={styles.centered}>
              <ActivityIndicator size="large" color="#4f46e5" />
              <Text style={styles.loadingText}>Loading templates…</Text>
            </View>
          ) : templatesError ? (
            <View style={styles.centered}>
              <Text style={styles.errorText}>{templatesError}</Text>
              <TouchableOpacity style={styles.retryBtn} onPress={loadTemplates}>
                <Text style={styles.retryBtnText}>Retry</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <SectionList
              sections={sections}
              keyExtractor={(item) => item.id}
              renderItem={renderTemplateItem}
              renderSectionHeader={renderSectionHeader}
              contentContainerStyle={styles.listContent}
              stickySectionHeadersEnabled={false}
              refreshControl={
                <RefreshControl
                  refreshing={templatesLoading}
                  onRefresh={loadTemplates}
                  tintColor="#4f46e5"
                />
              }
            />
          )}
        </>
      )}

      {tab === 'RESULTS' && (
        <>
          {results.length === 0 ? (
            <View style={styles.centered}>
              <Text style={styles.emptyText}>No results yet.</Text>
              <Text style={styles.emptySubText}>
                Go to Templates and tap Run Scan.
              </Text>
            </View>
          ) : (
            <FlatList
              data={results}
              keyExtractor={(item) => item.id}
              renderItem={({ item }) => (
                <ResultCard result={item} onPress={handleResultPress} />
              )}
              contentContainerStyle={styles.listContent}
            />
          )}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f9fafb',
  },
  marketToggle: {
    flexDirection: 'row',
    backgroundColor: '#ffffff',
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  marketBtn: {
    flex: 1,
    paddingVertical: 7,
    borderRadius: 8,
    alignItems: 'center',
    backgroundColor: '#f3f4f6',
  },
  marketBtnActive: {
    backgroundColor: '#4f46e5',
  },
  marketBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6b7280',
  },
  marketBtnTextActive: {
    color: '#ffffff',
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#ffffff',
    paddingHorizontal: 16,
    paddingBottom: 8,
    gap: 8,
  },
  tabBtn: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  tabBtnActive: {
    backgroundColor: '#eef2ff',
  },
  tabBtnText: {
    fontSize: 13,
    color: '#6b7280',
    fontWeight: '500',
  },
  tabBtnTextActive: {
    color: '#4f46e5',
    fontWeight: '700',
  },
  sectionHeader: {
    backgroundColor: '#f9fafb',
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 6,
  },
  sectionHeaderText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  listContent: {
    paddingBottom: 32,
    paddingTop: 8,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    padding: 24,
  },
  loadingText: {
    color: '#6b7280',
    fontSize: 14,
    marginTop: 8,
  },
  errorText: {
    color: '#dc2626',
    fontSize: 14,
    textAlign: 'center',
  },
  retryBtn: {
    backgroundColor: '#4f46e5',
    paddingVertical: 9,
    paddingHorizontal: 20,
    borderRadius: 8,
  },
  retryBtnText: {
    color: '#ffffff',
    fontWeight: '600',
    fontSize: 14,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
  emptySubText: {
    fontSize: 13,
    color: '#9ca3af',
    textAlign: 'center',
  },
});

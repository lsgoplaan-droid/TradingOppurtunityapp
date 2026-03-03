import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { ScanResult } from '../api/client';

// Root stack — lives inside the bottom tab for Scanner
export type ScanStackParamList = {
  ScanList: undefined;
  ScanDetail: { result: ScanResult };
};

// Bottom tab param list
export type RootTabParamList = {
  Scanner: undefined;
  Backtest: undefined;
};

export type ScanListScreenProps = NativeStackScreenProps<ScanStackParamList, 'ScanList'>;
export type ScanDetailScreenProps = NativeStackScreenProps<ScanStackParamList, 'ScanDetail'>;

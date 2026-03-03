import 'react-native-gesture-handler'; // must be first import
import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { AppNavigator } from './src/navigation/AppNavigator';

export default function App() {
  return (
    <>
      <StatusBar style="light" backgroundColor="#4f46e5" />
      <AppNavigator />
    </>
  );
}

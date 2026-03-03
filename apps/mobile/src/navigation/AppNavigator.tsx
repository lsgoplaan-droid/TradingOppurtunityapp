import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import { ScanScreen } from '../screens/ScanScreen';
import { ScanDetailScreen } from '../screens/ScanDetailScreen';
import { BacktestScreen } from '../screens/BacktestScreen';

import type { RootTabParamList, ScanStackParamList } from './types';

// ----------------------------------------------------------------
// Design tokens
// ----------------------------------------------------------------
const PRIMARY = '#4f46e5';   // indigo-600
const INACTIVE = '#9ca3af';  // gray-400
const BG = '#f9fafb';

// ----------------------------------------------------------------
// Scanner stack (ScanScreen → ScanDetailScreen)
// ----------------------------------------------------------------
const ScanStack = createNativeStackNavigator<ScanStackParamList>();

function ScanStackNavigator() {
  return (
    <ScanStack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: PRIMARY },
        headerTintColor: '#ffffff',
        headerTitleStyle: { fontWeight: '600', fontSize: 17 },
      }}
    >
      <ScanStack.Screen
        name="ScanList"
        component={ScanScreen}
        options={{ title: 'Scanner' }}
      />
      <ScanStack.Screen
        name="ScanDetail"
        component={ScanDetailScreen}
        options={{ title: 'Signal Detail' }}
      />
    </ScanStack.Navigator>
  );
}

// ----------------------------------------------------------------
// Bottom tab navigator
// ----------------------------------------------------------------
const Tab = createBottomTabNavigator<RootTabParamList>();

export function AppNavigator() {
  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          headerShown: false,
          tabBarActiveTintColor: PRIMARY,
          tabBarInactiveTintColor: INACTIVE,
          tabBarStyle: {
            backgroundColor: '#ffffff',
            borderTopColor: '#e5e7eb',
            paddingBottom: 4,
            height: 60,
          },
          tabBarLabelStyle: { fontSize: 12, fontWeight: '500' },
          tabBarIcon: ({ focused, color, size }) => {
            let iconName: keyof typeof Ionicons.glyphMap;
            if (route.name === 'Scanner') {
              iconName = focused ? 'search' : 'search-outline';
            } else {
              iconName = focused ? 'bar-chart' : 'bar-chart-outline';
            }
            return <Ionicons name={iconName} size={size} color={color} />;
          },
        })}
      >
        <Tab.Screen
          name="Scanner"
          component={ScanStackNavigator}
          options={{ tabBarLabel: 'Scanner' }}
        />
        <Tab.Screen
          name="Backtest"
          component={BacktestScreen}
          options={{
            tabBarLabel: 'Backtest',
            headerShown: true,
            headerStyle: { backgroundColor: PRIMARY },
            headerTintColor: '#ffffff',
            headerTitleStyle: { fontWeight: '600', fontSize: 17 },
            title: 'Backtest',
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

# TradingOpportunity Mobile App

React Native + Expo app that connects to the FastAPI backend at `http://localhost:8000`
(Android emulator: `http://10.0.2.2:8000`).

## Prerequisites

- Node.js 18+
- Expo CLI: `npm install -g expo-cli`
- EAS CLI: `npm install -g eas-cli`
- An Expo account (free) at https://expo.dev

## Generate placeholder assets (first time only)

The `assets/` folder needs PNG files before the app can start.
Run the included helper script once:

```bash
cd apps/mobile
C:/Python314/python.exe create_assets.py
```

This writes 1×1 transparent PNG placeholders for `icon.png`, `adaptive-icon.png`,
and `splash-icon.png`. Replace them with real 1024×1024 images before publishing.

## Local development

```bash
cd apps/mobile
npm install
npx expo start          # shows QR code for Expo Go on your phone
npx expo start --android  # launches in Android emulator (requires Android Studio)
npx expo start --ios      # launches in iOS Simulator (macOS only)
```

### Backend URL

The API client (`src/api/client.ts`) auto-selects the base URL:

| Runtime | URL used |
|---------|----------|
| iOS simulator | `http://localhost:8000` |
| Android emulator | `http://10.0.2.2:8000` |
| Physical Android/iOS | Edit `API_BASE` in `src/api/client.ts` to use your LAN IP e.g. `http://192.168.1.100:8000` |

## Building an APK (Android)

```bash
cd apps/mobile
npm install
npx eas login                                       # login to Expo account
npx eas build --platform android --profile preview  # builds APK (not AAB)
```

After the build completes, the Expo dashboard prints a download URL for the `.apk` file.
Install it on any Android device with "Install from unknown sources" enabled.

## Building for production (Play Store)

```bash
npx eas build --platform android --profile production
```

This produces an `.aab` (Android App Bundle) suitable for Google Play submission.

## iOS (App Store / TestFlight)

```bash
npx eas build --platform ios --profile production
```

Requires an Apple Developer account ($99/year).

## Project structure

```
apps/mobile/
  App.tsx                        Entry point
  app.json                       Expo config
  eas.json                       EAS Build profiles
  src/
    api/client.ts                All API calls + TypeScript interfaces
    navigation/
      AppNavigator.tsx           Bottom tab nav (Scanner | Backtest)
      types.ts                   Navigation param types
    screens/
      ScanScreen.tsx             Template list + results list
      ScanDetailScreen.tsx       Full detail view for a scan result
      BacktestScreen.tsx         Backtest form + equity curve + trade list
    components/
      TemplateCard.tsx           Single template card with Run button
      ResultCard.tsx             Compact scan result card
      MetricsGrid.tsx            Reusable 2- or 4-column metrics grid
  assets/                        PNG icons (generate with create_assets.py)
```

## Tech stack

| Library | Purpose |
|---------|---------|
| Expo ~53 | Build tooling, OTA updates, EAS cloud builds |
| React Native 0.76 | Core framework |
| @react-navigation/native + bottom-tabs | Navigation |
| @react-navigation/native-stack | Stack navigator inside Scanner tab |
| react-native-svg | SVG equity curve chart |
| @expo/vector-icons (Ionicons) | Tab bar icons |
| TypeScript | Type safety |

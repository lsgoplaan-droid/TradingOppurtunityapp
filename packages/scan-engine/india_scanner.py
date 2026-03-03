"""India-specific scan engine that handles F&O conditions (PCR, Max Pain, GEX)."""
import asyncio
import math as _math
import time
from datetime import date, timedelta
from uuid import uuid4
from typing import Optional

import numpy as np

from packages.data_adapters.base import DataAdapter
from packages.indicator_engine.indicators import (
    compute_sma,
    compute_ema,
    compute_rsi,
    compute_adx,
    compute_atr,
    compute_macd,
    compute_roc,
    compute_stochastic,
    compute_bollinger_bands,
    compute_bb_width,
    compute_obv,
    compute_vwap,
    crosses_above,
    crosses_below,
)
from packages.indicator_engine.options_indicators import (
    compute_iv_rank,
    compute_iv_percentile,
    compute_pcr,
    compute_max_pain,
    compute_gamma_exposure,
)
from packages.indicator_engine.iv_history import IVHistoryStore


def _safe_last(arr: np.ndarray) -> float:
    """Return the last non-NaN value from an array, or NaN if all NaN."""
    if arr is None or len(arr) == 0:
        return float("nan")
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return float("nan")
    return float(valid[-1])


def _india_norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + _math.erf(x / _math.sqrt(2.0)))


def _india_bs_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, S - K)
    d1 = (_math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * _math.sqrt(T))
    d2 = d1 - sigma * _math.sqrt(T)
    return S * _india_norm_cdf(d1) - K * _math.exp(-r * T) * _india_norm_cdf(d2)


def _india_atm_strike(price: float) -> float:
    """Round to nearest NSE F&O strike increment (₹50 for index, ₹5 for stocks)."""
    if price <= 0 or _math.isnan(price):
        return price
    if price > 10000:   # index like Nifty (18000-25000)
        increment = 50.0
    elif price > 2000:  # BankNifty range
        increment = 100.0
    elif price > 500:
        increment = 20.0
    elif price > 100:
        increment = 10.0
    else:
        increment = 5.0
    return round(price / increment) * increment


def _india_infer_direction(signal_name: str) -> str:
    name = signal_name.lower()
    if any(k in name for k in ('bearish', 'put', 'sell', 'death', 'breakdown')):
        return 'SELL'
    if any(k in name for k in ('straddle', 'condor', 'strangle', 'neutral', 'range')):
        return 'NEUTRAL'
    return 'BUY'


class IndiaScanEngine:
    """
    Extended scan engine for India markets.

    Handles equity conditions identically to ScanEngine (from scanner.py)
    but ALSO handles F&O-specific condition types:
    - near_max_pain: spot within threshold_pct of max pain
    - high_gex: net GEX > threshold
    - pcr_above / pcr_below: OI PCR comparisons
    """

    def __init__(
        self,
        data_adapter: DataAdapter,
        iv_store: Optional[IVHistoryStore] = None,
    ):
        self.adapter = data_adapter
        if iv_store is not None:
            self.iv_store = iv_store
        else:
            # Use None so IVHistoryStore creates its default file-based SQLite DB.
            # Passing ":memory:" directly causes os.makedirs("") to fail.
            self.iv_store = IVHistoryStore()

    async def run(self, rule, symbols: list[str]) -> list[dict]:
        """Run rule against all symbols concurrently."""
        tasks = [self._evaluate(rule, symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    @staticmethod
    def _rule_attr(rule, snake_key: str, camel_key: str, default=None):
        """
        Get a rule attribute supporting both ScanRule Pydantic models (snake_case)
        and plain dicts (camelCase from JSON templates).
        """
        # Try attribute access first (ScanRule Pydantic model)
        val = getattr(rule, snake_key, None)
        if val is not None:
            return val
        # Fall back to dict-style access (plain dict rules)
        if isinstance(rule, dict):
            return rule.get(camel_key, rule.get(snake_key, default))
        return default

    async def _evaluate(self, rule, symbol: str) -> Optional[dict]:
        """
        Fetch candles, compute indicators, evaluate conditions, return result dict or None.

        Returns None if:
        - Not enough candles are available
        - Any unrecoverable exception occurs
        """
        try:
            today = date.today()
            from_date = (today - timedelta(days=400)).isoformat()
            to_date = today.isoformat()

            timeframe = self._rule_attr(rule, "timeframe", "timeframe", "1day")
            min_candles = self._rule_attr(rule, "min_candles", "minCandles", 50)
            asset_class = self._rule_attr(rule, "asset_class", "assetClass", "EQUITY")
            market = self._rule_attr(rule, "market", "market", "INDIA")
            signal_name = self._rule_attr(rule, "signal_name", "signalName", "Signal")
            template_id = self._rule_attr(rule, "template_id", "templateId", "")
            conditions = self._rule_attr(rule, "conditions", "conditions", [])

            candles = await self.adapter.get_candles(
                symbol, timeframe, from_date, to_date
            )

            if not candles or len(candles) < min_candles:
                return None

            # Compute equity indicators (always needed)
            indicators = self._compute_equity_indicators(candles)

            # For F&O templates, also fetch option chain and compute F&O indicators
            if asset_class == "EQUITY_OPTIONS":
                fo_indicators = await self._compute_fo_indicators(symbol, indicators)
                indicators.update(fo_indicators)

            # Evaluate each condition
            conditions_met = 0
            total_conditions = len(conditions)

            for condition in conditions:
                if self._evaluate_condition(condition, indicators):
                    conditions_met += 1

            strength_score = (
                (conditions_met / total_conditions * 100)
                if total_conditions > 0
                else 0.0
            )

            # Build indicator values dict (scalar values only, skip arrays)
            indicator_values = {
                k: v
                for k, v in indicators.items()
                if not k.startswith("_") and isinstance(v, (int, float))
                and not (isinstance(v, float) and np.isnan(v))
            }

            entry_price = indicators.get("close", float("nan"))

            # Options fields (populated only for EQUITY_OPTIONS)
            option_premium_i: Optional[float] = None
            profit_probability_i: Optional[float] = None
            strike_price_i: Optional[float] = None
            spread_debit_i: Optional[float] = None
            spread_max_profit_i: Optional[float] = None
            spread_width_i: Optional[float] = None
            suggested_spread_i: Optional[str] = None

            if asset_class == 'EQUITY_OPTIONS' and entry_price and not _math.isnan(entry_price) and entry_price > 0:
                close_arr_i = np.array([c["close"] for c in candles])
                if len(close_arr_i) >= 21:
                    log_ret_i = np.log(close_arr_i[1:] / close_arr_i[:-1])
                    sigma_i = float(np.std(log_ret_i[-20:], ddof=1)) * _math.sqrt(252)
                else:
                    sigma_i = 0.20
                sigma_i = max(sigma_i, 0.05)
                T_i = 30.0 / 365.0
                r_i = 0.065  # India risk-free rate ~6.5%
                S_i = float(entry_price)
                call_p = _india_bs_call(S_i, S_i, T_i, r_i, sigma_i)
                put_p = max(call_p + S_i * (_math.exp(-r_i * T_i) - 1), 0.0)
                if T_i > 0 and sigma_i > 0:
                    d1_i = (r_i + 0.5 * sigma_i ** 2) * T_i / (sigma_i * _math.sqrt(T_i))
                    d2_i = d1_i - sigma_i * _math.sqrt(T_i)
                else:
                    d2_i = 0.0

                strike_price_i = _india_atm_strike(S_i)
                dir_i = _india_infer_direction(signal_name)
                otm = 0.05
                if dir_i == 'SELL':
                    option_premium_i = round(put_p, 2)
                    profit_probability_i = round(_india_norm_cdf(-d2_i) * 100, 1)
                    K_otm_i = S_i * (1.0 - otm)
                    otm_put_i = max(_india_bs_call(S_i, K_otm_i, T_i, r_i, sigma_i) + S_i * (_math.exp(-r_i * T_i) - 1), 0.0)
                    spread_debit_i = round(max(put_p - otm_put_i, 0.0), 2)
                    spread_width_i = round(S_i * otm, 2)
                    spread_max_profit_i = round(max(spread_width_i - spread_debit_i, 0.0), 2)
                    suggested_spread_i = 'LONG_PUT_SPREAD'
                elif dir_i == 'NEUTRAL':
                    option_premium_i = round(call_p + put_p, 2)
                    profit_probability_i = round((2.0 * _india_norm_cdf(1.0) - 1.0) * 100, 1)
                    suggested_spread_i = None
                else:
                    option_premium_i = round(call_p, 2)
                    profit_probability_i = round(_india_norm_cdf(d2_i) * 100, 1)
                    K_otm_i = S_i * (1.0 + otm)
                    otm_call_i = _india_bs_call(S_i, K_otm_i, T_i, r_i, sigma_i)
                    spread_debit_i = round(max(call_p - otm_call_i, 0.0), 2)
                    spread_width_i = round(S_i * otm, 2)
                    spread_max_profit_i = round(max(spread_width_i - spread_debit_i, 0.0), 2)
                    suggested_spread_i = 'LONG_CALL_SPREAD'

            return {
                "id": str(uuid4()),
                "symbol": symbol,
                "market": market,
                "assetClass": asset_class,
                "signalName": signal_name,
                "templateId": template_id,
                "timeframe": timeframe,
                "strengthScore": float(strength_score),
                "timestamp": int(time.time() * 1000),
                "indicatorValues": indicator_values,
                "strikePrice": strike_price_i,
                "optionPremium": option_premium_i,
                "profitProbability": profit_probability_i,
                "suggestedSpread": suggested_spread_i,
                "spreadDebit": spread_debit_i,
                "spreadWidth": spread_width_i,
                "spreadMaxProfit": spread_max_profit_i,
            }

        except Exception:
            return None

    def _compute_equity_indicators(self, candles: list[dict]) -> dict:
        """Compute all equity indicators, return dict of last values and full arrays."""
        close = np.array([c["close"] for c in candles], dtype=np.float64)
        high = np.array([c["high"] for c in candles], dtype=np.float64)
        low = np.array([c["low"] for c in candles], dtype=np.float64)
        volume = np.array([c["volume"] for c in candles], dtype=np.float64)

        # EMAs
        ema20_arr = compute_ema(close, 20)
        ema50_arr = compute_ema(close, 50)
        ema200_arr = compute_ema(close, 200)

        # SMAs
        sma20_arr = compute_sma(close, 20)
        sma50_arr = compute_sma(close, 50)
        sma200_arr = compute_sma(close, 200)

        # RSI
        rsi_arr = compute_rsi(close, 14)

        # MACD
        macd_line_arr, macd_signal_arr, macd_hist_arr = compute_macd(close, 12, 26, 9)

        # ROC
        roc_arr = compute_roc(close, 10)

        # Stochastic
        stoch_k_arr, stoch_d_arr = compute_stochastic(high, low, close, 14, 3)

        # Bollinger Bands
        bb_upper_arr, bb_middle_arr, bb_lower_arr = compute_bollinger_bands(close, 20, 2.0)
        bb_width_arr = compute_bb_width(close, 20, 2.0)

        # ATR
        atr_arr = compute_atr(high, low, close, 14)

        # ADX (returns tuple of adx, plus_di, minus_di)
        adx_result = compute_adx(high, low, close, 14)
        adx_arr = adx_result[0] if isinstance(adx_result, tuple) else adx_result

        # OBV
        obv_arr = compute_obv(close, volume)

        # VWAP
        vwap_arr = compute_vwap(high, low, close, volume)

        return {
            # Full arrays (prefixed with underscore) for crossover detection
            "_ema20": ema20_arr,
            "_ema50": ema50_arr,
            "_ema200": ema200_arr,
            "_sma20": sma20_arr,
            "_sma50": sma50_arr,
            "_sma200": sma200_arr,
            "_rsi": rsi_arr,
            "_macd_line": macd_line_arr,
            "_macd_signal": macd_signal_arr,
            "_macd_hist": macd_hist_arr,
            "_roc": roc_arr,
            "_stoch_k": stoch_k_arr,
            "_stoch_d": stoch_d_arr,
            "_bb_upper": bb_upper_arr,
            "_bb_middle": bb_middle_arr,
            "_bb_lower": bb_lower_arr,
            "_bb_width": bb_width_arr,
            "_atr": atr_arr,
            "_adx": adx_arr,
            "_obv": obv_arr,
            "_vwap": vwap_arr,
            "_volume": volume,
            "_close": close,
            # Scalar last values for conditions
            "ema20": _safe_last(ema20_arr),
            "ema50": _safe_last(ema50_arr),
            "ema200": _safe_last(ema200_arr),
            "sma20": _safe_last(sma20_arr),
            "sma50": _safe_last(sma50_arr),
            "sma200": _safe_last(sma200_arr),
            "rsi": _safe_last(rsi_arr),
            "macd_line": _safe_last(macd_line_arr),
            "macd_signal": _safe_last(macd_signal_arr),
            "macd_hist": _safe_last(macd_hist_arr),
            "roc": _safe_last(roc_arr),
            "stoch_k": _safe_last(stoch_k_arr),
            "stoch_d": _safe_last(stoch_d_arr),
            "bb_upper": _safe_last(bb_upper_arr),
            "bb_middle": _safe_last(bb_middle_arr),
            "bb_lower": _safe_last(bb_lower_arr),
            "bb_width": _safe_last(bb_width_arr),
            "atr": _safe_last(atr_arr),
            "adx": _safe_last(adx_arr),
            "obv": _safe_last(obv_arr),
            "vwap": _safe_last(vwap_arr),
            "close": float(close[-1]) if len(close) > 0 else float("nan"),
            "volume": float(volume[-1]) if len(volume) > 0 else float("nan"),
        }

    async def _compute_fo_indicators(
        self, symbol: str, equity_indicators: dict
    ) -> dict:
        """Fetch option chain and compute F&O indicators."""
        chain = await self.adapter.get_option_chain(symbol)
        spot = chain.get("spot", equity_indicators.get("close", 0.0))

        # Aggregate OI and volume across all strikes
        calls = chain.get("calls", [])
        puts = chain.get("puts", [])

        total_call_oi = sum(c.get("oi", 0) for c in calls)
        total_put_oi = sum(p.get("oi", 0) for p in puts)
        total_call_vol = sum(c.get("volume", 0) for c in calls)
        total_put_vol = sum(p.get("volume", 0) for p in puts)

        # PCR — compute_pcr returns {pcr_oi, pcr_vol, sentiment_oi}
        pcr_result = compute_pcr(total_put_oi, total_call_oi, total_put_vol, total_call_vol)

        # Max pain
        max_pain_price = compute_max_pain(chain)

        # Net GEX — compute_gamma_exposure returns a float
        net_gex = compute_gamma_exposure(chain)

        # IV: average ATM IV across calls and puts
        all_options = calls + puts
        iv_values = [o.get("iv", 0.0) for o in all_options if o.get("iv", 0.0) > 0]
        current_iv = float(np.mean(iv_values)) if iv_values else 0.18

        # IV history from store (may be empty; compute_iv_rank handles it)
        expiry = chain.get("expiry", "ANY")
        iv_history = self.iv_store.get_iv_history(symbol, expiry)

        iv_rank_val = compute_iv_rank(current_iv, iv_history)
        iv_percentile_val = compute_iv_percentile(current_iv, iv_history)

        return {
            # Map pcr_oi -> oi_pcr to match template condition indicator names
            "oi_pcr": pcr_result["pcr_oi"],
            "vol_pcr": pcr_result["pcr_vol"],
            "iv_rank": iv_rank_val,
            "iv_percentile": iv_percentile_val,
            "max_pain": max_pain_price,
            "net_gex": net_gex,
            "spot": spot,
        }

    def _evaluate_condition(self, condition: dict, indicators: dict) -> bool:
        """Evaluate a single condition dict against indicator values."""
        cond_type = condition.get("type", "")

        if cond_type == "crosses_above":
            ind_key = condition.get("indicator", "")
            ref_key = condition.get("reference", "")
            ind_arr = indicators.get(f"_{ind_key}")
            ref_arr = indicators.get(f"_{ref_key}")
            if ind_arr is None or ref_arr is None:
                return False
            crosses = crosses_above(ind_arr, ref_arr)
            return bool(crosses[-1]) if len(crosses) > 0 else False

        elif cond_type == "crosses_below":
            ind_key = condition.get("indicator", "")
            ref_key = condition.get("reference", "")
            ind_arr = indicators.get(f"_{ind_key}")
            ref_arr = indicators.get(f"_{ref_key}")
            if ind_arr is None or ref_arr is None:
                return False
            crosses = crosses_below(ind_arr, ref_arr)
            return bool(crosses[-1]) if len(crosses) > 0 else False

        elif cond_type == "greater_than":
            ind_key = condition.get("indicator", "")
            # Support "reference" as another indicator name
            if "reference" in condition:
                ref_val = indicators.get(condition["reference"], float("nan"))
                ind_val = indicators.get(ind_key, float("nan"))
                if isinstance(ind_val, float) and np.isnan(ind_val):
                    return False
                if isinstance(ref_val, float) and np.isnan(ref_val):
                    return False
                return float(ind_val) > float(ref_val)
            threshold = condition.get("value", 0)
            ind_val = indicators.get(ind_key, float("nan"))
            if isinstance(ind_val, float) and np.isnan(ind_val):
                return False
            return float(ind_val) > float(threshold)

        elif cond_type == "less_than":
            ind_key = condition.get("indicator", "")
            if "reference" in condition:
                ref_val = indicators.get(condition["reference"], float("nan"))
                ind_val = indicators.get(ind_key, float("nan"))
                if isinstance(ind_val, float) and np.isnan(ind_val):
                    return False
                if isinstance(ref_val, float) and np.isnan(ref_val):
                    return False
                return float(ind_val) < float(ref_val)
            threshold = condition.get("value", 0)
            ind_val = indicators.get(ind_key, float("nan"))
            if isinstance(ind_val, float) and np.isnan(ind_val):
                return False
            return float(ind_val) < float(threshold)

        elif cond_type == "between":
            ind_key = condition.get("indicator", "")
            min_val = condition.get("min", float("-inf"))
            max_val = condition.get("max", float("inf"))
            ind_val = indicators.get(ind_key, float("nan"))
            if isinstance(ind_val, float) and np.isnan(ind_val):
                return False
            return float(min_val) <= float(ind_val) <= float(max_val)

        elif cond_type == "volume_surge":
            # Check if current volume exceeds threshold * 20-bar average
            threshold = condition.get("threshold", 1.5)
            vol_arr = indicators.get("_volume")
            if vol_arr is None or len(vol_arr) < 21:
                # Placeholder: not enough data — return True to avoid blocking template
                return True
            avg_vol = float(np.mean(vol_arr[-21:-1]))
            current_vol = float(vol_arr[-1])
            if avg_vol == 0:
                return False
            return current_vol > threshold * avg_vol

        elif cond_type == "near_max_pain":
            # Spot within threshold_pct % of max pain
            threshold_pct = condition.get("threshold_pct", 1.0)
            spot = indicators.get("spot", indicators.get("close", float("nan")))
            max_pain_val = indicators.get("max_pain", float("nan"))
            if isinstance(spot, float) and np.isnan(spot):
                return False
            if isinstance(max_pain_val, float) and np.isnan(max_pain_val):
                return False
            if float(max_pain_val) == 0:
                return False
            distance_pct = abs(float(spot) - float(max_pain_val)) / float(max_pain_val) * 100
            return distance_pct <= threshold_pct

        elif cond_type == "high_gex":
            # Net GEX above threshold
            threshold = condition.get("threshold", 0)
            net_gex_val = indicators.get("net_gex", float("nan"))
            if isinstance(net_gex_val, float) and np.isnan(net_gex_val):
                return False
            return float(net_gex_val) > float(threshold)

        elif cond_type == "pcr_above":
            threshold = condition.get("value", 0)
            oi_pcr_val = indicators.get("oi_pcr", float("nan"))
            if isinstance(oi_pcr_val, float) and np.isnan(oi_pcr_val):
                return False
            return float(oi_pcr_val) > float(threshold)

        elif cond_type == "pcr_below":
            threshold = condition.get("value", 0)
            oi_pcr_val = indicators.get("oi_pcr", float("nan"))
            if isinstance(oi_pcr_val, float) and np.isnan(oi_pcr_val):
                return False
            return float(oi_pcr_val) < float(threshold)

        # Unknown condition type — do not block
        return False

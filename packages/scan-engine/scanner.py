"""Core scan engine — evaluates ScanRule conditions against live/mock market data."""
import asyncio
import math as _math
import time
from datetime import date, timedelta
from typing import Optional
from uuid import uuid4

import numpy as np
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Inline Black-Scholes helpers (no circular import)
# ---------------------------------------------------------------------------

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + _math.erf(x / _math.sqrt(2.0)))


def _bs_call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """ATM call price via Black-Scholes."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, S - K)
    d1 = (_math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * _math.sqrt(T))
    d2 = d1 - sigma * _math.sqrt(T)
    return S * _norm_cdf(d1) - K * _math.exp(-r * T) * _norm_cdf(d2)


def _infer_direction(signal_name: str) -> str:
    """Infer BUY / SELL / NEUTRAL from the signal name."""
    name = signal_name.lower()
    if any(k in name for k in ('death', 'bearish', 'overbought', 'put', 'pcr bear', 'sell')):
        return 'SELL'
    if any(k in name for k in ('straddle', 'condor', 'strangle', 'neutral', 'max pain', 'gamma')):
        return 'NEUTRAL'
    return 'BUY'


def _atm_strike(price: float) -> float:
    """Round stock price to the nearest standard option strike increment."""
    if price <= 0 or _math.isnan(price):
        return price
    if price < 10:
        increment = 0.5
    elif price < 25:
        increment = 1.0
    elif price < 200:
        increment = 5.0
    else:
        increment = 10.0
    return round(price / increment) * increment


def _bs_greeks(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> dict:
    """Black-Scholes Greeks. theta is per calendar day; vega is per 1% IV move."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    d1 = (_math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * _math.sqrt(T))
    d2 = d1 - sigma * _math.sqrt(T)
    npdf_d1 = _math.exp(-0.5 * d1 ** 2) / _math.sqrt(2.0 * _math.pi)
    delta = _norm_cdf(d1) if option_type == "call" else _norm_cdf(d1) - 1.0
    gamma = npdf_d1 / (S * sigma * _math.sqrt(T))
    if option_type == "call":
        theta_term2 = r * K * _math.exp(-r * T) * _norm_cdf(d2)
    else:
        theta_term2 = -r * K * _math.exp(-r * T) * _norm_cdf(-d2)
    theta = (-(S * npdf_d1 * sigma) / (2.0 * _math.sqrt(T)) - theta_term2) / 365.0
    vega = S * npdf_d1 * _math.sqrt(T) / 100.0
    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega":  round(vega, 4),
    }


def _iv_rank_from_prices(close_arr: np.ndarray) -> float:
    """IV rank (0-100) from last 252 bars of rolling 20-day annualised realised vol."""
    if len(close_arr) < 22:
        return float("nan")
    log_ret = np.log(close_arr[1:] / close_arr[:-1])
    n = len(log_ret)
    vols = [
        float(np.std(log_ret[max(0, i - 19):i + 1], ddof=1)) * _math.sqrt(252)
        for i in range(19, n)
    ]
    if len(vols) < 2:
        return float("nan")
    window = vols[-252:]
    current_vol = window[-1]
    lo, hi = min(window), max(window)
    if hi <= lo:
        return 50.0
    return round((current_vol - lo) / (hi - lo) * 100.0, 1)


from packages.data_adapters.base import DataAdapter
from packages.indicator_engine.indicators import (
    compute_sma,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_roc,
    compute_stochastic,
    compute_bollinger_bands,
    compute_bb_width,
    compute_atr,
    compute_adx,
    compute_obv,
    compute_vwap,
    crosses_above,
    crosses_below,
)


class ScanRule(BaseModel):
    id: str
    name: str
    description: str
    market: str          # "US" | "INDIA"
    asset_class: str     # "EQUITY" | "EQUITY_OPTIONS"
    timeframe: str       # "1day", "1hour", etc.
    min_candles: int     # how many candles required
    conditions: list[dict]  # list of condition specs
    signal_name: str
    template_id: str


def _compute_support_resistance(candles: list[dict], current_price: float) -> dict:
    """
    Detect swing-high/low levels as support and resistance.

    1. Mark bar i as swing high if its high >= all highs within ±window bars.
    2. Cluster nearby levels (within 1%) by averaging.
    3. Return up to 3 nearest support (below price) and 3 resistance (above price).
    """
    n = min(len(candles), 150)
    subset = candles[-n:]
    highs = [c["high"] for c in subset]
    lows  = [c["low"]  for c in subset]

    window = 3
    swing_highs: list[float] = []
    swing_lows:  list[float] = []

    for i in range(window, len(highs) - window):
        h = highs[i]
        l = lows[i]
        if h >= max(highs[i - window: i]) and h >= max(highs[i + 1: i + window + 1]):
            swing_highs.append(h)
        if l <= min(lows[i - window: i]) and l <= min(lows[i + 1: i + window + 1]):
            swing_lows.append(l)

    def cluster(levels: list[float], tol: float = 0.01) -> list[float]:
        if not levels:
            return []
        levels = sorted(levels)
        groups: list[list[float]] = [[levels[0]]]
        for lv in levels[1:]:
            if groups[-1][-1] > 0 and (lv / groups[-1][-1] - 1) < tol:
                groups[-1].append(lv)
            else:
                groups.append([lv])
        return [round(sum(g) / len(g), 2) for g in groups]

    support    = sorted([s for s in cluster(swing_lows)  if s < current_price],
                        key=lambda x: current_price - x)[:3]
    resistance = sorted([r for r in cluster(swing_highs) if r > current_price],
                        key=lambda x: x - current_price)[:3]
    return {"support": support, "resistance": resistance}


def _compute_exit_targets(
    entry_price: float,
    support_levels: list[float],
    resistance_levels: list[float],
    atr: float,
) -> dict:
    """
    Compute recommended stop-loss, target price, and risk/reward ratio.

    Stop-loss logic (picks the tighter / safer):
    - ATR-based:  entry - 2 × ATR
    - S/R-based:  nearest support level below entry (if within 3 × ATR)
    Uses the higher of the two (less downside risk).

    Target logic (picks the more conservative):
    - R/R-based:  entry + 3 × (entry - stop)  →  3:1 target
    - S/R-based:  nearest resistance above entry
    Uses the lower of the two (more achievable).
    """
    if entry_price <= 0 or atr <= 0 or np.isnan(entry_price) or np.isnan(atr):
        return {"stopLoss": None, "targetPrice": None, "riskReward": None}

    # Stop loss
    atr_stop = entry_price - 2.0 * atr
    if support_levels:
        # Nearest support that is above atr_stop (tighter)
        valid_supports = [s for s in support_levels if atr_stop <= s < entry_price]
        sr_stop = max(valid_supports) if valid_supports else atr_stop
    else:
        sr_stop = atr_stop
    stop_loss = round(max(atr_stop, sr_stop), 4)

    # Target price
    risk = entry_price - stop_loss
    rr_target = entry_price + 3.0 * risk        # 3:1 reward/risk
    if resistance_levels:
        sr_target = min(r for r in resistance_levels if r > entry_price) \
                    if any(r > entry_price for r in resistance_levels) else rr_target
    else:
        sr_target = rr_target
    target_price = round(min(rr_target, sr_target), 4)

    reward = target_price - entry_price
    risk_reward = round(reward / risk, 2) if risk > 0 else None

    return {
        "stopLoss": stop_loss,
        "targetPrice": target_price,
        "riskReward": risk_reward,
    }


def _safe_last(arr: np.ndarray) -> float:
    """Return the last non-NaN value from an array, or NaN if all NaN."""
    if arr is None or len(arr) == 0:
        return float("nan")
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return float("nan")
    return float(valid[-1])


def _compute_indicators(candles: list[dict]) -> dict:
    """
    Compute all indicator arrays from OHLCV candles.
    Returns a dict with both full arrays (for crossover detection) and scalar last values.
    """
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
        # Full arrays for crossover detection
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


def _get_indicator_value(indicators: dict, key: str) -> float:
    """Look up a scalar indicator value by name."""
    return indicators.get(key, float("nan"))


def _get_indicator_array(indicators: dict, key: str) -> Optional[np.ndarray]:
    """Look up a full indicator array by name (prefixed with underscore)."""
    return indicators.get(f"_{key}")


def _evaluate_condition(condition: dict, indicators: dict) -> bool:
    """
    Evaluate a single condition spec against computed indicators.

    Supported types:
    - crosses_above: indicator crosses above reference
    - crosses_below: indicator crosses below reference
    - greater_than: indicator > value
    - less_than: indicator < value
    - between: min <= indicator <= max
    - volume_surge: volume > threshold * average_volume (last 20 bars)
    """
    cond_type = condition.get("type", "")

    if cond_type == "crosses_above":
        ind_key = condition.get("indicator", "")
        ref_key = condition.get("reference", "")
        ind_arr = _get_indicator_array(indicators, ind_key)
        ref_arr = _get_indicator_array(indicators, ref_key)
        if ind_arr is None or ref_arr is None:
            return False
        crosses = crosses_above(ind_arr, ref_arr)
        # Check if the last bar is a crossover
        return bool(crosses[-1]) if len(crosses) > 0 else False

    elif cond_type == "crosses_below":
        ind_key = condition.get("indicator", "")
        ref_key = condition.get("reference", "")
        ind_arr = _get_indicator_array(indicators, ind_key)
        ref_arr = _get_indicator_array(indicators, ref_key)
        if ind_arr is None or ref_arr is None:
            return False
        crosses = crosses_below(ind_arr, ref_arr)
        return bool(crosses[-1]) if len(crosses) > 0 else False

    elif cond_type == "greater_than":
        ind_key = condition.get("indicator", "")
        threshold = condition.get("value", 0)
        # Support "reference" as another indicator name
        if "reference" in condition:
            ref_val = _get_indicator_value(indicators, condition["reference"])
            ind_val = _get_indicator_value(indicators, ind_key)
            if np.isnan(ind_val) or np.isnan(ref_val):
                return False
            return ind_val > ref_val
        ind_val = _get_indicator_value(indicators, ind_key)
        if np.isnan(ind_val):
            return False
        return ind_val > threshold

    elif cond_type == "less_than":
        ind_key = condition.get("indicator", "")
        threshold = condition.get("value", 0)
        if "reference" in condition:
            ref_val = _get_indicator_value(indicators, condition["reference"])
            ind_val = _get_indicator_value(indicators, ind_key)
            if np.isnan(ind_val) or np.isnan(ref_val):
                return False
            return ind_val < ref_val
        ind_val = _get_indicator_value(indicators, ind_key)
        if np.isnan(ind_val):
            return False
        return ind_val < threshold

    elif cond_type == "between":
        ind_key = condition.get("indicator", "")
        min_val = condition.get("min", float("-inf"))
        max_val = condition.get("max", float("inf"))
        ind_val = _get_indicator_value(indicators, ind_key)
        if np.isnan(ind_val):
            return False
        return min_val <= ind_val <= max_val

    elif cond_type == "volume_surge":
        threshold = condition.get("threshold", 1.5)
        vol_arr = _get_indicator_array(indicators, "volume")
        if vol_arr is None or len(vol_arr) < 21:
            return False
        avg_vol = float(np.mean(vol_arr[-21:-1]))  # last 20 bars avg (excluding current)
        current_vol = float(vol_arr[-1])
        if avg_vol == 0:
            return False
        return current_vol > threshold * avg_vol

    return False


class ScanEngine:
    """
    Core scan engine that evaluates ScanRule conditions against market data.

    Usage:
        engine = ScanEngine(data_adapter)
        results = await engine.run(rule, ["AAPL", "MSFT", ...])
    """

    def __init__(self, data_adapter: DataAdapter, storage=None):
        self._adapter = data_adapter
        self._storage = storage

    async def run(self, rule: ScanRule, symbols: list[str]) -> list[dict]:
        """Run rule against all symbols concurrently using asyncio.gather."""
        tasks = [self._evaluate(rule, symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Filter out exceptions and None results
        return [r for r in results if isinstance(r, dict)]

    async def _evaluate(self, rule: ScanRule, symbol: str) -> Optional[dict]:
        """
        Fetch candles, compute indicators, evaluate conditions, return ScanResult dict or None.

        Returns None if:
        - Not enough candles are available
        - Any unrecoverable exception occurs
        - All conditions fail to be met (strengthScore is computed regardless)
        """
        try:
            today = date.today()
            from_date = (today - timedelta(days=400)).isoformat()
            to_date = today.isoformat()

            candles = await self._adapter.get_candles(
                symbol, rule.timeframe, from_date, to_date
            )

            if not candles or len(candles) < rule.min_candles:
                return None

            # Compute all indicators
            indicators = _compute_indicators(candles)

            # Evaluate each condition
            conditions_met = 0
            total_conditions = len(rule.conditions)

            for condition in rule.conditions:
                if _evaluate_condition(condition, indicators):
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
                and not np.isnan(v)
            }

            # Entry price = current close (where you'd enter on this signal)
            entry_price = float(indicators.get("close", float("nan")))

            # Support / resistance from recent swing highs and lows
            sr = _compute_support_resistance(candles, entry_price)

            # Exit targets — stop loss, take-profit, risk:reward
            atr_val = indicator_values.get("atr", float("nan"))
            exit_targets = _compute_exit_targets(
                entry_price, sr["support"], sr["resistance"], atr_val
            )

            # Direction inference
            direction = _infer_direction(rule.signal_name)

            # For options: ATM strike, premium, Greeks, IV rank, PoP, spread, EV
            option_premium: Optional[float] = None
            profit_probability: Optional[float] = None
            strike_price: Optional[float] = None
            spread_debit: Optional[float] = None
            spread_max_profit: Optional[float] = None
            spread_width: Optional[float] = None
            suggested_spread: Optional[str] = None
            delta: Optional[float] = None
            gamma: Optional[float] = None
            theta: Optional[float] = None
            vega: Optional[float] = None
            iv_rank: Optional[float] = None
            iv_recommendation: Optional[str] = None
            expected_value: Optional[float] = None
            if rule.asset_class == 'EQUITY_OPTIONS' and not np.isnan(entry_price) and entry_price > 0:
                close_arr = indicators.get('_close', np.array([]))
                if len(close_arr) >= 21:
                    log_ret = np.log(close_arr[1:] / close_arr[:-1])
                    sigma = float(np.std(log_ret[-20:], ddof=1)) * _math.sqrt(252)
                else:
                    sigma = 0.20
                sigma = max(sigma, 0.05)
                T = 30.0 / 365.0
                r = 0.05
                S = entry_price
                call_prem = _bs_call_price(S, S, T, r, sigma)
                put_prem = call_prem + S * (_math.exp(-r * T) - 1)
                put_prem = max(put_prem, 0.0)
                if T > 0 and sigma > 0:
                    d1 = (_math.log(1.0) + (r + 0.5 * sigma ** 2) * T) / (sigma * _math.sqrt(T))
                    d2 = d1 - sigma * _math.sqrt(T)
                else:
                    d2 = 0.0
                strike_price = _atm_strike(S)

                # IV rank
                iv_rank = _iv_rank_from_prices(close_arr) if len(close_arr) >= 22 else float("nan")
                if not _math.isnan(iv_rank):
                    if iv_rank >= 70:
                        iv_recommendation = 'SELL_PREMIUM'
                    elif iv_rank <= 30:
                        iv_recommendation = 'BUY_PREMIUM'
                    else:
                        iv_recommendation = 'NEUTRAL'
                else:
                    iv_rank = None
                    iv_recommendation = None

                otm_offset = 0.05
                if direction == 'SELL':
                    option_premium = round(put_prem, 4)
                    profit_probability = round(_norm_cdf(-d2) * 100, 1)
                    K_otm = S * (1.0 - otm_offset)
                    otm_put = max(_bs_call_price(S, K_otm, T, r, sigma) + S * (_math.exp(-r * T) - 1), 0.0)
                    spread_debit = round(max(put_prem - otm_put, 0.0), 4)
                    spread_width = round(S * otm_offset, 4)
                    spread_max_profit = round(max(spread_width - spread_debit, 0.0), 4)
                    suggested_spread = 'LONG_PUT_SPREAD'
                    greeks = _bs_greeks(S, S, T, r, sigma, "put")
                    pop_spread = max(0.0, min(1.0, 1.0 - spread_debit / spread_width)) if spread_width > 0 else 0.5
                    expected_value = round(pop_spread * spread_max_profit - (1.0 - pop_spread) * spread_debit, 4)
                elif direction == 'NEUTRAL':
                    option_premium = round(call_prem + put_prem, 4)
                    profit_probability = round((2.0 * _norm_cdf(1.0) - 1.0) * 100, 1)
                    suggested_spread = None
                    greeks = _bs_greeks(S, S, T, r, sigma, "call")
                    # Straddle EV: PoP of big move
                    z = (option_premium / S) / (sigma * _math.sqrt(T)) if sigma * _math.sqrt(T) > 0 else 1.0
                    pop_straddle = max(0.0, 2.0 * (1.0 - _norm_cdf(z)))
                    expected_value = round(pop_straddle * option_premium * 0.5 - (1.0 - pop_straddle) * option_premium, 4)
                else:  # BUY
                    option_premium = round(call_prem, 4)
                    profit_probability = round(_norm_cdf(d2) * 100, 1)
                    K_otm = S * (1.0 + otm_offset)
                    otm_call = _bs_call_price(S, K_otm, T, r, sigma)
                    spread_debit = round(max(call_prem - otm_call, 0.0), 4)
                    spread_width = round(S * otm_offset, 4)
                    spread_max_profit = round(max(spread_width - spread_debit, 0.0), 4)
                    suggested_spread = 'LONG_CALL_SPREAD'
                    greeks = _bs_greeks(S, S, T, r, sigma, "call")
                    pop_spread = max(0.0, min(1.0, 1.0 - spread_debit / spread_width)) if spread_width > 0 else 0.5
                    expected_value = round(pop_spread * spread_max_profit - (1.0 - pop_spread) * spread_debit, 4)

                delta = greeks["delta"]
                gamma = greeks["gamma"]
                theta = greeks["theta"]
                vega  = greeks["vega"]

            # Last 60 bars for the mini chart (timestamp + close only)
            chart_candles = [
                {"t": c["timestamp"], "c": round(c["close"], 4)}
                for c in candles[-60:]
            ]

            result = {
                "id": str(uuid4()),
                "symbol": symbol,
                "market": rule.market,
                "assetClass": rule.asset_class,
                "signalName": rule.signal_name,
                "templateId": rule.template_id,
                "timeframe": rule.timeframe,
                "strengthScore": float(strength_score),
                "timestamp": int(time.time() * 1000),
                "indicatorValues": indicator_values,
                "direction": direction,
                "entryPrice": round(entry_price, 4) if not np.isnan(entry_price) else None,
                "strikePrice": strike_price,
                "optionPremium": option_premium,
                "profitProbability": profit_probability,
                "suggestedSpread": suggested_spread,
                "spreadDebit": spread_debit,
                "spreadWidth": spread_width,
                "spreadMaxProfit": spread_max_profit,
                "delta": delta,
                "gamma": gamma,
                "theta": theta,
                "vega": vega,
                "ivRank": iv_rank,
                "ivRecommendation": iv_recommendation,
                "expectedValue": expected_value,
                "stopLoss": exit_targets["stopLoss"],
                "targetPrice": exit_targets["targetPrice"],
                "riskReward": exit_targets["riskReward"],
                "supportLevels": sr["support"],
                "resistanceLevels": sr["resistance"],
                "recentCandles": chart_candles,
            }

            # Optionally persist result
            if self._storage is not None:
                try:
                    await self._storage.save_scan_result(result)
                except Exception:
                    pass  # Storage failure should not break scan result delivery

            return result

        except Exception:
            return None

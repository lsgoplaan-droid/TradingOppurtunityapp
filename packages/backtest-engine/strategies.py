"""Pre-built trading strategies — each returns (entry_signals, exit_signals) bool arrays."""
import numpy as np
from packages.indicator_engine.indicators import (
    compute_ema, compute_rsi, compute_macd, compute_atr,
    compute_adx, compute_bollinger_bands, crosses_above, crosses_below
)


def strategy_golden_cross(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """EMA50 crosses above EMA200 -> entry. EMA50 crosses below EMA200 -> exit."""
    ema50 = compute_ema(closes, 50)
    ema200 = compute_ema(closes, 200)
    entry = crosses_above(ema50, ema200)
    exit_ = crosses_below(ema50, ema200)
    return entry, exit_


def strategy_rsi_mean_reversion(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """RSI drops below 30 (entry when it crosses back above 30), rises above 70 (exit)."""
    rsi = compute_rsi(closes, 14)
    entry = crosses_above(rsi, np.full_like(rsi, 30.0))
    exit_ = crosses_above(rsi, np.full_like(rsi, 70.0))
    return entry, exit_


def strategy_macd_trend(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """MACD line crosses above signal -> entry. Crosses below -> exit."""
    macd_line, signal_line, _ = compute_macd(closes, 12, 26, 9)
    entry = crosses_above(macd_line, signal_line)
    exit_ = crosses_below(macd_line, signal_line)
    return entry, exit_


def strategy_bollinger_reversion(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Close touches lower band (entry), touches upper band (exit)."""
    upper, middle, lower = compute_bollinger_bands(closes, 20, 2.0)
    entry = closes < lower
    exit_ = closes > upper
    return entry, exit_


STRATEGY_REGISTRY: dict[str, callable] = {
    "golden_cross": strategy_golden_cross,
    "rsi_mean_reversion": strategy_rsi_mean_reversion,
    "macd_trend": strategy_macd_trend,
    "bollinger_reversion": strategy_bollinger_reversion,
}

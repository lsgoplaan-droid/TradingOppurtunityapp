"""Tests for pre-built strategies."""
import numpy as np
import pytest
from packages.backtest_engine.strategies import (
    strategy_golden_cross,
    strategy_rsi_mean_reversion,
    strategy_macd_trend,
    strategy_bollinger_reversion,
    STRATEGY_REGISTRY,
)


def _synthetic_ohlcv(n=300, seed=42):
    rng = np.random.default_rng(seed)
    closes = 100 + np.cumsum(rng.standard_normal(n) * 0.5)
    closes = np.clip(closes, 1, None)
    highs  = closes + rng.uniform(0, 1, n)
    lows   = closes - rng.uniform(0, 1, n)
    return closes, highs, lows


def test_golden_cross_returns_bool_arrays():
    closes, highs, lows = _synthetic_ohlcv()
    entry, exit_ = strategy_golden_cross(closes, highs, lows)
    assert entry.dtype == bool
    assert exit_.dtype == bool
    assert len(entry) == len(closes)


def test_golden_cross_signals_sparse():
    """Crossover signals should fire rarely, not every bar."""
    closes, highs, lows = _synthetic_ohlcv(n=500)
    entry, exit_ = strategy_golden_cross(closes, highs, lows)
    assert entry.sum() < 20


def test_rsi_mean_reversion_returns_bool_arrays():
    closes, highs, lows = _synthetic_ohlcv()
    entry, exit_ = strategy_rsi_mean_reversion(closes, highs, lows)
    assert entry.dtype == bool
    assert len(entry) == len(closes)


def test_macd_trend_returns_bool_arrays():
    closes, highs, lows = _synthetic_ohlcv()
    entry, exit_ = strategy_macd_trend(closes, highs, lows)
    assert entry.dtype == bool
    assert len(entry) == len(closes)


def test_bollinger_reversion_returns_bool_arrays():
    closes, highs, lows = _synthetic_ohlcv()
    entry, exit_ = strategy_bollinger_reversion(closes, highs, lows)
    assert entry.dtype == bool
    assert len(entry) == len(closes)


def test_strategy_registry_has_all_strategies():
    expected = {"golden_cross", "rsi_mean_reversion", "macd_trend", "bollinger_reversion"}
    assert expected.issubset(STRATEGY_REGISTRY.keys())


def test_all_strategies_callable():
    closes, highs, lows = _synthetic_ohlcv()
    for name, fn in STRATEGY_REGISTRY.items():
        entry, exit_ = fn(closes, highs, lows)
        assert entry.dtype == bool, f"{name} entry not bool"
        assert exit_.dtype == bool, f"{name} exit not bool"

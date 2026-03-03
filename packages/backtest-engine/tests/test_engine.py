"""Tests for the backtest engine."""
import numpy as np
import pytest
from packages.backtest_engine.engine import BacktestConfig, run_backtest


def _make_config(**kwargs) -> BacktestConfig:
    defaults = dict(
        symbol="TEST",
        strategy_name="test_strat",
        start_date="2022-01-01",
        end_date="2023-01-01",
        initial_capital=100_000.0,
        position_sizing="pct_equity",
        commission_pct=0.001,
    )
    defaults.update(kwargs)
    return BacktestConfig(**defaults)


def _synthetic_data(n=300, seed=42):
    rng = np.random.default_rng(seed)
    prices = 100 + np.cumsum(rng.standard_normal(n) * 0.5)
    prices = np.clip(prices, 1, None)
    timestamps = np.array([1640000000000 + i * 86400000 for i in range(n)], dtype=np.float64)
    highs = prices + rng.uniform(0, 1, n)
    lows  = prices - rng.uniform(0, 1, n)
    return timestamps, prices, highs, lows


def test_run_backtest_returns_correct_keys():
    ts, closes, highs, lows = _synthetic_data()
    entry = np.zeros(len(closes), dtype=bool); entry[50] = True
    exit_ = np.zeros(len(closes), dtype=bool); exit_[100] = True
    result = run_backtest(_make_config(), ts, closes, highs, lows, entry, exit_)
    required = {"id", "symbol", "strategyName", "startDate", "endDate", "totalReturn",
                "cagr", "sharpe", "sortino", "maxDrawdown", "winRate", "profitFactor",
                "avgTradeDuration", "equityCurve", "drawdownCurve", "trades"}
    assert required.issubset(result.keys())


def test_run_backtest_no_trades():
    """No entry signals -> no trades, equity unchanged."""
    ts, closes, highs, lows = _synthetic_data()
    entry = np.zeros(len(closes), dtype=bool)
    exit_ = np.zeros(len(closes), dtype=bool)
    result = run_backtest(_make_config(), ts, closes, highs, lows, entry, exit_)
    assert result["trades"] == []
    assert result["totalReturn"] == 0.0


def test_run_backtest_single_winning_trade():
    """Buy at price 100, sell at price 110 -> positive return."""
    n = 300
    prices = np.full(n, 100.0)
    prices[101:] = 110.0
    ts = np.array([1640000000000 + i * 86400000 for i in range(n)], dtype=np.float64)
    highs = prices + 0.5
    lows  = prices - 0.5
    entry = np.zeros(n, dtype=bool); entry[50] = True
    exit_ = np.zeros(n, dtype=bool); exit_[110] = True  # exit after price rises to 110
    result = run_backtest(_make_config(), ts, prices, highs, lows, entry, exit_)
    assert len(result["trades"]) == 1
    assert result["trades"][0]["pnl"] > 0
    assert result["totalReturn"] > 0


def test_run_backtest_single_losing_trade():
    """Buy at 100, sell at 90 -> negative PnL."""
    n = 300
    prices = np.full(n, 100.0)
    prices[101:] = 90.0
    ts = np.array([1640000000000 + i * 86400000 for i in range(n)], dtype=np.float64)
    highs = prices + 0.5
    lows  = prices - 0.5
    entry = np.zeros(n, dtype=bool); entry[50] = True
    exit_ = np.zeros(n, dtype=bool); exit_[100] = True
    result = run_backtest(_make_config(), ts, prices, highs, lows, entry, exit_)
    assert result["trades"][0]["pnl"] < 0
    assert result["totalReturn"] < 0


def test_equity_curve_length_matches_input():
    ts, closes, highs, lows = _synthetic_data()
    entry = np.zeros(len(closes), dtype=bool)
    exit_ = np.zeros(len(closes), dtype=bool)
    result = run_backtest(_make_config(), ts, closes, highs, lows, entry, exit_)
    assert len(result["equityCurve"]) == len(closes)


def test_equity_curve_has_timestamp_and_value():
    ts, closes, highs, lows = _synthetic_data()
    entry = np.zeros(len(closes), dtype=bool)
    exit_ = np.zeros(len(closes), dtype=bool)
    result = run_backtest(_make_config(), ts, closes, highs, lows, entry, exit_)
    assert "timestamp" in result["equityCurve"][0]
    assert "value" in result["equityCurve"][0]


def test_drawdown_curve_length_matches_input():
    ts, closes, highs, lows = _synthetic_data()
    entry = np.zeros(len(closes), dtype=bool)
    exit_ = np.zeros(len(closes), dtype=bool)
    result = run_backtest(_make_config(), ts, closes, highs, lows, entry, exit_)
    assert len(result["drawdownCurve"]) == len(closes)


def test_max_drawdown_is_negative_or_zero():
    ts, closes, highs, lows = _synthetic_data()
    entry = np.zeros(len(closes), dtype=bool); entry[50] = True
    exit_ = np.zeros(len(closes), dtype=bool); exit_[100] = True
    result = run_backtest(_make_config(), ts, closes, highs, lows, entry, exit_)
    assert result["maxDrawdown"] <= 0


def test_win_rate_between_0_and_1():
    ts, closes, highs, lows = _synthetic_data()
    entry = np.zeros(len(closes), dtype=bool); entry[50] = True; entry[150] = True
    exit_ = np.zeros(len(closes), dtype=bool); exit_[100] = True; exit_[200] = True
    result = run_backtest(_make_config(), ts, closes, highs, lows, entry, exit_)
    assert 0.0 <= result["winRate"] <= 1.0


def test_profit_factor_non_negative():
    ts, closes, highs, lows = _synthetic_data()
    entry = np.zeros(len(closes), dtype=bool); entry[50] = True
    exit_ = np.zeros(len(closes), dtype=bool); exit_[100] = True
    result = run_backtest(_make_config(), ts, closes, highs, lows, entry, exit_)
    assert result["profitFactor"] >= 0


def test_fixed_position_sizing():
    ts, closes, highs, lows = _synthetic_data()
    entry = np.zeros(len(closes), dtype=bool); entry[50] = True
    exit_ = np.zeros(len(closes), dtype=bool); exit_[100] = True
    cfg = _make_config(position_sizing="fixed", fixed_position_size=5_000)
    result = run_backtest(cfg, ts, closes, highs, lows, entry, exit_)
    assert len(result["trades"]) == 1


def test_kelly_position_sizing():
    ts, closes, highs, lows = _synthetic_data()
    entry = np.zeros(len(closes), dtype=bool); entry[50] = True
    exit_ = np.zeros(len(closes), dtype=bool); exit_[100] = True
    cfg = _make_config(position_sizing="kelly")
    result = run_backtest(cfg, ts, closes, highs, lows, entry, exit_)
    assert result is not None


def test_commission_reduces_profit():
    """Higher commission -> lower total return."""
    n = 300
    prices = np.full(n, 100.0); prices[101:] = 110.0
    ts = np.array([1640000000000 + i * 86400000 for i in range(n)], dtype=np.float64)
    highs = prices + 0.5; lows = prices - 0.5
    entry = np.zeros(n, dtype=bool); entry[50] = True
    exit_ = np.zeros(n, dtype=bool); exit_[100] = True
    result_low  = run_backtest(_make_config(commission_pct=0.0001), ts, prices, highs, lows, entry, exit_)
    result_high = run_backtest(_make_config(commission_pct=0.01),   ts, prices, highs, lows, entry, exit_)
    assert result_low["totalReturn"] > result_high["totalReturn"]


def test_multiple_trades_accumulate():
    ts, closes, highs, lows = _synthetic_data()
    entry = np.zeros(len(closes), dtype=bool)
    exit_ = np.zeros(len(closes), dtype=bool)
    for i in range(0, 200, 40):
        entry[i] = True; exit_[i + 20] = True
    result = run_backtest(_make_config(), ts, closes, highs, lows, entry, exit_)
    assert len(result["trades"]) >= 2

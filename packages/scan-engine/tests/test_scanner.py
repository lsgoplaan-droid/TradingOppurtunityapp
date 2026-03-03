"""Tests for the core scan engine."""
import asyncio
import pytest
import numpy as np

from packages.data_adapters.base import DataAdapter
from packages.scan_engine.scanner import ScanEngine, ScanRule, _evaluate_condition, _compute_indicators
from packages.scan_engine.template_loader import list_templates, load_template


# ─── Mock Data Adapter ────────────────────────────────────────────────────────

class MockDataAdapter(DataAdapter):
    """Minimal mock adapter returning synthetic OHLCV data for testing."""

    def __init__(self, candles=None):
        self._candles = candles or self._default_candles()

    def _default_candles(self):
        """Generate 250 synthetic candles (enough for all indicators)."""
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(250) * 0.5)
        return [
            {
                "timestamp": 1700000000000 + i * 86400000,
                "open": float(prices[i] - 0.1),
                "high": float(prices[i] + 0.5),
                "low": float(prices[i] - 0.5),
                "close": float(prices[i]),
                "volume": float(1_000_000 + i * 1000),
            }
            for i in range(250)
        ]

    async def get_candles(self, symbol, timeframe, from_date, to_date):
        return self._candles

    async def get_quote(self, symbol):
        return {
            "symbol": symbol,
            "price": 100.0,
            "change": 0.5,
            "change_pct": 0.5,
            "timestamp": 1700000000000,
        }

    async def get_option_chain(self, symbol, expiry=None):
        return {}

    async def search_symbols(self, query):
        return []


# ─── Minimal ScanRule fixture ─────────────────────────────────────────────────

def make_rule(conditions=None, min_candles=50):
    """Create a minimal ScanRule for testing."""
    return ScanRule(
        id="test_rule",
        name="Test Rule",
        description="Rule for unit tests",
        market="US",
        asset_class="EQUITY",
        timeframe="1day",
        min_candles=min_candles,
        conditions=conditions or [{"type": "greater_than", "indicator": "rsi", "value": 0}],
        signal_name="Test Signal",
        template_id="test_rule",
    )


# ─── ScanEngine.run() tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_returns_list_of_dicts():
    """ScanEngine.run() should return a list of dicts."""
    adapter = MockDataAdapter()
    engine = ScanEngine(adapter)
    rule = make_rule()
    results = await engine.run(rule, ["AAPL", "MSFT"])
    assert isinstance(results, list)
    # All items should be dicts (exceptions are filtered out)
    for r in results:
        assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_run_with_multiple_symbols():
    """ScanEngine.run() processes all symbols concurrently."""
    adapter = MockDataAdapter()
    engine = ScanEngine(adapter)
    rule = make_rule()
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
    results = await engine.run(rule, symbols)
    assert isinstance(results, list)
    # All results should come from the symbol list
    result_symbols = {r["symbol"] for r in results}
    assert result_symbols.issubset(set(symbols))


@pytest.mark.asyncio
async def test_run_filters_exceptions():
    """ScanEngine.run() silently drops symbols that raise exceptions."""

    class FailingAdapter(DataAdapter):
        async def get_candles(self, symbol, timeframe, from_date, to_date):
            raise RuntimeError("Simulated failure")

        async def get_quote(self, symbol):
            return {}

        async def get_option_chain(self, symbol, expiry=None):
            return {}

        async def search_symbols(self, query):
            return []

    engine = ScanEngine(FailingAdapter())
    rule = make_rule()
    results = await engine.run(rule, ["AAPL", "MSFT"])
    # All should be filtered out since all raise exceptions
    assert results == []


# ─── _evaluate() tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_evaluate_returns_none_when_not_enough_candles():
    """_evaluate() returns None when fewer candles than min_candles."""
    np.random.seed(0)
    prices = 100 + np.cumsum(np.random.randn(10) * 0.5)
    few_candles = [
        {
            "timestamp": 1700000000000 + i * 86400000,
            "open": float(prices[i] - 0.1),
            "high": float(prices[i] + 0.5),
            "low": float(prices[i] - 0.5),
            "close": float(prices[i]),
            "volume": float(1_000_000),
        }
        for i in range(10)
    ]
    adapter = MockDataAdapter(candles=few_candles)
    engine = ScanEngine(adapter)
    rule = make_rule(min_candles=50)  # requires 50 but only 10 available
    result = await engine._evaluate(rule, "AAPL")
    assert result is None


@pytest.mark.asyncio
async def test_evaluate_returns_dict_when_conditions_met():
    """_evaluate() returns a ScanResult dict with correct keys when conditions are met."""
    adapter = MockDataAdapter()
    engine = ScanEngine(adapter)
    # Use a condition that will trivially pass (RSI > 0)
    rule = make_rule(conditions=[{"type": "greater_than", "indicator": "rsi", "value": 0}])
    result = await engine._evaluate(rule, "AAPL")
    assert result is not None
    assert isinstance(result, dict)

    # Verify all required ScanResult keys are present
    required_keys = {
        "id", "symbol", "market", "assetClass", "signalName",
        "templateId", "timeframe", "strengthScore", "timestamp", "indicatorValues",
    }
    assert required_keys.issubset(result.keys())


@pytest.mark.asyncio
async def test_evaluate_correct_field_values():
    """_evaluate() returns correct field values matching the rule."""
    adapter = MockDataAdapter()
    engine = ScanEngine(adapter)
    rule = make_rule(conditions=[{"type": "greater_than", "indicator": "rsi", "value": 0}])
    result = await engine._evaluate(rule, "TSLA")
    assert result["symbol"] == "TSLA"
    assert result["market"] == "US"
    assert result["assetClass"] == "EQUITY"
    assert result["signalName"] == "Test Signal"
    assert result["templateId"] == "test_rule"
    assert result["timeframe"] == "1day"
    assert isinstance(result["strengthScore"], float)
    assert isinstance(result["timestamp"], int)
    assert isinstance(result["indicatorValues"], dict)


@pytest.mark.asyncio
async def test_evaluate_returns_dict_even_when_conditions_fail():
    """
    _evaluate() still returns a ScanResult dict even when conditions fail.
    The strengthScore will be 0.0 but the result is not filtered.
    """
    adapter = MockDataAdapter()
    engine = ScanEngine(adapter)
    # Use a condition that will always fail (RSI > 200 — impossible)
    rule = make_rule(conditions=[{"type": "greater_than", "indicator": "rsi", "value": 200}])
    result = await engine._evaluate(rule, "AAPL")
    assert result is not None
    assert result["strengthScore"] == 0.0


# ─── Strength score tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_strength_score_all_pass():
    """Strength score = 100 when all conditions pass."""
    adapter = MockDataAdapter()
    engine = ScanEngine(adapter)
    rule = make_rule(conditions=[
        {"type": "greater_than", "indicator": "rsi", "value": 0},
        {"type": "greater_than", "indicator": "close", "value": 0},
    ])
    result = await engine._evaluate(rule, "AAPL")
    assert result is not None
    assert result["strengthScore"] == 100.0


@pytest.mark.asyncio
async def test_strength_score_partial():
    """Strength score = 50 when exactly half the conditions pass."""
    adapter = MockDataAdapter()
    engine = ScanEngine(adapter)
    rule = make_rule(conditions=[
        {"type": "greater_than", "indicator": "rsi", "value": 0},    # always passes
        {"type": "greater_than", "indicator": "rsi", "value": 200},  # always fails
    ])
    result = await engine._evaluate(rule, "AAPL")
    assert result is not None
    assert result["strengthScore"] == 50.0


@pytest.mark.asyncio
async def test_strength_score_none_pass():
    """Strength score = 0 when no conditions pass."""
    adapter = MockDataAdapter()
    engine = ScanEngine(adapter)
    rule = make_rule(conditions=[
        {"type": "greater_than", "indicator": "rsi", "value": 200},  # always fails
        {"type": "greater_than", "indicator": "adx", "value": 10000},  # always fails
    ])
    result = await engine._evaluate(rule, "AAPL")
    assert result is not None
    assert result["strengthScore"] == 0.0


# ─── Condition evaluation unit tests ─────────────────────────────────────────

def test_evaluate_condition_greater_than():
    """Test greater_than condition type."""
    candles = MockDataAdapter()._default_candles()
    indicators = _compute_indicators(candles)
    cond = {"type": "greater_than", "indicator": "close", "value": 0}
    assert _evaluate_condition(cond, indicators) is True

    cond_fail = {"type": "greater_than", "indicator": "close", "value": 1e9}
    assert _evaluate_condition(cond_fail, indicators) is False


def test_evaluate_condition_less_than():
    """Test less_than condition type."""
    candles = MockDataAdapter()._default_candles()
    indicators = _compute_indicators(candles)
    cond = {"type": "less_than", "indicator": "rsi", "value": 200}
    assert _evaluate_condition(cond, indicators) is True

    cond_fail = {"type": "less_than", "indicator": "rsi", "value": 0}
    assert _evaluate_condition(cond_fail, indicators) is False


def test_evaluate_condition_between():
    """Test between condition type."""
    candles = MockDataAdapter()._default_candles()
    indicators = _compute_indicators(candles)
    # RSI is always 0-100
    cond = {"type": "between", "indicator": "rsi", "min": 0, "max": 100}
    assert _evaluate_condition(cond, indicators) is True

    cond_fail = {"type": "between", "indicator": "rsi", "min": 200, "max": 300}
    assert _evaluate_condition(cond_fail, indicators) is False


def test_evaluate_condition_unknown_type():
    """Unknown condition type should return False, not raise."""
    candles = MockDataAdapter()._default_candles()
    indicators = _compute_indicators(candles)
    cond = {"type": "totally_unknown_condition", "indicator": "rsi", "value": 50}
    result = _evaluate_condition(cond, indicators)
    assert result is False


def test_evaluate_condition_crosses_above():
    """Test crosses_above condition type."""
    candles = MockDataAdapter()._default_candles()
    indicators = _compute_indicators(candles)
    cond = {"type": "crosses_above", "indicator": "ema20", "reference": "ema50"}
    # Just check it returns a bool without raising
    result = _evaluate_condition(cond, indicators)
    assert isinstance(result, bool)


def test_evaluate_condition_volume_surge():
    """Test volume_surge condition type."""
    candles = MockDataAdapter()._default_candles()
    indicators = _compute_indicators(candles)
    # With threshold 0 — should always pass
    cond = {"type": "volume_surge", "threshold": 0}
    assert _evaluate_condition(cond, indicators) is True

    # With very high threshold — should fail
    cond_fail = {"type": "volume_surge", "threshold": 1e9}
    assert _evaluate_condition(cond_fail, indicators) is False


# ─── Indicator values in result ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_indicator_values_present_in_result():
    """ScanResult should include key indicator values."""
    adapter = MockDataAdapter()
    engine = ScanEngine(adapter)
    rule = make_rule()
    result = await engine._evaluate(rule, "AAPL")
    assert result is not None
    ivs = result["indicatorValues"]
    # Check some fundamental indicators are present
    assert "close" in ivs
    assert "rsi" in ivs
    assert "adx" in ivs


@pytest.mark.asyncio
async def test_result_id_is_unique():
    """Each ScanResult should have a unique ID."""
    adapter = MockDataAdapter()
    engine = ScanEngine(adapter)
    rule = make_rule()
    results = await engine.run(rule, ["AAPL", "MSFT", "GOOGL"])
    ids = [r["id"] for r in results]
    assert len(ids) == len(set(ids)), "ScanResult IDs should be unique"

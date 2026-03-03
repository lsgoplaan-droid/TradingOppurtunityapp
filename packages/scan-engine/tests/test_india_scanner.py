"""Tests for the India-specific scan engine."""
import asyncio
import pytest
import numpy as np

from packages.data_adapters.base import DataAdapter
from packages.scan_engine.india_scanner import IndiaScanEngine
from packages.scan_engine.template_loader import list_templates


# ─── Mock India Data Adapter ─────────────────────────────────────────────────

class MockIndiaAdapter(DataAdapter):
    """Mock adapter returning synthetic NSE-level OHLCV and option chain data."""

    def __init__(self, with_option_chain=True):
        self._with_option_chain = with_option_chain
        self._call_count = {"get_option_chain": 0}

    async def get_candles(self, symbol, timeframe, from_date, to_date):
        np.random.seed(42)
        prices = 18000 + np.cumsum(np.random.randn(250) * 10)
        return [
            {
                "timestamp": 1700000000000 + i * 86400000,
                "open": float(prices[i] - 5),
                "high": float(prices[i] + 10),
                "low": float(prices[i] - 10),
                "close": float(prices[i]),
                "volume": float(100_000 + i * 500),
            }
            for i in range(250)
        ]

    async def get_quote(self, symbol):
        return {
            "symbol": symbol,
            "price": 18500.0,
            "change": 50.0,
            "change_pct": 0.27,
            "timestamp": 1700000000000,
        }

    async def get_option_chain(self, symbol, expiry=None):
        self._call_count["get_option_chain"] += 1
        if not self._with_option_chain:
            return {}
        return {
            "underlying": symbol,
            "spot": 18500.0,
            "expiry": "2024-01-25",
            "calls": [
                {
                    "strike": 18400, "optionType": "CE", "ltp": 200, "iv": 0.18,
                    "oi": 50000, "volume": 5000, "delta": 0.6, "gamma": 0.001,
                    "theta": -10, "vega": 5, "rho": 0.1,
                },
                {
                    "strike": 18500, "optionType": "CE", "ltp": 150, "iv": 0.17,
                    "oi": 80000, "volume": 8000, "delta": 0.5, "gamma": 0.0015,
                    "theta": -12, "vega": 6, "rho": 0.09,
                },
                {
                    "strike": 18600, "optionType": "CE", "ltp": 100, "iv": 0.16,
                    "oi": 40000, "volume": 4000, "delta": 0.4, "gamma": 0.001,
                    "theta": -8, "vega": 4, "rho": 0.08,
                },
            ],
            "puts": [
                {
                    "strike": 18400, "optionType": "PE", "ltp": 100, "iv": 0.18,
                    "oi": 60000, "volume": 6000, "delta": -0.4, "gamma": 0.001,
                    "theta": -8, "vega": 4, "rho": -0.08,
                },
                {
                    "strike": 18500, "optionType": "PE", "ltp": 150, "iv": 0.17,
                    "oi": 90000, "volume": 9000, "delta": -0.5, "gamma": 0.0015,
                    "theta": -12, "vega": 6, "rho": -0.09,
                },
                {
                    "strike": 18600, "optionType": "PE", "ltp": 200, "iv": 0.16,
                    "oi": 45000, "volume": 4500, "delta": -0.6, "gamma": 0.001,
                    "theta": -10, "vega": 5, "rho": -0.1,
                },
            ],
        }

    async def search_symbols(self, query):
        return []


# ─── Minimal rule helpers ─────────────────────────────────────────────────────

def make_equity_rule(conditions=None, min_candles=50):
    """Create a minimal equity rule dict for India."""
    return {
        "id": "test_india_eq",
        "name": "Test India Equity",
        "description": "Test rule for India equity",
        "market": "INDIA",
        "assetClass": "EQUITY",
        "timeframe": "1day",
        "minCandles": min_candles,
        "conditions": conditions or [{"type": "greater_than", "indicator": "rsi", "value": 0}],
        "signalName": "Test Signal",
        "templateId": "test_india_eq",
    }


def make_fo_rule(conditions=None, min_candles=50):
    """Create a minimal F&O rule dict for India."""
    return {
        "id": "test_india_fo",
        "name": "Test India F&O",
        "description": "Test rule for India F&O",
        "market": "INDIA",
        "assetClass": "EQUITY_OPTIONS",
        "timeframe": "1day",
        "minCandles": min_candles,
        "conditions": conditions or [{"type": "greater_than", "indicator": "iv_rank", "value": 0}],
        "signalName": "Test F&O Signal",
        "templateId": "test_india_fo",
    }


# ─── IndiaScanEngine.run() tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_equity_returns_list_of_dicts():
    """IndiaScanEngine.run() with equity template returns list of dicts."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_equity_rule()
    results = await engine.run(rule, ["NIFTY", "RELIANCE"])
    assert isinstance(results, list)
    for r in results:
        assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_run_equity_returns_correct_symbols():
    """IndiaScanEngine.run() results include the scanned symbols."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_equity_rule()
    symbols = ["NIFTY", "TCS", "INFY"]
    results = await engine.run(rule, symbols)
    result_symbols = {r["symbol"] for r in results}
    assert result_symbols.issubset(set(symbols))


@pytest.mark.asyncio
async def test_run_fo_returns_list_of_dicts():
    """IndiaScanEngine.run() with F&O template returns list of dicts."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_fo_rule()
    results = await engine.run(rule, ["NIFTY", "RELIANCE"])
    assert isinstance(results, list)
    for r in results:
        assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_fo_template_calls_get_option_chain():
    """F&O template scan must call get_option_chain() for each symbol."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_fo_rule()
    symbols = ["NIFTY", "RELIANCE", "TCS"]
    await engine.run(rule, symbols)
    assert adapter._call_count["get_option_chain"] == len(symbols)


@pytest.mark.asyncio
async def test_equity_template_does_not_call_get_option_chain():
    """Equity template scan must NOT call get_option_chain()."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_equity_rule()
    symbols = ["NIFTY", "RELIANCE", "TCS"]
    await engine.run(rule, symbols)
    assert adapter._call_count["get_option_chain"] == 0


# ─── _evaluate_condition() unit tests ────────────────────────────────────────

def test_evaluate_condition_near_max_pain_within_threshold():
    """near_max_pain returns True when spot is within threshold_pct of max_pain."""
    engine = IndiaScanEngine(MockIndiaAdapter())
    # spot=18500, max_pain=18510 → distance = 10/18510 * 100 ≈ 0.054% < 1%
    indicators = {"spot": 18500.0, "max_pain": 18510.0}
    cond = {"type": "near_max_pain", "threshold_pct": 1.0}
    assert engine._evaluate_condition(cond, indicators) is True


def test_evaluate_condition_near_max_pain_outside_threshold():
    """near_max_pain returns False when spot is outside threshold_pct of max_pain."""
    engine = IndiaScanEngine(MockIndiaAdapter())
    # spot=18500, max_pain=18700 → distance = 200/18700 * 100 ≈ 1.07% > 1%
    indicators = {"spot": 18500.0, "max_pain": 18700.0}
    cond = {"type": "near_max_pain", "threshold_pct": 1.0}
    assert engine._evaluate_condition(cond, indicators) is False


def test_evaluate_condition_high_gex_above_threshold():
    """high_gex returns True when net_gex > threshold."""
    engine = IndiaScanEngine(MockIndiaAdapter())
    indicators = {"net_gex": 500.0}
    cond = {"type": "high_gex", "threshold": 0}
    assert engine._evaluate_condition(cond, indicators) is True


def test_evaluate_condition_high_gex_below_threshold():
    """high_gex returns False when net_gex <= threshold."""
    engine = IndiaScanEngine(MockIndiaAdapter())
    indicators = {"net_gex": -100.0}
    cond = {"type": "high_gex", "threshold": 0}
    assert engine._evaluate_condition(cond, indicators) is False


def test_evaluate_condition_between_oi_pcr_in_range():
    """between condition on oi_pcr returns True when value is in range."""
    engine = IndiaScanEngine(MockIndiaAdapter())
    # oi_pcr = 1.0 — between 0.8 and 1.2
    indicators = {"oi_pcr": 1.0}
    cond = {"type": "between", "indicator": "oi_pcr", "min": 0.8, "max": 1.2}
    assert engine._evaluate_condition(cond, indicators) is True


def test_evaluate_condition_between_oi_pcr_out_of_range():
    """between condition on oi_pcr returns False when value is outside range."""
    engine = IndiaScanEngine(MockIndiaAdapter())
    # oi_pcr = 1.8 — outside 0.8 to 1.2
    indicators = {"oi_pcr": 1.8}
    cond = {"type": "between", "indicator": "oi_pcr", "min": 0.8, "max": 1.2}
    assert engine._evaluate_condition(cond, indicators) is False


def test_evaluate_condition_greater_than_iv_rank():
    """greater_than on iv_rank returns correct result."""
    engine = IndiaScanEngine(MockIndiaAdapter())
    indicators = {"iv_rank": 75.0}
    cond_pass = {"type": "greater_than", "indicator": "iv_rank", "value": 60}
    cond_fail = {"type": "greater_than", "indicator": "iv_rank", "value": 80}
    assert engine._evaluate_condition(cond_pass, indicators) is True
    assert engine._evaluate_condition(cond_fail, indicators) is False


def test_evaluate_condition_pcr_above():
    """pcr_above returns True when oi_pcr > threshold."""
    engine = IndiaScanEngine(MockIndiaAdapter())
    indicators = {"oi_pcr": 1.6}
    cond = {"type": "pcr_above", "value": 1.5}
    assert engine._evaluate_condition(cond, indicators) is True


def test_evaluate_condition_pcr_below():
    """pcr_below returns True when oi_pcr < threshold."""
    engine = IndiaScanEngine(MockIndiaAdapter())
    indicators = {"oi_pcr": 0.7}
    cond = {"type": "pcr_below", "value": 0.8}
    assert engine._evaluate_condition(cond, indicators) is True


def test_evaluate_condition_unknown_type_returns_false():
    """Unknown condition type should return False without raising."""
    engine = IndiaScanEngine(MockIndiaAdapter())
    indicators = {"rsi": 55.0}
    cond = {"type": "totally_unknown_condition_type"}
    assert engine._evaluate_condition(cond, indicators) is False


# ─── Strength score tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_strength_score_range():
    """Strength score should always be in range 0-100."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_equity_rule(conditions=[
        {"type": "greater_than", "indicator": "rsi", "value": 0},
        {"type": "greater_than", "indicator": "adx", "value": 0},
        {"type": "greater_than", "indicator": "rsi", "value": 200},  # always fails
    ])
    results = await engine.run(rule, ["NIFTY"])
    assert len(results) == 1
    score = results[0]["strengthScore"]
    assert 0.0 <= score <= 100.0


@pytest.mark.asyncio
async def test_strength_score_all_conditions_pass():
    """Strength score = 100 when all conditions trivially pass."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_equity_rule(conditions=[
        {"type": "greater_than", "indicator": "rsi", "value": 0},
        {"type": "greater_than", "indicator": "close", "value": 0},
    ])
    results = await engine.run(rule, ["NIFTY"])
    assert len(results) == 1
    assert results[0]["strengthScore"] == 100.0


@pytest.mark.asyncio
async def test_strength_score_no_conditions_pass():
    """Strength score = 0 when all conditions fail."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_equity_rule(conditions=[
        {"type": "greater_than", "indicator": "rsi", "value": 200},
        {"type": "greater_than", "indicator": "adx", "value": 10000},
    ])
    results = await engine.run(rule, ["NIFTY"])
    assert len(results) == 1
    assert results[0]["strengthScore"] == 0.0


# ─── India template listing tests ─────────────────────────────────────────────

def test_india_template_list_returns_only_india_market():
    """list_templates filtered by INDIA market returns only India templates."""
    all_templates = list_templates()
    india_templates = [t for t in all_templates if t["market"] == "INDIA"]
    # All should have market == "INDIA"
    for t in india_templates:
        assert t["market"] == "INDIA"


def test_india_templates_count():
    """There should be at least 12 India templates (4 equity + 4 F&O + 4 options)."""
    all_templates = list_templates()
    india_templates = [t for t in all_templates if t["market"] == "INDIA"]
    assert len(india_templates) >= 12


def test_india_template_ids_are_unique():
    """India template IDs should all be unique."""
    all_templates = list_templates()
    india_templates = [t for t in all_templates if t["market"] == "INDIA"]
    ids = [t["id"] for t in india_templates]
    assert len(ids) == len(set(ids))


def test_india_fo_templates_have_correct_asset_class():
    """F&O India templates should have EQUITY_OPTIONS assetClass."""
    all_templates = list_templates()
    fo_templates = [
        t for t in all_templates
        if t["market"] == "INDIA" and t["id"].startswith("india_fo")
    ]
    assert len(fo_templates) > 0
    for t in fo_templates:
        assert t["assetClass"] == "EQUITY_OPTIONS"


def test_india_eq_templates_have_equity_asset_class():
    """Equity India templates should have EQUITY assetClass."""
    all_templates = list_templates()
    eq_templates = [
        t for t in all_templates
        if t["market"] == "INDIA" and t["id"].startswith("india_eq")
    ]
    assert len(eq_templates) > 0
    for t in eq_templates:
        assert t["assetClass"] == "EQUITY"


# ─── ScanResult structure tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_has_required_keys():
    """ScanResult should contain all required keys."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_equity_rule()
    results = await engine.run(rule, ["NIFTY"])
    assert len(results) == 1
    required_keys = {
        "id", "symbol", "market", "assetClass", "signalName",
        "templateId", "timeframe", "strengthScore", "timestamp", "indicatorValues",
    }
    assert required_keys.issubset(results[0].keys())


@pytest.mark.asyncio
async def test_result_ids_are_unique():
    """Each ScanResult should have a unique ID."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_equity_rule()
    results = await engine.run(rule, ["NIFTY", "RELIANCE", "TCS"])
    ids = [r["id"] for r in results]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_result_market_is_india():
    """ScanResult market field should be INDIA."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_equity_rule()
    results = await engine.run(rule, ["NIFTY"])
    assert results[0]["market"] == "INDIA"


@pytest.mark.asyncio
async def test_fo_result_indicator_values_include_fo_indicators():
    """F&O scan results should include F&O-specific indicator values."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    rule = make_fo_rule(conditions=[
        {"type": "greater_than", "indicator": "iv_rank", "value": 0},
    ])
    results = await engine.run(rule, ["NIFTY"])
    assert len(results) == 1
    ivs = results[0]["indicatorValues"]
    # F&O indicators should be present
    assert "iv_rank" in ivs
    assert "oi_pcr" in ivs
    assert "max_pain" in ivs


@pytest.mark.asyncio
async def test_not_enough_candles_returns_no_result():
    """Engine should return no result for symbols with fewer candles than min_candles."""
    adapter = MockIndiaAdapter()
    engine = IndiaScanEngine(adapter)
    # Require more candles than the adapter provides (250)
    rule = make_equity_rule(min_candles=300)
    results = await engine.run(rule, ["NIFTY"])
    assert results == []


@pytest.mark.asyncio
async def test_run_handles_exceptions_gracefully():
    """IndiaScanEngine.run() silently drops symbols that raise exceptions."""

    class FailingAdapter(DataAdapter):
        async def get_candles(self, symbol, timeframe, from_date, to_date):
            raise RuntimeError("Simulated failure")

        async def get_quote(self, symbol):
            return {}

        async def get_option_chain(self, symbol, expiry=None):
            return {}

        async def search_symbols(self, query):
            return []

    engine = IndiaScanEngine(FailingAdapter())
    rule = make_equity_rule()
    results = await engine.run(rule, ["NIFTY", "RELIANCE"])
    assert results == []

"""Tests for MockBreezeAdapter — verifies synthetic data shape."""
import pytest
from packages.data_adapters.mock_breeze_adapter import MockBreezeAdapter


@pytest.mark.asyncio
async def test_get_candles_returns_correct_shape():
    adapter = MockBreezeAdapter()
    candles = await adapter.get_candles("NIFTY", "1day", "2024-01-01", "2024-12-31")
    assert len(candles) > 240  # Approximately 1 year of trading days (250-260 weekdays)
    for c in candles:
        assert "timestamp" in c
        assert c["high"] >= c["close"] >= 0
        assert c["high"] >= c["open"] >= 0
        assert c["low"] <= c["close"]
        assert c["low"] <= c["open"]
        assert c["volume"] > 0


@pytest.mark.asyncio
async def test_get_option_chain_returns_calls_and_puts():
    adapter = MockBreezeAdapter()
    chain = await adapter.get_option_chain("NIFTY")
    assert len(chain["calls"]) == 21  # 21 strikes (-10 to +10 ATM)
    assert len(chain["puts"]) == 21
    for contract in chain["calls"] + chain["puts"]:
        assert "strike" in contract
        assert "iv" in contract
        assert "delta" in contract
        assert "ltp" in contract
        assert contract["ltp"] > 0


@pytest.mark.asyncio
async def test_india_data_service_uses_mock_without_credentials(monkeypatch):
    monkeypatch.delenv("BREEZE_API_KEY", raising=False)
    from packages.data_adapters.india_data_service import IndiaDataService
    svc = IndiaDataService()
    assert svc.is_mock is True

"""Tests for PolygonAdapter using respx (httpx mock library)."""
import pytest
import respx
import httpx

from packages.data_adapters.polygon_adapter import PolygonAdapter


MOCK_CANDLES_RESPONSE = {
    "results": [
        {"t": 1700000000000, "o": 150.0, "h": 151.5, "l": 149.0, "c": 151.0, "v": 1_000_000},
        {"t": 1700086400000, "o": 151.0, "h": 152.0, "l": 150.0, "c": 150.5, "v": 900_000},
    ],
    "status": "OK",
}


@pytest.mark.asyncio
@respx.mock
async def test_get_candles_returns_ohlcv():
    respx.get(url__regex=r".*aggs/ticker/AAPL.*").mock(
        return_value=httpx.Response(200, json=MOCK_CANDLES_RESPONSE)
    )
    adapter = PolygonAdapter(api_key="test_key")
    candles = await adapter.get_candles("AAPL", "1day", "2024-01-01", "2024-01-31")
    assert len(candles) == 2
    assert candles[0]["close"] == 151.0
    assert "timestamp" in candles[0]
    assert "volume" in candles[0]


@pytest.mark.asyncio
@respx.mock
async def test_get_candles_retries_on_429():
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=MOCK_CANDLES_RESPONSE)

    respx.get(url__regex=r".*aggs/ticker/AAPL.*").mock(side_effect=side_effect)
    adapter = PolygonAdapter(api_key="test_key")
    candles = await adapter.get_candles("AAPL", "1day", "2024-01-01", "2024-01-31")
    assert call_count == 3
    assert len(candles) == 2


@pytest.mark.asyncio
@respx.mock
async def test_search_symbols():
    mock_response = {
        "results": [
            {"ticker": "AAPL", "name": "Apple Inc.", "primary_exchange": "NASDAQ"},
        ]
    }
    respx.get(url__regex=r".*reference/tickers.*").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    adapter = PolygonAdapter(api_key="test_key")
    results = await adapter.search_symbols("apple")
    assert len(results) == 1
    assert results[0]["symbol"] == "AAPL"

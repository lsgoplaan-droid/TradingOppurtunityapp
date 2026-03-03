"""Tests for USEquityDataService failover logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from packages.data_adapters.us_data_service import USEquityDataService

MOCK_CANDLES = [{"timestamp": 1700000000000, "open": 150.0, "high": 151.0,
                 "low": 149.0, "close": 150.5, "volume": 1_000_000}]


@pytest.mark.asyncio
async def test_uses_polygon_when_available():
    polygon = AsyncMock()
    polygon.get_candles.return_value = MOCK_CANDLES
    finnhub = AsyncMock()

    svc = USEquityDataService(polygon=polygon, finnhub=finnhub)
    result = await svc.get_candles("AAPL", "1day", "2024-01-01", "2024-01-31")

    assert result == MOCK_CANDLES
    polygon.get_candles.assert_called_once()
    finnhub.get_candles.assert_not_called()


@pytest.mark.asyncio
async def test_falls_back_to_finnhub_on_polygon_error():
    polygon = AsyncMock()
    polygon.get_candles.side_effect = Exception("Polygon unavailable")
    finnhub = AsyncMock()
    finnhub.get_candles.return_value = MOCK_CANDLES

    svc = USEquityDataService(polygon=polygon, finnhub=finnhub)
    result = await svc.get_candles("AAPL", "1day", "2024-01-01", "2024-01-31")

    assert result == MOCK_CANDLES
    finnhub.get_candles.assert_called_once()


@pytest.mark.asyncio
async def test_falls_back_to_finnhub_on_empty_polygon_response():
    polygon = AsyncMock()
    polygon.get_candles.return_value = []  # empty result
    finnhub = AsyncMock()
    finnhub.get_candles.return_value = MOCK_CANDLES

    svc = USEquityDataService(polygon=polygon, finnhub=finnhub)
    result = await svc.get_candles("AAPL", "1day", "2024-01-01", "2024-01-31")

    assert result == MOCK_CANDLES

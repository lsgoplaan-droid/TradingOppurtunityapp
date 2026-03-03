"""US equity data service: Polygon.io primary, Finnhub fallback."""
import logging
from typing import Optional

from packages.data_adapters.base import DataAdapter
from packages.data_adapters.polygon_adapter import PolygonAdapter
from packages.data_adapters.finnhub_adapter import FinnhubAdapter

logger = logging.getLogger(__name__)


class USEquityDataService(DataAdapter):
    """Routes US equity requests to Polygon.io; falls back to Finnhub on failure."""

    def __init__(
        self,
        polygon: Optional[PolygonAdapter] = None,
        finnhub: Optional[FinnhubAdapter] = None,
    ):
        self._polygon = polygon or PolygonAdapter()
        self._finnhub = finnhub or FinnhubAdapter()

    async def get_candles(self, symbol: str, timeframe: str, from_date: str, to_date: str) -> list[dict]:
        try:
            result = await self._polygon.get_candles(symbol, timeframe, from_date, to_date)
            if result:
                return result
            logger.info(f"Polygon returned empty candles for {symbol}, trying Finnhub")
        except Exception as e:
            logger.warning(f"Polygon get_candles failed ({e}), falling back to Finnhub")
        return await self._finnhub.get_candles(symbol, timeframe, from_date, to_date)

    async def get_quote(self, symbol: str) -> dict:
        try:
            return await self._polygon.get_quote(symbol)
        except Exception as e:
            logger.warning(f"Polygon get_quote failed ({e}), falling back to Finnhub")
            return await self._finnhub.get_quote(symbol)

    async def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> dict:
        # Both free tiers lack options chain data; return empty with explanation
        return {
            "underlying": symbol, "expiry": expiry or "", "spot": 0.0,
            "calls": [], "puts": [],
            "_source": "us_data_service",
            "_note": "US options chain requires Polygon Starter plan or CBOE data feed",
        }

    async def search_symbols(self, query: str) -> list[dict]:
        try:
            return await self._polygon.search_symbols(query)
        except Exception as e:
            logger.warning(f"Polygon search failed ({e}), falling back to Finnhub")
            return await self._finnhub.search_symbols(query)

    async def close(self) -> None:
        await self._polygon.close()
        await self._finnhub.close()

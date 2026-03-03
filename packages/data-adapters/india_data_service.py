"""India (NSE) data service.

Uses real Breeze adapter when BREEZE_API_KEY is set.
Falls back to MockBreezeAdapter automatically for development.
"""
import os
import logging
from typing import Optional

from packages.data_adapters.base import DataAdapter
from packages.data_adapters.mock_breeze_adapter import MockBreezeAdapter

logger = logging.getLogger(__name__)


def _make_real_breeze_adapter():
    """Lazily import and construct real BreezeAdapter (requires breeze-connect installed)."""
    try:
        from packages.data_adapters.breeze_adapter import BreezeAdapter
        return BreezeAdapter()
    except ImportError:
        logger.warning("breeze-connect not installed — using mock adapter")
        return MockBreezeAdapter()


class IndiaDataService(DataAdapter):
    """
    Routes India requests to Breeze (real) or MockBreeze (development).
    Selection is automatic based on BREEZE_API_KEY env var.
    """

    def __init__(self, adapter: Optional[DataAdapter] = None):
        if adapter is not None:
            self._adapter = adapter
        elif os.environ.get("BREEZE_API_KEY"):
            logger.info("BREEZE_API_KEY found — using real Breeze adapter")
            self._adapter = _make_real_breeze_adapter()
        else:
            logger.info("BREEZE_API_KEY not set — using mock Breeze adapter for development")
            self._adapter = MockBreezeAdapter()

    async def get_candles(self, symbol: str, timeframe: str, from_date: str, to_date: str) -> list[dict]:
        return await self._adapter.get_candles(symbol, timeframe, from_date, to_date)

    async def get_quote(self, symbol: str) -> dict:
        return await self._adapter.get_quote(symbol)

    async def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> dict:
        return await self._adapter.get_option_chain(symbol, expiry)

    async def search_symbols(self, query: str) -> list[dict]:
        return await self._adapter.search_symbols(query)

    @property
    def is_mock(self) -> bool:
        return isinstance(self._adapter, MockBreezeAdapter)

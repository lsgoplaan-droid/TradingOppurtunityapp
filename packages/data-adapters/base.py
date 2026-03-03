"""Abstract base classes for data adapters and storage.

All agents program against these interfaces — never against concrete implementations.
Swap implementations by changing the concrete class, not the call sites.
"""
from abc import ABC, abstractmethod
from typing import Optional


class DataAdapter(ABC):
    """Unified interface for all market data sources."""

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: str,           # e.g. "1min", "5min", "1hour", "1day"
        from_date: str,           # ISO date "YYYY-MM-DD"
        to_date: str,             # ISO date "YYYY-MM-DD"
    ) -> list[dict]:
        """Return list of OHLCV dicts: {timestamp, open, high, low, close, volume}."""
        ...

    @abstractmethod
    async def get_quote(self, symbol: str) -> dict:
        """Return current quote: {symbol, price, change, change_pct, timestamp}."""
        ...

    @abstractmethod
    async def get_option_chain(
        self,
        symbol: str,
        expiry: Optional[str] = None,  # ISO date; None = nearest expiry
    ) -> dict:
        """Return option chain dict matching OptionsChain TypeScript shape."""
        ...

    @abstractmethod
    async def search_symbols(self, query: str) -> list[dict]:
        """Return list of {symbol, name, exchange, asset_class} matching query."""
        ...


class StorageService(ABC):
    """Unified interface for persistence — SQLite locally, DynamoDB in cloud."""

    # ── Scan results ──────────────────────────────────────────────────────────

    @abstractmethod
    async def save_scan_result(self, result: dict) -> None: ...

    @abstractmethod
    async def get_scan_results(
        self,
        limit: int = 100,
        asset_class: Optional[str] = None,
        market: Optional[str] = None,
    ) -> list[dict]: ...

    # ── Backtest results ──────────────────────────────────────────────────────

    @abstractmethod
    async def save_backtest_result(self, job_id: str, result: dict) -> None: ...

    @abstractmethod
    async def get_backtest_result(self, job_id: str) -> Optional[dict]: ...

    @abstractmethod
    async def update_backtest_status(
        self, job_id: str, status: str, error: Optional[str] = None, result_id: Optional[str] = None
    ) -> None: ...

    # ── Watchlists ────────────────────────────────────────────────────────────

    @abstractmethod
    async def save_watchlist(self, watchlist: dict) -> None: ...

    @abstractmethod
    async def get_watchlists(self) -> list[dict]: ...

    @abstractmethod
    async def get_watchlist(self, watchlist_id: str) -> Optional[dict]: ...

    # ── IV history (for IV Rank / IV Percentile) ──────────────────────────────

    @abstractmethod
    async def save_iv_record(self, symbol: str, expiry: str, date: str, iv: float) -> None: ...

    @abstractmethod
    async def get_iv_history(
        self, symbol: str, expiry: str, days: int = 252
    ) -> list[dict]: ...

"""Polygon.io adapter for US equities and options data.

Free tier: 5 requests/minute, 15-min delayed data.
Docs: https://polygon.io/docs
"""
import asyncio
import os
import logging
from typing import Optional

import httpx

from packages.data_adapters.base import DataAdapter
from packages.data_adapters.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)

POLYGON_BASE_URL = "https://api.polygon.io"

# Timeframe mapping: our canonical names -> Polygon multiplier/timespan
TIMEFRAME_MAP = {
    "1min":  ("1", "minute"),
    "5min":  ("5", "minute"),
    "15min": ("15", "minute"),
    "1hour": ("1", "hour"),
    "4hour": ("4", "hour"),
    "1day":  ("1", "day"),
    "1week": ("1", "week"),
}


class PolygonAdapter(DataAdapter):
    """Polygon.io REST adapter with rate limiting and retry logic."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("POLYGON_API_KEY", "")
        self._limiter = TokenBucketRateLimiter(tokens_per_minute=5)
        self._client = httpx.AsyncClient(
            base_url=POLYGON_BASE_URL,
            timeout=30.0,
        )

    async def _get(self, path: str, params: dict) -> dict:
        """Make a rate-limited GET with exponential backoff retry."""
        params["apiKey"] = self._api_key
        last_exc = None
        for attempt in range(3):
            await self._limiter.acquire()
            try:
                resp = await self._client.get(path, params=params)
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(f"Polygon rate limited, waiting {wait}s")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                last_exc = e
                if e.response.status_code < 500:
                    raise
                await asyncio.sleep(2 ** attempt)
            except httpx.RequestError as e:
                last_exc = e
                await asyncio.sleep(2 ** attempt)
        raise last_exc

    async def get_candles(
        self, symbol: str, timeframe: str, from_date: str, to_date: str
    ) -> list[dict]:
        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}. Use: {list(TIMEFRAME_MAP)}")
        multiplier, timespan = TIMEFRAME_MAP[timeframe]
        data = await self._get(
            f"/v2/aggs/ticker/{symbol.upper()}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
            params={"adjusted": "true", "sort": "asc", "limit": 50000},
        )
        results = data.get("results", [])
        return [
            {
                "timestamp": bar["t"],
                "open": bar["o"],
                "high": bar["h"],
                "low": bar["l"],
                "close": bar["c"],
                "volume": bar["v"],
            }
            for bar in results
        ]

    async def get_quote(self, symbol: str) -> dict:
        data = await self._get(
            f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol.upper()}",
            params={},
        )
        ticker = data.get("ticker", {})
        day = ticker.get("day", {})
        prev = ticker.get("prevDay", {})
        price = day.get("c") or prev.get("c", 0)
        prev_close = prev.get("c", price)
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        return {
            "symbol": symbol.upper(),
            "price": price,
            "change": round(change, 4),
            "change_pct": round(change_pct, 4),
            "volume": day.get("v", 0),
            "timestamp": ticker.get("updated", 0),
        }

    async def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> dict:
        """Note: Options chain requires Polygon paid plan. Returns empty chain on free tier."""
        logger.warning(
            "Polygon.io free tier does not include options chain data. "
            "Returning empty chain. Upgrade to Starter plan for options data."
        )
        return {
            "underlying": symbol.upper(),
            "expiry": expiry or "",
            "spot": 0.0,
            "calls": [],
            "puts": [],
            "_source": "polygon",
            "_error": "options_chain_requires_paid_plan",
        }

    async def search_symbols(self, query: str) -> list[dict]:
        data = await self._get(
            "/v3/reference/tickers",
            params={"search": query, "market": "stocks", "active": "true", "limit": 20},
        )
        return [
            {
                "symbol": t["ticker"],
                "name": t.get("name", ""),
                "exchange": t.get("primary_exchange", ""),
                "asset_class": "EQUITY",
            }
            for t in data.get("results", [])
        ]

    async def close(self) -> None:
        await self._client.aclose()

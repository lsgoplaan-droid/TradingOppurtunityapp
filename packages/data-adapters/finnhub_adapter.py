"""Finnhub adapter — US equity fallback data source.

Free tier: 60 requests/minute, 15-min delayed data.
Docs: https://finnhub.io/docs/api
"""
import os
import logging
import time
from typing import Optional

import httpx

from packages.data_adapters.base import DataAdapter
from packages.data_adapters.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

TIMEFRAME_MAP = {
    "1min":  "1",
    "5min":  "5",
    "15min": "15",
    "30min": "30",
    "1hour": "60",
    "1day":  "D",
    "1week": "W",
}


class FinnhubAdapter(DataAdapter):
    """Finnhub REST adapter. Used as fallback when Polygon.io is rate-limited."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("FINNHUB_API_KEY", "")
        self._limiter = TokenBucketRateLimiter(tokens_per_minute=60)
        self._client = httpx.AsyncClient(
            base_url=FINNHUB_BASE_URL,
            headers={"X-Finnhub-Token": self._api_key},
            timeout=15.0,
        )

    async def get_candles(
        self, symbol: str, timeframe: str, from_date: str, to_date: str
    ) -> list[dict]:
        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        resolution = TIMEFRAME_MAP[timeframe]
        # Convert ISO dates to Unix timestamps
        import datetime
        from_ts = int(datetime.datetime.fromisoformat(from_date).timestamp())
        to_ts = int(datetime.datetime.fromisoformat(to_date).timestamp())

        await self._limiter.acquire()
        resp = await self._client.get(
            "/stock/candle",
            params={"symbol": symbol.upper(), "resolution": resolution,
                    "from": from_ts, "to": to_ts},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("s") == "no_data" or "t" not in data:
            return []

        return [
            {
                "timestamp": int(t) * 1000,  # convert to ms
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
            }
            for t, o, h, l, c, v in zip(
                data["t"], data["o"], data["h"],
                data["l"], data["c"], data["v"]
            )
        ]

    async def get_quote(self, symbol: str) -> dict:
        await self._limiter.acquire()
        resp = await self._client.get("/quote", params={"symbol": symbol.upper()})
        resp.raise_for_status()
        data = resp.json()
        price = data.get("c", 0)
        prev = data.get("pc", price)
        change = price - prev
        return {
            "symbol": symbol.upper(),
            "price": price,
            "change": round(change, 4),
            "change_pct": round((change / prev * 100) if prev else 0, 4),
            "volume": data.get("v", 0),
            "timestamp": int(time.time() * 1000),
        }

    async def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> dict:
        return {"underlying": symbol, "expiry": expiry or "", "spot": 0.0,
                "calls": [], "puts": [], "_source": "finnhub",
                "_error": "not_supported_on_free_tier"}

    async def search_symbols(self, query: str) -> list[dict]:
        await self._limiter.acquire()
        resp = await self._client.get("/search", params={"q": query})
        resp.raise_for_status()
        return [
            {"symbol": r["symbol"], "name": r.get("description", ""),
             "exchange": r.get("type", ""), "asset_class": "EQUITY"}
            for r in resp.json().get("result", [])[:20]
        ]

    async def close(self) -> None:
        await self._client.aclose()

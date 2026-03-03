"""Mock Breeze adapter — synthetic NSE data for development without ICICI credentials.

Activated automatically when BREEZE_API_KEY env var is not set.
Returns realistic but fake data so all India scan logic can be developed and tested.
"""
import time
import random
import math
from typing import Optional
from datetime import datetime, timedelta

from packages.data_adapters.base import DataAdapter


class MockBreezeAdapter(DataAdapter):
    """Generates realistic synthetic NSE data for development."""

    # Nifty index synthetic spot
    NIFTY_SPOT = 22_000.0
    BANKNIFTY_SPOT = 47_500.0

    def _make_candles(self, base_price: float, n: int, timeframe: str) -> list[dict]:
        """Generate random walk OHLCV candles."""
        candles = []
        price = base_price
        now_ms = int(time.time() * 1000)
        timeframe_ms = {"1min": 60_000, "5min": 300_000, "15min": 900_000,
                        "1hour": 3_600_000, "1day": 86_400_000}.get(timeframe, 86_400_000)
        for i in range(n):
            change = price * random.gauss(0, 0.005)
            open_ = price + random.gauss(0, price * 0.002)
            close = open_ + change
            high = max(open_, close) * (1 + abs(random.gauss(0, 0.002)))
            low = min(open_, close) * (1 - abs(random.gauss(0, 0.002)))
            volume = int(random.gauss(500_000, 100_000))
            candles.append({
                "timestamp": now_ms - (n - i) * timeframe_ms,
                "open": round(open_, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": max(volume, 10_000),
            })
            price = close
        return candles

    def _make_option_contracts(self, spot: float, option_type: str, expiry: str) -> list[dict]:
        """Generate option chain contracts around ATM strike."""
        atm = round(spot / 100) * 100  # round to nearest 100
        strikes = [atm + i * 100 for i in range(-10, 11)]
        contracts = []
        for strike in strikes:
            moneyness = (spot - strike) / spot
            iv = 0.18 + abs(moneyness) * 0.3 + random.gauss(0, 0.01)
            t = 0.05  # ~18 days to expiry
            r = 0.07
            # Rough Black-Scholes approximation for IV
            d1 = (math.log(spot / strike) + (r + 0.5 * iv ** 2) * t) / (iv * math.sqrt(t))
            d2 = d1 - iv * math.sqrt(t)
            from math import erf, sqrt, pi, exp

            def norm_cdf(x):
                return (1 + erf(x / sqrt(2))) / 2

            if option_type == "CE":
                ltp = max(0.01, spot * norm_cdf(d1) - strike * exp(-r * t) * norm_cdf(d2))
                delta = norm_cdf(d1)
            else:
                ltp = max(0.01, strike * exp(-r * t) * norm_cdf(-d2) - spot * norm_cdf(-d1))
                delta = norm_cdf(d1) - 1

            gamma = norm_cdf(d1) / (spot * iv * sqrt(t)) * (1 / sqrt(2 * pi)) * exp(-d1 ** 2 / 2)
            theta = -(spot * norm_cdf(d1) * iv) / (2 * sqrt(t)) / 365
            vega = spot * norm_cdf(d1) * sqrt(t) / 100

            contracts.append({
                "strike": strike,
                "expiry": expiry,
                "optionType": option_type,
                "ltp": round(ltp, 2),
                "iv": round(iv, 4),
                "delta": round(delta, 4),
                "gamma": round(gamma, 6),
                "theta": round(theta, 4),
                "vega": round(vega, 4),
                "oi": random.randint(10_000, 500_000),
                "volume": random.randint(1_000, 100_000),
            })
        return contracts

    async def get_candles(self, symbol: str, timeframe: str, from_date: str, to_date: str) -> list[dict]:
        sym = symbol.upper()
        base = self.BANKNIFTY_SPOT if "BANK" in sym else self.NIFTY_SPOT
        if sym not in ("NIFTY", "BANKNIFTY"):
            # Seed by symbol so the same symbol always gets the same base price
            rng_seed = sum(ord(c) for c in sym)
            base = 500 + (rng_seed * 17) % 2500

        # Parse dates and generate one bar per business day in the range
        from datetime import date as _date, timedelta as _td
        try:
            start = _date.fromisoformat(from_date)
            end   = _date.fromisoformat(to_date)
        except (ValueError, TypeError):
            start = _date.today() - _td(days=365)
            end   = _date.today()

        if end < start:
            start, end = end, start

        # Collect all weekday dates in range
        dates = []
        cur = start
        while cur <= end:
            if cur.weekday() < 5:   # Mon–Fri only
                dates.append(cur)
            cur += _td(days=1)

        if not dates:
            dates = [end]

        # Build candles with proper timestamps
        price = base
        candles = []
        for d in dates:
            ts_ms = int(datetime.combine(d, datetime.min.time()).timestamp() * 1000)
            change = price * random.gauss(0, 0.01)
            open_  = price + random.gauss(0, price * 0.003)
            close  = open_ + change
            high   = max(open_, close) * (1 + abs(random.gauss(0, 0.003)))
            low    = min(open_, close) * (1 - abs(random.gauss(0, 0.003)))
            volume = int(abs(random.gauss(500_000, 100_000)))
            candles.append({
                "timestamp": ts_ms,
                "open":  round(open_, 2),
                "high":  round(high, 2),
                "low":   round(low, 2),
                "close": round(max(0.01, close), 2),
                "volume": max(volume, 10_000),
            })
            price = max(0.01, close)

        return candles

    async def get_quote(self, symbol: str) -> dict:
        sym = symbol.upper()
        price = self.BANKNIFTY_SPOT if "BANK" in sym else self.NIFTY_SPOT
        price += random.gauss(0, price * 0.005)
        return {"symbol": sym, "price": round(price, 2),
                "change": round(random.gauss(0, 50), 2),
                "change_pct": round(random.gauss(0, 0.3), 4),
                "volume": random.randint(1_000_000, 5_000_000),
                "timestamp": int(time.time() * 1000)}

    async def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> dict:
        sym = symbol.upper()
        spot = self.BANKNIFTY_SPOT if "BANK" in sym else self.NIFTY_SPOT
        spot += random.gauss(0, spot * 0.005)
        if not expiry:
            # Next Thursday
            today = datetime.now()
            days_until_thursday = (3 - today.weekday()) % 7 or 7
            expiry = (today + timedelta(days=days_until_thursday)).strftime("%Y-%m-%d")
        return {
            "underlying": sym,
            "expiry": expiry,
            "spot": round(spot, 2),
            "calls": self._make_option_contracts(spot, "CE", expiry),
            "puts": self._make_option_contracts(spot, "PE", expiry),
            "_source": "mock_breeze",
        }

    async def search_symbols(self, query: str) -> list[dict]:
        symbols = ["NIFTY", "BANKNIFTY", "RELIANCE", "INFY", "TCS",
                   "HDFCBANK", "ICICIBANK", "SBIN", "WIPRO", "BHARTIARTL"]
        q = query.upper()
        return [
            {"symbol": s, "name": s, "exchange": "NSE", "asset_class": "EQUITY"}
            for s in symbols if q in s
        ][:10]

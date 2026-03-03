"""Yahoo Finance data adapter — real market data, no API key required.

Supports US equities and India NSE (via .NS suffix).
yfinance calls are synchronous, wrapped in asyncio.to_thread for non-blocking use.
"""
import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Optional

from packages.data_adapters.base import DataAdapter

logger = logging.getLogger(__name__)

# Canonical timeframe -> yfinance interval
TIMEFRAME_MAP = {
    "1min":  "1m",
    "5min":  "5m",
    "15min": "15m",
    "1hour": "1h",
    "4hour": "1h",   # yfinance has no 4h; use 1h (caller can aggregate)
    "1day":  "1d",
    "1week": "1wk",
}

# Special India index tickers
_INDIA_INDEX_MAP = {
    "NIFTY":     "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "MIDCAP":    "^NSEMDCP50",
    "FINNIFTY":  "^CNXFIN",
}


def _bs_greeks(spot: float, strike: float, t: float, r: float, iv: float, option_type: str) -> dict:
    """Compute Black-Scholes Greeks from IV. Returns delta, gamma, theta, vega."""
    from math import log, sqrt, exp, erf, pi
    def norm_cdf(x):
        return (1 + erf(x / sqrt(2))) / 2
    def norm_pdf(x):
        return exp(-0.5 * x * x) / sqrt(2 * pi)

    if t <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    try:
        d1 = (log(spot / strike) + (r + 0.5 * iv ** 2) * t) / (iv * sqrt(t))
        d2 = d1 - iv * sqrt(t)
        if option_type == "CE":
            delta = norm_cdf(d1)
        else:
            delta = norm_cdf(d1) - 1
        gamma = norm_pdf(d1) / (spot * iv * sqrt(t))
        theta = (-(spot * norm_pdf(d1) * iv) / (2 * sqrt(t)) / 365
                 - r * strike * exp(-r * t) * (norm_cdf(d2) if option_type == "CE" else norm_cdf(-d2)) / 365)
        vega = spot * norm_pdf(d1) * sqrt(t) / 100
    except (ValueError, ZeroDivisionError):
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega":  round(vega, 4),
    }


class YFinanceAdapter(DataAdapter):
    """
    Real market data via Yahoo Finance.

    market="US"    — plain symbols (AAPL, MSFT, SPY)
    market="INDIA" — NSE symbols auto-suffixed with .NS (RELIANCE → RELIANCE.NS)
                     Index symbols mapped: NIFTY → ^NSEI, BANKNIFTY → ^NSEBANK
    """

    def __init__(self, market: str = "US"):
        self._market = market.upper()

    def _ticker(self, symbol: str) -> str:
        """Convert canonical symbol to yfinance ticker string."""
        sym = symbol.upper().strip()
        if self._market == "INDIA":
            if sym in _INDIA_INDEX_MAP:
                return _INDIA_INDEX_MAP[sym]
            if not sym.endswith(".NS") and not sym.startswith("^"):
                return sym + ".NS"
        return sym

    # ── get_candles ────────────────────────────────────────────────────────────

    async def get_candles(
        self, symbol: str, timeframe: str, from_date: str, to_date: str
    ) -> list[dict]:
        interval = TIMEFRAME_MAP.get(timeframe, "1d")
        ticker_sym = self._ticker(symbol)

        def _fetch():
            import yfinance as yf
            tk = yf.Ticker(ticker_sym)
            df = tk.history(start=from_date, end=to_date, interval=interval, auto_adjust=True)
            return df

        try:
            df = await asyncio.to_thread(_fetch)
        except Exception as exc:
            logger.warning(f"yfinance candles failed for {ticker_sym}: {exc} — returning empty")
            return []

        if df is None or df.empty:
            logger.warning(f"yfinance returned no candles for {ticker_sym} ({from_date}→{to_date})")
            return []

        candles = []
        for ts, row in df.iterrows():
            # ts is a pandas Timestamp; convert to UTC Unix ms
            try:
                ts_ms = int(ts.timestamp() * 1000)
            except Exception:
                ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            candles.append({
                "timestamp": ts_ms,
                "open":   round(float(row["Open"]),   4),
                "high":   round(float(row["High"]),   4),
                "low":    round(float(row["Low"]),    4),
                "close":  round(float(row["Close"]),  4),
                "volume": int(row.get("Volume", 0) or 0),
            })
        return candles

    # ── get_quote ──────────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> dict:
        ticker_sym = self._ticker(symbol)

        def _fetch():
            import yfinance as yf
            tk = yf.Ticker(ticker_sym)
            info = tk.fast_info
            return info

        try:
            info = await asyncio.to_thread(_fetch)
            price     = float(info.last_price or 0)
            prev      = float(info.previous_close or price)
            change    = round(price - prev, 4)
            chg_pct   = round((change / prev * 100) if prev else 0, 4)
            volume    = int(info.three_month_average_volume or 0)
        except Exception as exc:
            logger.warning(f"yfinance quote failed for {ticker_sym}: {exc}")
            return {"symbol": symbol.upper(), "price": 0.0, "change": 0.0,
                    "change_pct": 0.0, "volume": 0,
                    "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)}

        return {
            "symbol":     symbol.upper(),
            "price":      round(price, 4),
            "change":     change,
            "change_pct": chg_pct,
            "volume":     volume,
            "timestamp":  int(datetime.now(timezone.utc).timestamp() * 1000),
        }

    # ── get_option_chain ───────────────────────────────────────────────────────

    async def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> dict:
        """
        Fetch real option chain from Yahoo Finance.
        Greeks are computed from IV via Black-Scholes (yfinance doesn't provide them directly).
        India NSE options chains have limited data in yfinance — falls back to mock if empty.
        """
        ticker_sym = self._ticker(symbol)

        def _fetch():
            import yfinance as yf
            tk = yf.Ticker(ticker_sym)
            dates = tk.options          # list of expiry date strings "YYYY-MM-DD"
            if not dates:
                return None, None, None, 0.0
            # Pick requested expiry or nearest
            if expiry and expiry in dates:
                chosen = expiry
            else:
                chosen = dates[0]       # nearest expiry
            chain = tk.option_chain(chosen)
            spot  = float(tk.fast_info.last_price or 0)
            return chain.calls, chain.puts, chosen, spot

        try:
            calls_df, puts_df, chosen_expiry, spot = await asyncio.to_thread(_fetch)
        except Exception as exc:
            logger.warning(f"yfinance option chain failed for {ticker_sym}: {exc}")
            return self._empty_chain(symbol, expiry)

        if calls_df is None or (calls_df.empty and puts_df.empty):
            logger.warning(f"yfinance returned empty option chain for {ticker_sym}")
            return self._empty_chain(symbol, expiry)

        # Time to expiry in years
        try:
            from datetime import date as _date
            exp_d = _date.fromisoformat(chosen_expiry)
            t = max((exp_d - _date.today()).days / 365.0, 1 / 365)
        except Exception:
            t = 0.05
        r = 0.05  # risk-free rate approximation

        def _parse_options(df, option_type: str) -> list[dict]:
            rows = []
            for _, row in df.iterrows():
                strike = float(row.get("strike", 0))
                ltp    = float(row.get("lastPrice", 0) or 0)
                iv     = float(row.get("impliedVolatility", 0.2) or 0.2)
                oi     = int(row.get("openInterest", 0) or 0)
                vol    = int(row.get("volume", 0) or 0)
                greeks = _bs_greeks(spot, strike, t, r, iv, option_type)
                rows.append({
                    "strike":     round(strike, 2),
                    "expiry":     chosen_expiry,
                    "optionType": option_type,
                    "ltp":        round(ltp, 2),
                    "iv":         round(iv, 4),
                    "oi":         oi,
                    "volume":     vol,
                    **greeks,
                })
            return rows

        return {
            "underlying": symbol.upper(),
            "expiry":     chosen_expiry,
            "spot":       round(spot, 2),
            "calls":      _parse_options(calls_df, "CE"),
            "puts":       _parse_options(puts_df,  "PE"),
            "_source":    "yfinance",
        }

    def _empty_chain(self, symbol: str, expiry: Optional[str]) -> dict:
        return {
            "underlying": symbol.upper(),
            "expiry":     expiry or "",
            "spot":       0.0,
            "calls":      [],
            "puts":       [],
            "_source":    "yfinance_empty",
        }

    # ── search_symbols ─────────────────────────────────────────────────────────

    async def search_symbols(self, query: str) -> list[dict]:
        q = query.upper().strip()

        def _fetch():
            import yfinance as yf
            results = []
            # Try exact match first
            candidates = [q]
            if self._market == "INDIA" and not q.endswith(".NS") and not q.startswith("^"):
                candidates.append(q + ".NS")
            for sym in candidates:
                try:
                    info = yf.Ticker(sym).fast_info
                    if info.last_price:
                        results.append(sym)
                except Exception:
                    pass
            return results

        try:
            hits = await asyncio.to_thread(_fetch)
        except Exception:
            hits = []

        out = []
        for sym in hits:
            clean = sym.replace(".NS", "") if sym.endswith(".NS") else sym
            out.append({
                "symbol":      clean,
                "name":        clean,
                "exchange":    "NSE" if self._market == "INDIA" else "US",
                "asset_class": "EQUITY",
            })
        return out[:10]

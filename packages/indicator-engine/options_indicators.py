"""
Options-specific indicator computation.

All functions work with plain Python floats / lists / dicts.
No external dependencies beyond standard library and numpy.
"""
import math
import numpy as np
from typing import Optional


# ─── IV Rank & IV Percentile ──────────────────────────────────────────────────

def compute_iv_rank(current_iv: float, iv_history_52w: list[float]) -> float:
    """
    IV Rank: position of current IV within its 52-week range.
    Returns 0-100. Higher = IV is elevated relative to its range.
    """
    if not iv_history_52w:
        return 50.0
    iv_min = min(iv_history_52w)
    iv_max = max(iv_history_52w)
    if iv_max == iv_min:
        return 50.0
    return round(((current_iv - iv_min) / (iv_max - iv_min)) * 100, 2)


def compute_iv_percentile(current_iv: float, iv_history_252d: list[float]) -> float:
    """
    IV Percentile: percentage of days in past year where IV was BELOW current IV.
    More robust than IVR when IV has had extreme spikes.
    Returns 0-100.
    """
    if not iv_history_252d:
        return 50.0
    below = sum(1 for iv in iv_history_252d if iv < current_iv)
    return round((below / len(iv_history_252d)) * 100, 2)


# ─── Put/Call Ratio ───────────────────────────────────────────────────────────

def compute_pcr(
    put_oi: float,
    call_oi: float,
    put_vol: float,
    call_vol: float,
) -> dict:
    """
    Put/Call Ratio — two variants.

    OI-based PCR > 1.2 = bullish (hedgers buying puts).
    Vol-based PCR > 1.2 = bearish (put buyers active).
    NSE interpretation: PCR_OI > 1.2 bullish, < 0.8 bearish.
    """
    pcr_oi = round(put_oi / call_oi, 4) if call_oi > 0 else 0.0
    pcr_vol = round(put_vol / call_vol, 4) if call_vol > 0 else 0.0
    sentiment_oi = "bullish" if pcr_oi > 1.2 else ("bearish" if pcr_oi < 0.8 else "neutral")
    return {
        "pcr_oi": pcr_oi,
        "pcr_vol": pcr_vol,
        "sentiment_oi": sentiment_oi,
    }


# ─── Max Pain ─────────────────────────────────────────────────────────────────

def compute_max_pain(chain: dict) -> float:
    """
    Max Pain: strike where aggregate dollar loss to option buyers is maximised.

    This is where the market tends to gravitate at expiry.
    Provide chain as: {"calls": [...], "puts": [...], "spot": float}
    Each contract: {"strike": float, "oi": int}
    """
    calls = chain.get("calls", [])
    puts = chain.get("puts", [])
    all_strikes = sorted(set(c["strike"] for c in calls + puts))

    if not all_strikes:
        return chain.get("spot", 0.0)

    min_pain = float("inf")
    max_pain_strike = all_strikes[0]

    for test_strike in all_strikes:
        call_pain = sum(
            max(0, test_strike - c["strike"]) * c["oi"] for c in calls
        )
        put_pain = sum(
            max(0, p["strike"] - test_strike) * p["oi"] for p in puts
        )
        total_pain = call_pain + put_pain
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = test_strike

    return float(max_pain_strike)


# ─── Unusual Options Activity ─────────────────────────────────────────────────

def compute_uoa(
    volume: float,
    avg_oi_30d: float,
    threshold: float = 3.0,
) -> bool:
    """
    Unusual Options Activity: volume is unusually high relative to recent OI.
    Returns True if volume > threshold * avg_oi_30d.
    """
    if avg_oi_30d <= 0:
        return False
    return (volume / avg_oi_30d) >= threshold


def compute_uoa_ratio(volume: float, avg_oi_30d: float) -> float:
    """Returns the raw volume/OI ratio for display."""
    if avg_oi_30d <= 0:
        return 0.0
    return round(volume / avg_oi_30d, 2)


# ─── Black-Scholes Greeks ─────────────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    return (1 + math.erf(x / math.sqrt(2))) / 2


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def compute_greeks_bs(
    S: float,       # Spot price
    K: float,       # Strike price
    T: float,       # Time to expiry in years
    r: float,       # Risk-free rate (annual, e.g. 0.05 for 5%)
    sigma: float,   # Implied volatility (annual, e.g. 0.20 for 20%)
    option_type: str,  # "CE" (call) or "PE" (put)
) -> dict:
    """
    Black-Scholes option Greeks.

    Returns: delta, gamma, theta (per day), vega (per 1% IV move), rho, iv, price.
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0,
                "rho": 0, "iv": sigma, "price": max(0, S - K if option_type == "CE" else K - S)}

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "CE":
        price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
        delta = _norm_cdf(d1)
        rho = K * T * math.exp(-r * T) * _norm_cdf(d2) / 100
        theta = (
            -(S * _norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * _norm_cdf(d2)
        ) / 365
    else:
        price = K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1
        rho = -K * T * math.exp(-r * T) * _norm_cdf(-d2) / 100
        theta = (
            -(S * _norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
            + r * K * math.exp(-r * T) * _norm_cdf(-d2)
        ) / 365

    gamma = _norm_pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * _norm_pdf(d1) * math.sqrt(T) / 100  # per 1% move in IV

    return {
        "price": round(max(0, price), 4),
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "rho": round(rho, 4),
        "iv": sigma,
    }


# ─── NSE-specific ─────────────────────────────────────────────────────────────

def compute_gamma_exposure(chain: dict) -> float:
    """
    Net gamma exposure (GEX) at spot. Positive GEX = market makers long gamma (stabilising).
    Negative GEX = market makers short gamma (amplifying moves).
    """
    spot = chain.get("spot", 0)
    if not spot:
        return 0.0
    call_gex = sum(
        c.get("gamma", 0) * c.get("oi", 0) * spot * 0.01
        for c in chain.get("calls", [])
    )
    put_gex = sum(
        p.get("gamma", 0) * p.get("oi", 0) * spot * 0.01
        for p in chain.get("puts", [])
    )
    return round(call_gex - put_gex, 2)

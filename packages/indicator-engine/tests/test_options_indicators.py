"""Tests for options indicators."""
import math
import pytest
from packages.indicator_engine.options_indicators import (
    compute_iv_rank, compute_iv_percentile, compute_pcr,
    compute_max_pain, compute_uoa, compute_greeks_bs, compute_gamma_exposure,
)


def test_iv_rank_at_high():
    history = [0.10, 0.15, 0.20, 0.25, 0.30]
    assert compute_iv_rank(0.30, history) == 100.0


def test_iv_rank_at_low():
    history = [0.10, 0.15, 0.20, 0.25, 0.30]
    assert compute_iv_rank(0.10, history) == 0.0


def test_iv_rank_midpoint():
    history = [0.10, 0.20, 0.30]
    rank = compute_iv_rank(0.20, history)
    assert abs(rank - 50.0) < 1e-9


def test_iv_rank_empty_history():
    assert compute_iv_rank(0.20, []) == 50.0


def test_iv_percentile_all_below():
    history = [0.10, 0.15, 0.18]
    pct = compute_iv_percentile(0.20, history)
    assert pct == 100.0


def test_iv_percentile_none_below():
    history = [0.25, 0.30, 0.35]
    pct = compute_iv_percentile(0.20, history)
    assert pct == 0.0


def test_pcr_bullish():
    result = compute_pcr(put_oi=150_000, call_oi=100_000, put_vol=80_000, call_vol=60_000)
    assert result["pcr_oi"] == 1.5
    assert result["sentiment_oi"] == "bullish"


def test_pcr_bearish():
    result = compute_pcr(put_oi=70_000, call_oi=100_000, put_vol=50_000, call_vol=60_000)
    assert result["pcr_oi"] == 0.7
    assert result["sentiment_oi"] == "bearish"


def test_max_pain_calculation():
    # Create a simple chain: max pain should be at strike 100
    chain = {
        "spot": 102.0,
        "calls": [
            {"strike": 90, "oi": 1000},
            {"strike": 100, "oi": 5000},
            {"strike": 110, "oi": 500},
        ],
        "puts": [
            {"strike": 90, "oi": 500},
            {"strike": 100, "oi": 5000},
            {"strike": 110, "oi": 1000},
        ],
    }
    mp = compute_max_pain(chain)
    assert mp == 100.0  # ATM has most pain distributed equally


def test_max_pain_empty_chain():
    chain = {"spot": 100.0, "calls": [], "puts": []}
    mp = compute_max_pain(chain)
    assert mp == 100.0


def test_uoa_detects_spike():
    assert compute_uoa(volume=9_000, avg_oi_30d=2_000, threshold=3.0) is True


def test_uoa_normal_activity():
    assert compute_uoa(volume=5_000, avg_oi_30d=5_000, threshold=3.0) is False


def test_greeks_bs_call_delta_between_0_and_1():
    greeks = compute_greeks_bs(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type="CE")
    assert 0 < greeks["delta"] < 1


def test_greeks_bs_put_delta_between_minus1_and_0():
    greeks = compute_greeks_bs(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type="PE")
    assert -1 < greeks["delta"] < 0


def test_greeks_bs_call_put_parity():
    """Put-call parity: C - P = S - K*e^(-rT)"""
    S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.20
    call = compute_greeks_bs(S, K, T, r, sigma, "CE")
    put = compute_greeks_bs(S, K, T, r, sigma, "PE")
    parity = S - K * math.exp(-r * T)
    assert abs((call["price"] - put["price"]) - parity) < 0.01


def test_greeks_bs_gamma_positive():
    greeks = compute_greeks_bs(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type="CE")
    assert greeks["gamma"] > 0


def test_greeks_bs_vega_positive():
    greeks = compute_greeks_bs(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type="CE")
    assert greeks["vega"] > 0


def test_greeks_bs_theta_negative_call():
    greeks = compute_greeks_bs(S=100, K=100, T=0.25, r=0.05, sigma=0.20, option_type="CE")
    assert greeks["theta"] < 0


def test_greeks_bs_deep_itm_call_delta_near_1():
    greeks = compute_greeks_bs(S=150, K=100, T=0.25, r=0.05, sigma=0.20, option_type="CE")
    assert greeks["delta"] > 0.9


def test_greeks_bs_zero_time():
    greeks = compute_greeks_bs(S=100, K=100, T=0, r=0.05, sigma=0.20, option_type="CE")
    assert greeks["price"] >= 0

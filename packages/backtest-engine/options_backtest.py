"""
Options backtesting engine — FR-013.

Simulates options strategies using Black-Scholes pricing with realized
volatility (20-day rolling std of log-returns) as a proxy for IV.

Supported strategies
--------------------
long_call         Buy ATM call at entry, hold to expiry or target/stop
long_put          Buy ATM put at entry, hold to expiry or target/stop
covered_call      Buy shares + sell OTM call; premium collected upfront
straddle          Buy ATM call + ATM put; exit when move exceeds break-even
iron_condor       Sell OTM call spread + OTM put spread; collect net premium
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Optional
from uuid import uuid4

import numpy as np

from packages.backtest_engine.engine import (
    BacktestConfig,
    _compute_metrics,
    _ts_to_date,
)


# ---------------------------------------------------------------------------
# Black-Scholes helpers
# ---------------------------------------------------------------------------

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(
    S: float,
    K: float,
    T: float,       # years to expiry
    r: float,       # risk-free rate (annual)
    sigma: float,   # implied / realized vol (annual)
    option_type: str,  # "call" or "put"
) -> float:
    """Black-Scholes option price. Returns 0 if inputs are degenerate."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, (S - K) if option_type == "call" else (K - S))
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == "call":
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    else:  # put
        return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def _realized_vol(closes: np.ndarray, window: int = 20) -> np.ndarray:
    """20-day annualized realized volatility at each bar."""
    log_ret = np.log(closes[1:] / closes[:-1])
    vol = np.full(len(closes), np.nan)
    for i in range(window, len(closes)):
        vol[i] = np.std(log_ret[i - window: i], ddof=1) * math.sqrt(252)
    # Back-fill the initial NaN bars with the first valid value
    first_valid = next((v for v in vol if not np.isnan(v)), 0.20)
    vol[:window] = first_valid
    return vol


# ---------------------------------------------------------------------------
# Options backtest config
# ---------------------------------------------------------------------------

@dataclass
class OptionsBacktestConfig:
    symbol: str
    strategy_name: str        # key in OPTIONS_STRATEGY_REGISTRY
    start_date: str
    end_date: str
    initial_capital: float
    commission_pct: float
    expiry_days: int = 30     # days to option expiry at trade initiation
    strike_offset_pct: float = 0.0   # 0 = ATM; +0.05 = 5% OTM call/put
    wing_width_pct: float = 0.05     # iron condor wing width (5% OTM)
    risk_free_rate: float = 0.05     # 5% annualised
    profit_target_pct: float = 0.50  # exit at 50% of max profit
    stop_loss_pct: float = 2.0       # exit at 2× premium paid (100% loss of premium)
    contracts: int = 1               # number of option contracts (100 shares each)


# ---------------------------------------------------------------------------
# Strategy implementations — each returns a list of trade dicts
# ---------------------------------------------------------------------------

def _run_long_call(
    config: OptionsBacktestConfig,
    timestamps: np.ndarray,
    closes: np.ndarray,
    vols: np.ndarray,
) -> tuple[list[dict], list[dict]]:
    """Buy one ATM call at every entry signal (simple: buy on first bar of each month)."""
    equity = config.initial_capital
    equity_curve = []
    trades = []
    r = config.risk_free_rate
    T0 = config.expiry_days / 365.0
    n = len(closes)

    i = 0
    while i < n:
        S = closes[i]
        K = round(S * (1.0 + config.strike_offset_pct), 2)
        sigma = vols[i] if not np.isnan(vols[i]) else 0.20
        prem = bs_price(S, K, T0, r, sigma, "call") * 100 * config.contracts
        cost = prem * (1 + config.commission_pct)
        if cost > equity:
            equity_curve.append({"timestamp": int(timestamps[i]), "value": round(equity, 2)})
            i += 1
            continue

        equity -= cost
        entry_date = _ts_to_date(int(timestamps[i]))
        entry_idx = i
        prem_paid = prem
        _opts = {"stockPrice": round(S, 4), "strikePrice": round(K, 4)}

        # Hold until expiry or profit/stop
        exit_i = min(i + config.expiry_days, n - 1)
        for j in range(i + 1, exit_i + 1):
            T_rem = max((exit_i - j) / 365.0, 0.0)
            S_j = closes[j]
            sigma_j = vols[j] if not np.isnan(vols[j]) else sigma
            current_val = bs_price(S_j, K, T_rem, r, sigma_j, "call") * 100 * config.contracts
            pnl = current_val - prem_paid
            if current_val >= prem_paid * (1 + config.profit_target_pct):
                # Profit target hit
                proceeds = current_val * (1 - config.commission_pct)
                equity += proceeds
                trades.append({
                    "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[j])),
                    "direction": "LONG", "entryPrice": round(prem_paid / (100 * config.contracts), 4),
                    "exitPrice": round(current_val / (100 * config.contracts), 4),
                    "pnl": round(proceeds - prem_paid, 2),
                    "pnlPct": round((proceeds - prem_paid) / prem_paid * 100, 4),
                    "_duration_bars": j - entry_idx, **_opts,
                })
                i = j + 1
                break
            if pnl <= -prem_paid * config.stop_loss_pct:
                # Stop loss: expire worthless-ish
                proceeds = max(current_val * (1 - config.commission_pct), 0)
                equity += proceeds
                trades.append({
                    "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[j])),
                    "direction": "LONG", "entryPrice": round(prem_paid / (100 * config.contracts), 4),
                    "exitPrice": round(proceeds / (100 * config.contracts), 4),
                    "pnl": round(proceeds - prem_paid, 2),
                    "pnlPct": round((proceeds - prem_paid) / prem_paid * 100, 4),
                    "_duration_bars": j - entry_idx, **_opts,
                })
                i = j + 1
                break
            equity_curve.append({"timestamp": int(timestamps[j]), "value": round(equity + current_val, 2)})
        else:
            # Expiry
            S_exp = closes[exit_i]
            intrinsic = max(S_exp - K, 0) * 100 * config.contracts
            proceeds = intrinsic * (1 - config.commission_pct)
            equity += proceeds
            trades.append({
                "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[exit_i])),
                "direction": "LONG", "entryPrice": round(prem_paid / (100 * config.contracts), 4),
                "exitPrice": round(intrinsic / (100 * config.contracts), 4),
                "pnl": round(proceeds - prem_paid, 2),
                "pnlPct": round((proceeds - prem_paid) / prem_paid * 100, 4),
                "_duration_bars": exit_i - entry_idx, **_opts,
            })
            i = exit_i + 1

        equity_curve.append({"timestamp": int(timestamps[min(i, n - 1)]), "value": round(equity, 2)})
        # Skip ahead one month before next trade
        i = max(i, entry_idx + config.expiry_days)

    # Fill equity curve for any gaps
    if not equity_curve:
        equity_curve = [{"timestamp": int(timestamps[j]), "value": round(equity, 2)} for j in range(n)]

    return trades, equity_curve


def _run_long_put(
    config: OptionsBacktestConfig,
    timestamps: np.ndarray,
    closes: np.ndarray,
    vols: np.ndarray,
) -> tuple[list[dict], list[dict]]:
    """Buy ATM put — mirror of long_call but with put pricing."""
    equity = config.initial_capital
    equity_curve = []
    trades = []
    r = config.risk_free_rate
    T0 = config.expiry_days / 365.0
    n = len(closes)

    i = 0
    while i < n:
        S = closes[i]
        K = round(S * (1.0 - config.strike_offset_pct), 2)
        sigma = vols[i] if not np.isnan(vols[i]) else 0.20
        prem = bs_price(S, K, T0, r, sigma, "put") * 100 * config.contracts
        cost = prem * (1 + config.commission_pct)
        if cost > equity:
            equity_curve.append({"timestamp": int(timestamps[i]), "value": round(equity, 2)})
            i += 1
            continue

        equity -= cost
        entry_date = _ts_to_date(int(timestamps[i]))
        entry_idx = i
        prem_paid = prem
        _opts = {"stockPrice": round(S, 4), "strikePrice": round(K, 4)}

        exit_i = min(i + config.expiry_days, n - 1)
        for j in range(i + 1, exit_i + 1):
            T_rem = max((exit_i - j) / 365.0, 0.0)
            S_j = closes[j]
            sigma_j = vols[j] if not np.isnan(vols[j]) else sigma
            current_val = bs_price(S_j, K, T_rem, r, sigma_j, "put") * 100 * config.contracts
            pnl = current_val - prem_paid
            if current_val >= prem_paid * (1 + config.profit_target_pct):
                proceeds = current_val * (1 - config.commission_pct)
                equity += proceeds
                trades.append({
                    "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[j])),
                    "direction": "LONG", "entryPrice": round(prem_paid / (100 * config.contracts), 4),
                    "exitPrice": round(proceeds / (100 * config.contracts), 4),
                    "pnl": round(proceeds - prem_paid, 2),
                    "pnlPct": round((proceeds - prem_paid) / prem_paid * 100, 4),
                    "_duration_bars": j - entry_idx, **_opts,
                })
                i = j + 1
                break
            if pnl <= -prem_paid * config.stop_loss_pct:
                proceeds = max(current_val * (1 - config.commission_pct), 0)
                equity += proceeds
                trades.append({
                    "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[j])),
                    "direction": "LONG", "entryPrice": round(prem_paid / (100 * config.contracts), 4),
                    "exitPrice": round(proceeds / (100 * config.contracts), 4),
                    "pnl": round(proceeds - prem_paid, 2),
                    "pnlPct": round((proceeds - prem_paid) / prem_paid * 100, 4),
                    "_duration_bars": j - entry_idx, **_opts,
                })
                i = j + 1
                break
            equity_curve.append({"timestamp": int(timestamps[j]), "value": round(equity + current_val, 2)})
        else:
            S_exp = closes[exit_i]
            intrinsic = max(K - S_exp, 0) * 100 * config.contracts
            proceeds = intrinsic * (1 - config.commission_pct)
            equity += proceeds
            trades.append({
                "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[exit_i])),
                "direction": "LONG", "entryPrice": round(prem_paid / (100 * config.contracts), 4),
                "exitPrice": round(intrinsic / (100 * config.contracts), 4),
                "pnl": round(proceeds - prem_paid, 2),
                "pnlPct": round((proceeds - prem_paid) / prem_paid * 100, 4),
                "_duration_bars": exit_i - entry_idx, **_opts,
            })
            i = exit_i + 1

        equity_curve.append({"timestamp": int(timestamps[min(i, n - 1)]), "value": round(equity, 2)})
        i = max(i, entry_idx + config.expiry_days)

    if not equity_curve:
        equity_curve = [{"timestamp": int(timestamps[j]), "value": round(equity, 2)} for j in range(n)]

    return trades, equity_curve


def _run_straddle(
    config: OptionsBacktestConfig,
    timestamps: np.ndarray,
    closes: np.ndarray,
    vols: np.ndarray,
) -> tuple[list[dict], list[dict]]:
    """Buy ATM call + ATM put. Profit when price moves > combined premium."""
    equity = config.initial_capital
    equity_curve = []
    trades = []
    r = config.risk_free_rate
    T0 = config.expiry_days / 365.0
    n = len(closes)

    i = 0
    while i < n:
        S = closes[i]
        K = S
        sigma = vols[i] if not np.isnan(vols[i]) else 0.20
        call_prem = bs_price(S, K, T0, r, sigma, "call") * 100 * config.contracts
        put_prem  = bs_price(S, K, T0, r, sigma, "put")  * 100 * config.contracts
        total_prem = call_prem + put_prem
        cost = total_prem * (1 + config.commission_pct)
        if cost > equity:
            equity_curve.append({"timestamp": int(timestamps[i]), "value": round(equity, 2)})
            i += 1
            continue

        equity -= cost
        entry_date = _ts_to_date(int(timestamps[i]))
        entry_idx = i
        _opts = {
            "stockPrice": round(S, 4), "strikePrice": round(K, 4),
            "leg1Premium": round(call_prem / (100 * config.contracts), 4),
            "leg2Premium": round(put_prem  / (100 * config.contracts), 4),
        }

        exit_i = min(i + config.expiry_days, n - 1)
        for j in range(i + 1, exit_i + 1):
            T_rem = max((exit_i - j) / 365.0, 0.0)
            S_j = closes[j]
            sigma_j = vols[j] if not np.isnan(vols[j]) else sigma
            straddle_val = (
                bs_price(S_j, K, T_rem, r, sigma_j, "call") +
                bs_price(S_j, K, T_rem, r, sigma_j, "put")
            ) * 100 * config.contracts
            if straddle_val >= total_prem * (1 + config.profit_target_pct):
                proceeds = straddle_val * (1 - config.commission_pct)
                equity += proceeds
                trades.append({
                    "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[j])),
                    "direction": "LONG", "entryPrice": round(total_prem / (100 * config.contracts), 4),
                    "exitPrice": round(proceeds / (100 * config.contracts), 4),
                    "pnl": round(proceeds - total_prem, 2),
                    "pnlPct": round((proceeds - total_prem) / total_prem * 100, 4),
                    "_duration_bars": j - entry_idx, **_opts,
                })
                i = j + 1
                break
            if straddle_val <= total_prem * (1 - config.stop_loss_pct / 2):
                proceeds = max(straddle_val * (1 - config.commission_pct), 0)
                equity += proceeds
                trades.append({
                    "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[j])),
                    "direction": "LONG", "entryPrice": round(total_prem / (100 * config.contracts), 4),
                    "exitPrice": round(proceeds / (100 * config.contracts), 4),
                    "pnl": round(proceeds - total_prem, 2),
                    "pnlPct": round((proceeds - total_prem) / total_prem * 100, 4),
                    "_duration_bars": j - entry_idx, **_opts,
                })
                i = j + 1
                break
            equity_curve.append({"timestamp": int(timestamps[j]), "value": round(equity + straddle_val, 2)})
        else:
            S_exp = closes[exit_i]
            intrinsic = (max(S_exp - K, 0) + max(K - S_exp, 0)) * 100 * config.contracts
            proceeds = intrinsic * (1 - config.commission_pct)
            equity += proceeds
            trades.append({
                "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[exit_i])),
                "direction": "LONG", "entryPrice": round(total_prem / (100 * config.contracts), 4),
                "exitPrice": round(intrinsic / (100 * config.contracts), 4),
                "pnl": round(proceeds - total_prem, 2),
                "pnlPct": round((proceeds - total_prem) / total_prem * 100, 4),
                "_duration_bars": exit_i - entry_idx, **_opts,
            })
            i = exit_i + 1

        equity_curve.append({"timestamp": int(timestamps[min(i, n - 1)]), "value": round(equity, 2)})
        i = max(i, entry_idx + config.expiry_days)

    if not equity_curve:
        equity_curve = [{"timestamp": int(timestamps[j]), "value": round(equity, 2)} for j in range(n)]

    return trades, equity_curve


def _run_iron_condor(
    config: OptionsBacktestConfig,
    timestamps: np.ndarray,
    closes: np.ndarray,
    vols: np.ndarray,
) -> tuple[list[dict], list[dict]]:
    """
    Sell OTM call spread + OTM put spread.
    Collect net premium; max loss = wing_width - net_premium.
    Exit at 50% profit or 2× premium loss.
    """
    equity = config.initial_capital
    equity_curve = []
    trades = []
    r = config.risk_free_rate
    T0 = config.expiry_days / 365.0
    w = config.wing_width_pct
    n = len(closes)

    i = 0
    while i < n:
        S = closes[i]
        sigma = vols[i] if not np.isnan(vols[i]) else 0.20

        # Short call spread: sell K_sc, buy K_sc_long
        K_sc      = S * (1 + w)
        K_sc_long = S * (1 + 2 * w)
        # Short put spread: sell K_sp, buy K_sp_long
        K_sp      = S * (1 - w)
        K_sp_long = S * (1 - 2 * w)

        # Net premium collected = (short premiums) - (long premiums)
        sc_short = bs_price(S, K_sc,      T0, r, sigma, "call")
        sc_long  = bs_price(S, K_sc_long, T0, r, sigma, "call")
        sp_short = bs_price(S, K_sp,      T0, r, sigma, "put")
        sp_long  = bs_price(S, K_sp_long, T0, r, sigma, "put")
        net_premium = ((sc_short - sc_long) + (sp_short - sp_long)) * 100 * config.contracts
        if net_premium <= 0:
            equity_curve.append({"timestamp": int(timestamps[i]), "value": round(equity, 2)})
            i += 1
            continue

        equity += net_premium * (1 - config.commission_pct)
        entry_date = _ts_to_date(int(timestamps[i]))
        entry_idx = i
        _opts = {
            "stockPrice":  round(S, 4),
            "strikePrice": round(K_sc, 4),       # short call
            "strikePrice2": round(K_sp, 4),      # short put
            "strikeLong1": round(K_sc_long, 4),  # long call (protection)
            "strikeLong2": round(K_sp_long, 4),  # long put (protection)
        }

        exit_i = min(i + config.expiry_days, n - 1)
        for j in range(i + 1, exit_i + 1):
            T_rem = max((exit_i - j) / 365.0, 0.0)
            S_j = closes[j]
            sigma_j = vols[j] if not np.isnan(vols[j]) else sigma
            current_condor_value = (
                (bs_price(S_j, K_sc,      T_rem, r, sigma_j, "call") - bs_price(S_j, K_sc_long, T_rem, r, sigma_j, "call")) +
                (bs_price(S_j, K_sp,      T_rem, r, sigma_j, "put")  - bs_price(S_j, K_sp_long, T_rem, r, sigma_j, "put"))
            ) * 100 * config.contracts
            pnl_so_far = net_premium - current_condor_value
            if pnl_so_far >= net_premium * config.profit_target_pct:
                # Buy back at profit
                buyback = current_condor_value * (1 + config.commission_pct)
                equity -= buyback
                trades.append({
                    "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[j])),
                    "direction": "SHORT", "entryPrice": round(net_premium / (100 * config.contracts), 4),
                    "exitPrice": round(current_condor_value / (100 * config.contracts), 4),
                    "pnl": round(pnl_so_far, 2),
                    "pnlPct": round(pnl_so_far / net_premium * 100, 4),
                    "_duration_bars": j - entry_idx, **_opts,
                })
                i = j + 1
                break
            if pnl_so_far <= -net_premium * config.stop_loss_pct:
                buyback = current_condor_value * (1 + config.commission_pct)
                equity -= buyback
                trades.append({
                    "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[j])),
                    "direction": "SHORT", "entryPrice": round(net_premium / (100 * config.contracts), 4),
                    "exitPrice": round(current_condor_value / (100 * config.contracts), 4),
                    "pnl": round(pnl_so_far, 2),
                    "pnlPct": round(pnl_so_far / net_premium * 100, 4),
                    "_duration_bars": j - entry_idx, **_opts,
                })
                i = j + 1
                break
            equity_curve.append({"timestamp": int(timestamps[j]), "value": round(equity - current_condor_value, 2)})
        else:
            # Expire — close at intrinsic value
            S_exp = closes[exit_i]
            intrinsic = (
                max(min(S_exp, K_sc_long) - max(S_exp, K_sc), 0) +
                max(min(K_sp_long, K_sp) - min(S_exp, K_sp), 0)
            ) * 100 * config.contracts
            # Approximate: at expiry condor = max intrinsic loss bounded by wing width
            final_pnl = net_premium - intrinsic
            equity -= intrinsic * (1 + config.commission_pct)
            trades.append({
                "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[exit_i])),
                "direction": "SHORT", "entryPrice": round(net_premium / (100 * config.contracts), 4),
                "exitPrice": round(intrinsic / (100 * config.contracts), 4),
                "pnl": round(final_pnl, 2),
                "pnlPct": round(final_pnl / net_premium * 100, 4) if net_premium > 0 else 0.0,
                "_duration_bars": exit_i - entry_idx, **_opts,
            })
            i = exit_i + 1

        equity_curve.append({"timestamp": int(timestamps[min(i, n - 1)]), "value": round(equity, 2)})
        i = max(i, entry_idx + config.expiry_days)

    if not equity_curve:
        equity_curve = [{"timestamp": int(timestamps[j]), "value": round(equity, 2)} for j in range(n)]

    return trades, equity_curve


def _run_covered_call(
    config: OptionsBacktestConfig,
    timestamps: np.ndarray,
    closes: np.ndarray,
    vols: np.ndarray,
) -> tuple[list[dict], list[dict]]:
    """
    Buy 100 shares + sell one OTM call each month.
    Collect premium every cycle; gain capped at strike.
    """
    equity = config.initial_capital
    r = config.risk_free_rate
    T0 = config.expiry_days / 365.0
    w = config.strike_offset_pct if config.strike_offset_pct > 0 else 0.03  # default 3% OTM
    n = len(closes)
    equity_curve = []
    trades = []

    # Buy shares on first bar
    S0 = closes[0]
    shares = (equity * 0.90) / S0  # use 90% of capital for shares
    cost_shares = shares * S0 * (1 + config.commission_pct)
    equity -= cost_shares
    share_value = shares * closes[0]

    i = 0
    while i < n:
        S = closes[i]
        K = S * (1 + w)
        sigma = vols[i] if not np.isnan(vols[i]) else 0.20
        call_prem = bs_price(S, K, T0, r, sigma, "call") * 100 * config.contracts
        equity += call_prem * (1 - config.commission_pct)
        entry_date = _ts_to_date(int(timestamps[i]))
        entry_idx = i

        exit_i = min(i + config.expiry_days, n - 1)
        S_exp = closes[exit_i]

        # If called away, sell shares at strike; else keep shares
        if S_exp >= K:
            call_buyback = (S_exp - K) * 100 * config.contracts  # short call ITM loss
            equity -= call_buyback * (1 + config.commission_pct)
        else:
            call_buyback = 0.0

        share_value = shares * S_exp
        pnl = (S_exp - S) * shares - call_buyback + call_prem * (1 - config.commission_pct)
        trades.append({
            "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[exit_i])),
            "direction": "LONG", "entryPrice": round(S, 4),
            "exitPrice": round(S_exp, 4),
            "pnl": round(pnl, 2),
            "pnlPct": round(pnl / (S * shares) * 100, 4) if S > 0 and shares > 0 else 0.0,
            "_duration_bars": exit_i - entry_idx,
            "stockPrice": round(S, 4), "strikePrice": round(K, 4),
            "leg1Premium": round(call_prem / (100 * config.contracts), 4),
        })

        for j in range(i, exit_i + 1):
            equity_curve.append({
                "timestamp": int(timestamps[j]),
                "value": round(equity + shares * closes[j], 2)
            })

        i = exit_i + 1

    if not equity_curve:
        equity_curve = [{"timestamp": int(timestamps[j]), "value": round(equity + shares * closes[j], 2)} for j in range(n)]

    return trades, equity_curve


def _run_strangle(
    config: OptionsBacktestConfig,
    timestamps: np.ndarray,
    closes: np.ndarray,
    vols: np.ndarray,
) -> tuple[list[dict], list[dict]]:
    """Buy OTM call + OTM put (strangle). Break-even requires a larger move than a straddle."""
    equity = config.initial_capital
    equity_curve = []
    trades = []
    r = config.risk_free_rate
    T0 = config.expiry_days / 365.0
    offset = config.strike_offset_pct if config.strike_offset_pct > 0 else 0.02  # default 2% OTM
    n = len(closes)

    i = 0
    while i < n:
        S = closes[i]
        K_call = S * (1.0 + offset)
        K_put  = S * (1.0 - offset)
        sigma = vols[i] if not np.isnan(vols[i]) else 0.20
        call_prem = bs_price(S, K_call, T0, r, sigma, "call") * 100 * config.contracts
        put_prem  = bs_price(S, K_put,  T0, r, sigma, "put")  * 100 * config.contracts
        total_prem = call_prem + put_prem
        cost = total_prem * (1 + config.commission_pct)
        if cost > equity:
            equity_curve.append({"timestamp": int(timestamps[i]), "value": round(equity, 2)})
            i += 1
            continue

        equity -= cost
        entry_date = _ts_to_date(int(timestamps[i]))
        entry_idx = i
        _opts = {
            "stockPrice": round(S, 4),
            "strikePrice": round(K_call, 4), "strikePrice2": round(K_put, 4),
            "leg1Premium": round(call_prem / (100 * config.contracts), 4),
            "leg2Premium": round(put_prem  / (100 * config.contracts), 4),
        }

        exit_i = min(i + config.expiry_days, n - 1)
        for j in range(i + 1, exit_i + 1):
            T_rem = max((exit_i - j) / 365.0, 0.0)
            S_j = closes[j]
            sigma_j = vols[j] if not np.isnan(vols[j]) else sigma
            strangle_val = (
                bs_price(S_j, K_call, T_rem, r, sigma_j, "call") +
                bs_price(S_j, K_put,  T_rem, r, sigma_j, "put")
            ) * 100 * config.contracts
            if strangle_val >= total_prem * (1 + config.profit_target_pct):
                proceeds = strangle_val * (1 - config.commission_pct)
                equity += proceeds
                trades.append({
                    "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[j])),
                    "direction": "LONG",
                    "entryPrice": round(total_prem / (100 * config.contracts), 4),
                    "exitPrice": round(proceeds / (100 * config.contracts), 4),
                    "pnl": round(proceeds - total_prem, 2),
                    "pnlPct": round((proceeds - total_prem) / total_prem * 100, 4),
                    "_duration_bars": j - entry_idx, **_opts,
                })
                i = j + 1
                break
            if strangle_val <= total_prem * (1 - config.stop_loss_pct / 2):
                proceeds = max(strangle_val * (1 - config.commission_pct), 0)
                equity += proceeds
                trades.append({
                    "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[j])),
                    "direction": "LONG",
                    "entryPrice": round(total_prem / (100 * config.contracts), 4),
                    "exitPrice": round(proceeds / (100 * config.contracts), 4),
                    "pnl": round(proceeds - total_prem, 2),
                    "pnlPct": round((proceeds - total_prem) / total_prem * 100, 4),
                    "_duration_bars": j - entry_idx, **_opts,
                })
                i = j + 1
                break
            equity_curve.append({"timestamp": int(timestamps[j]), "value": round(equity + strangle_val, 2)})
        else:
            S_exp = closes[exit_i]
            intrinsic = (max(S_exp - K_call, 0) + max(K_put - S_exp, 0)) * 100 * config.contracts
            proceeds = intrinsic * (1 - config.commission_pct)
            equity += proceeds
            trades.append({
                "entryDate": entry_date, "exitDate": _ts_to_date(int(timestamps[exit_i])),
                "direction": "LONG",
                "entryPrice": round(total_prem / (100 * config.contracts), 4),
                "exitPrice": round(intrinsic / (100 * config.contracts), 4),
                "pnl": round(proceeds - total_prem, 2),
                "pnlPct": round((proceeds - total_prem) / total_prem * 100, 4),
                "_duration_bars": exit_i - entry_idx, **_opts,
            })
            i = exit_i + 1

        equity_curve.append({"timestamp": int(timestamps[min(i, n - 1)]), "value": round(equity, 2)})
        i = max(i, entry_idx + config.expiry_days)

    if not equity_curve:
        equity_curve = [{"timestamp": int(timestamps[j]), "value": round(equity, 2)} for j in range(n)]

    return trades, equity_curve


def _run_zero_dte_straddle(
    config: OptionsBacktestConfig,
    timestamps: np.ndarray,
    closes: np.ndarray,
    vols: np.ndarray,
) -> tuple[list[dict], list[dict]]:
    """0DTE straddle — ATM call + put expiring the same day (expiry_days=1)."""
    return _run_straddle(replace(config, expiry_days=1), timestamps, closes, vols)


def _run_zero_dte_strangle(
    config: OptionsBacktestConfig,
    timestamps: np.ndarray,
    closes: np.ndarray,
    vols: np.ndarray,
) -> tuple[list[dict], list[dict]]:
    """0DTE strangle — OTM call + put expiring the same day (expiry_days=1, 1% OTM by default)."""
    offset = config.strike_offset_pct if config.strike_offset_pct > 0 else 0.01
    return _run_strangle(replace(config, expiry_days=1, strike_offset_pct=offset), timestamps, closes, vols)


# ---------------------------------------------------------------------------
# Registry + dispatcher
# ---------------------------------------------------------------------------

OPTIONS_STRATEGY_REGISTRY = {
    "long_call":          _run_long_call,
    "long_put":           _run_long_put,
    "straddle":           _run_straddle,
    "strangle":           _run_strangle,
    "iron_condor":        _run_iron_condor,
    "covered_call":       _run_covered_call,
    "zero_dte_straddle":  _run_zero_dte_straddle,
    "zero_dte_strangle":  _run_zero_dte_strangle,
}


def run_options_backtest(
    config: OptionsBacktestConfig,
    timestamps: np.ndarray,
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
) -> dict:
    """
    Entry point for options backtesting.
    Delegates to the registered strategy function, then builds BacktestResult.
    """
    strategy_fn = OPTIONS_STRATEGY_REGISTRY.get(config.strategy_name)
    if strategy_fn is None:
        raise ValueError(f"Unknown options strategy: {config.strategy_name}")

    vols = _realized_vol(closes, window=20)
    trades, equity_curve = strategy_fn(config, timestamps, closes, vols)

    # Ensure equity_curve is non-empty and sorted
    if not equity_curve:
        equity_curve = [{"timestamp": int(timestamps[i]), "value": config.initial_capital}
                        for i in range(len(timestamps))]
    equity_curve.sort(key=lambda x: x["timestamp"])

    # Re-use the existing metrics computation
    bt_config = BacktestConfig(
        symbol=config.symbol,
        strategy_name=config.strategy_name,
        start_date=config.start_date,
        end_date=config.end_date,
        initial_capital=config.initial_capital,
        position_sizing="fixed",
        commission_pct=config.commission_pct,
    )
    final_equity = equity_curve[-1]["value"] if equity_curve else config.initial_capital
    result = _compute_metrics(bt_config, trades, equity_curve, final_equity)

    # Options-specific metrics
    n_trades = len(trades)
    if n_trades > 0:
        # % of long-option trades that expired worthless (exit premium near zero)
        worthless = sum(1 for t in trades if t.get("exitPrice", 1.0) < 0.05)
        pct_expired_worthless = round(worthless / n_trades * 100, 1)
        # Average DTE at exit (in bars/days)
        avg_dte_at_exit = round(
            sum(t.get("_duration_bars", 0) for t in trades) / n_trades, 1
        )
    else:
        pct_expired_worthless = 0.0
        avg_dte_at_exit = 0.0

    result["pctExpiredWorthless"] = pct_expired_worthless
    result["avgDteAtExit"] = avg_dte_at_exit
    return result

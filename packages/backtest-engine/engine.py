"""Pure-Python/NumPy vectorised backtester."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from uuid import uuid4
from typing import Optional
import numpy as np


@dataclass
class BacktestConfig:
    symbol: str
    strategy_name: str
    start_date: str          # ISO date "YYYY-MM-DD"
    end_date: str            # ISO date "YYYY-MM-DD"
    initial_capital: float   # e.g. 100_000
    position_sizing: str     # "fixed" | "pct_equity" | "kelly"
    commission_pct: float    # e.g. 0.001 for 0.1%
    fixed_position_size: float = 10_000.0   # used when position_sizing == "fixed"
    pct_equity_size: float = 0.10           # 10% of equity per trade
    atr_stop_multiplier: Optional[float] = None  # None = no stop loss


def _ts_to_date(ts_ms: int) -> str:
    """Convert Unix ms to ISO date string."""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _compute_shares(config: BacktestConfig, equity: float, price: float) -> float:
    """Compute number of shares/units to buy."""
    if price <= 0:
        return 0.0
    if config.position_sizing == "fixed":
        return config.fixed_position_size / price
    elif config.position_sizing == "pct_equity":
        return (equity * config.pct_equity_size) / price
    elif config.position_sizing == "kelly":
        # Simplified half-Kelly: assume 55% win rate, 1.5:1 reward/risk
        edge = 0.55 - (0.45 / 1.5)
        kelly_fraction = max(0.0, min(0.25, edge / (1 / 1.5)))  # cap at 25%
        return (equity * kelly_fraction * 0.5) / price  # half-Kelly
    return 0.0


def _close_trade(
    entry_price: float,
    exit_price: float,
    shares: float,
    entry_date: str,
    exit_date: str,
    entry_idx: int,
    exit_idx: int,
    commission_pct: float,
) -> tuple[float, dict]:
    """Compute PnL and create trade dict. Returns (pnl_net, trade_dict)."""
    gross_pnl = (exit_price - entry_price) * shares
    entry_commission = entry_price * shares * commission_pct
    exit_commission = exit_price * shares * commission_pct
    net_pnl = gross_pnl - entry_commission - exit_commission

    pnl_pct = net_pnl / (entry_price * shares) * 100 if entry_price > 0 and shares > 0 else 0.0
    duration_days = exit_idx - entry_idx

    trade = {
        "entryDate": entry_date,
        "exitDate": exit_date,
        "direction": "LONG",
        "entryPrice": round(entry_price, 4),
        "exitPrice": round(exit_price, 4),
        "pnl": round(net_pnl, 2),
        "pnlPct": round(pnl_pct, 4),
        "_duration_bars": duration_days,
    }
    return net_pnl, trade


def _compute_metrics(
    config: BacktestConfig,
    trades: list[dict],
    equity_curve: list[dict],
    final_equity: float,
) -> dict:
    """Compute all performance metrics and return BacktestResult dict."""
    initial_capital = config.initial_capital

    # Total return
    total_return = (final_equity - initial_capital) / initial_capital * 100

    # CAGR — use actual calendar span when dates are available
    n_bars = len(equity_curve)
    try:
        from datetime import date as _date
        _start = _date.fromisoformat(config.start_date)
        _end   = _date.fromisoformat(config.end_date)
        years = max((_end - _start).days / 365.25, n_bars / 252.0)
    except (ValueError, AttributeError):
        years = n_bars / 252.0 if n_bars > 0 else 1.0
    years = years if years > 0 else 1.0
    if years > 0 and initial_capital > 0:
        cagr = (final_equity / initial_capital) ** (1.0 / years) - 1
    else:
        cagr = 0.0

    # Daily returns from equity curve
    values = np.array([pt["value"] for pt in equity_curve], dtype=np.float64)
    if len(values) > 1:
        daily_returns = np.diff(values) / values[:-1]
        # Filter out NaN/Inf
        daily_returns = daily_returns[np.isfinite(daily_returns)]
    else:
        daily_returns = np.array([], dtype=np.float64)

    # Sharpe ratio (annualised, risk-free = 0)
    if len(daily_returns) > 1:
        std_all = np.std(daily_returns, ddof=1)
        if std_all > 0:
            sharpe = float(np.mean(daily_returns) / std_all * np.sqrt(252))
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    # Sortino ratio (annualised, downside deviation)
    if len(daily_returns) > 1:
        neg_returns = daily_returns[daily_returns < 0]
        if len(neg_returns) > 0:
            downside_std = np.std(neg_returns, ddof=1)
            if downside_std > 0:
                sortino = float(np.mean(daily_returns) / downside_std * np.sqrt(252))
            else:
                sortino = 0.0
        else:
            # No negative returns
            sortino = float(np.mean(daily_returns) * np.sqrt(252)) if np.mean(daily_returns) > 0 else 0.0
    else:
        sortino = 0.0

    # Max drawdown
    if len(values) > 0:
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            if peak > 0:
                dd = (v - peak) / peak
                if dd < max_dd:
                    max_dd = dd
        max_drawdown = round(max_dd * 100, 4)
    else:
        max_drawdown = 0.0

    # Drawdown curve
    drawdown_curve = []
    if len(values) > 0:
        peak = values[0]
        for i, pt in enumerate(equity_curve):
            v = pt["value"]
            if v > peak:
                peak = v
            dd_pct = ((v - peak) / peak * 100) if peak > 0 else 0.0
            drawdown_curve.append({"timestamp": pt["timestamp"], "value": round(dd_pct, 4)})

    # Win rate
    n_trades = len(trades)
    if n_trades > 0:
        winners = sum(1 for t in trades if t["pnl"] > 0)
        win_rate = winners / n_trades
    else:
        win_rate = 0.0

    # Profit factor
    gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = 999.0  # no losses, return sentinel value
    else:
        profit_factor = 0.0

    # Average trade duration (in days/bars)
    if n_trades > 0:
        avg_trade_duration = float(np.mean([t["_duration_bars"] for t in trades]))
    else:
        avg_trade_duration = 0.0

    # Clean up internal fields from trades
    clean_trades = []
    for t in trades:
        clean_t = {k: v for k, v in t.items() if not k.startswith("_")}
        clean_trades.append(clean_t)

    return {
        "id": str(uuid4()),
        "symbol": config.symbol,
        "strategyName": config.strategy_name,
        "startDate": config.start_date,
        "endDate": config.end_date,
        "totalReturn": round(total_return, 4),
        "cagr": round(cagr, 4),
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "maxDrawdown": round(max_drawdown, 4),
        "winRate": round(win_rate, 4),
        "profitFactor": round(profit_factor, 4),
        "avgTradeDuration": round(avg_trade_duration, 2),
        "equityCurve": equity_curve,
        "drawdownCurve": drawdown_curve,
        "trades": clean_trades,
    }


def run_backtest(
    config: BacktestConfig,
    timestamps: np.ndarray,   # Unix ms, shape (N,)
    closes: np.ndarray,       # float64, shape (N,)
    highs: np.ndarray,
    lows: np.ndarray,
    entry_signals: np.ndarray,  # bool, shape (N,) — True on bar where we enter
    exit_signals: np.ndarray,   # bool, shape (N,) — True on bar where we exit
    atrs: Optional[np.ndarray] = None,  # float64, shape (N,), required if atr_stop_multiplier set
) -> dict:
    """
    Run a vectorised backtest. Returns a BacktestResult dict.

    Strategy rules:
    - Enter LONG when entry_signal[i] is True (at close price of bar i)
    - Exit when exit_signal[i] is True, OR when stop-loss breached (low[i] < stop_price)
    - Only one position at a time
    - Commission applied at both entry and exit
    """
    equity = config.initial_capital
    equity_curve = []       # list of {"timestamp": ms, "value": equity}
    trades = []

    in_position = False
    entry_price = 0.0
    entry_date = ""
    entry_idx = 0
    stop_price = 0.0
    shares = 0.0

    n = len(closes)

    for i in range(n):
        ts = int(timestamps[i])
        price = float(closes[i])

        # Check stop-loss if in position
        if in_position and atrs is not None and config.atr_stop_multiplier is not None:
            if float(lows[i]) < stop_price:
                # Exit at stop price
                exit_price = stop_price
                net_pnl, trade = _close_trade(
                    entry_price, exit_price, shares,
                    entry_date, _ts_to_date(ts),
                    entry_idx, i,
                    config.commission_pct,
                )
                equity += net_pnl
                in_position = False
                trades.append(trade)

        # Check exit signal if still in position
        if in_position and bool(exit_signals[i]):
            exit_price = price
            net_pnl, trade = _close_trade(
                entry_price, exit_price, shares,
                entry_date, _ts_to_date(ts),
                entry_idx, i,
                config.commission_pct,
            )
            equity += net_pnl
            in_position = False
            trades.append(trade)

        # Check entry signal if not in position
        if not in_position and bool(entry_signals[i]):
            shares = _compute_shares(config, equity, price)
            if shares > 0:
                cost = shares * price * (1 + config.commission_pct)
                if cost <= equity:
                    entry_price = price
                    entry_date = _ts_to_date(ts)
                    entry_idx = i
                    in_position = True
                    if atrs is not None and config.atr_stop_multiplier is not None:
                        atr_val = float(atrs[i]) if not np.isnan(atrs[i]) else 0.0
                        stop_price = price - config.atr_stop_multiplier * atr_val
                    else:
                        stop_price = 0.0

        equity_curve.append({"timestamp": ts, "value": round(equity, 2)})

    # Close any open position at end of data
    if in_position and n > 0:
        last_i = n - 1
        last_ts = int(timestamps[last_i])
        exit_price = float(closes[last_i])
        net_pnl, trade = _close_trade(
            entry_price, exit_price, shares,
            entry_date, _ts_to_date(last_ts),
            entry_idx, last_i,
            config.commission_pct,
        )
        equity += net_pnl
        trades.append(trade)
        # Update last equity curve point
        if equity_curve:
            equity_curve[-1]["value"] = round(equity, 2)

    return _compute_metrics(config, trades, equity_curve, equity)

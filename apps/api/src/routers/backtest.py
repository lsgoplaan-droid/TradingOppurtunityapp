"""Backtest API — job submission, status polling, result retrieval."""
import asyncio
from uuid import uuid4
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

# In-memory job store
_jobs: dict[str, dict] = {}


class BacktestRequest(BaseModel):
    symbol: str
    templateId: str    # maps to strategy name
    startDate: str
    endDate: str
    initialCapital: float = 100_000
    positionSizing: str = "pct_equity"
    commissionPct: float = 0.001
    market: str = "US"            # "US" or "INDIA"
    assetClass: str = "EQUITY"    # "EQUITY" or "EQUITY_OPTIONS"
    # Options-specific (only used when assetClass == EQUITY_OPTIONS)
    optionsStrategy: str = "long_call"
    expiryDays: int = 30
    strikeOffsetPct: float = 0.0
    wingWidthPct: float = 0.05


@router.post("/run")
async def submit_backtest(request: BacktestRequest, background_tasks: BackgroundTasks) -> dict:
    """Submit a backtest job. Returns jobId immediately, runs in background."""
    job_id = str(uuid4())
    _jobs[job_id] = {"jobId": job_id, "status": "pending"}
    background_tasks.add_task(_run_backtest_job, job_id, request.model_dump())
    return {"jobId": job_id, "status": "pending"}


@router.get("/status/{job_id}")
async def get_status(job_id: str) -> dict:
    if job_id not in _jobs:
        raise HTTPException(404, f"Job not found: {job_id}")
    return _jobs[job_id]


@router.get("/result/{job_id}")
async def get_result(job_id: str) -> dict:
    if job_id not in _jobs:
        raise HTTPException(404, f"Job not found: {job_id}")
    job = _jobs[job_id]
    if job["status"] != "complete":
        raise HTTPException(400, f"Job not complete: {job['status']}")
    return job.get("result", {})


@router.get("/strategies")
async def list_strategies() -> list[dict]:
    return [
        # Equity strategies
        {"id": "golden_cross",        "name": "Golden Cross",        "description": "EMA50 × EMA200",             "assetClass": "EQUITY"},
        {"id": "rsi_mean_reversion",  "name": "RSI Mean Reversion",  "description": "RSI 30/70 bounce",           "assetClass": "EQUITY"},
        {"id": "macd_trend",          "name": "MACD Trend",          "description": "MACD line × signal",         "assetClass": "EQUITY"},
        {"id": "bollinger_reversion", "name": "Bollinger Reversion", "description": "Touch lower/upper bands",    "assetClass": "EQUITY"},
        # Options strategies
        {"id": "long_call",         "name": "Long Call",         "description": "Buy ATM call, 30-day expiry",          "assetClass": "EQUITY_OPTIONS"},
        {"id": "long_put",          "name": "Long Put",          "description": "Buy ATM put, 30-day expiry",           "assetClass": "EQUITY_OPTIONS"},
        {"id": "straddle",          "name": "Straddle",          "description": "Buy ATM call + put",                   "assetClass": "EQUITY_OPTIONS"},
        {"id": "strangle",          "name": "Strangle",          "description": "Buy OTM call + put (2% strikes)",      "assetClass": "EQUITY_OPTIONS"},
        {"id": "iron_condor",       "name": "Iron Condor",       "description": "Sell OTM call+put spreads",            "assetClass": "EQUITY_OPTIONS"},
        {"id": "covered_call",      "name": "Covered Call",      "description": "Own shares + sell OTM call",           "assetClass": "EQUITY_OPTIONS"},
        {"id": "zero_dte_straddle", "name": "0DTE Straddle",     "description": "ATM call + put, same-day expiry",      "assetClass": "EQUITY_OPTIONS"},
        {"id": "zero_dte_strangle", "name": "0DTE Strangle",     "description": "OTM call + put, same-day expiry (1%)", "assetClass": "EQUITY_OPTIONS"},
    ]


# Map scan template IDs → equity strategy registry keys
_TEMPLATE_TO_STRATEGY: dict[str, str] = {
    "us_eq_golden_cross":        "golden_cross",
    "us_eq_death_cross":         "golden_cross",
    "us_eq_rsi_oversold_bounce": "rsi_mean_reversion",
    "us_eq_macd_bullish_cross":  "macd_trend",
    "us_eq_breakout_volume":     "bollinger_reversion",
    "us_eq_mean_reversion":      "rsi_mean_reversion",
    "us_eq_mtf_uptrend":         "golden_cross",
    "us_eq_mtf_mean_reversion":  "rsi_mean_reversion",
    "us_opt_high_iv_rank":       "long_call",
    "us_opt_low_iv_rank":        "long_call",
    "india_eq_golden_cross":     "golden_cross",
    "india_eq_rsi_oversold":     "rsi_mean_reversion",
    "india_eq_momentum":         "macd_trend",
    "india_eq_breakout":         "bollinger_reversion",
    "india_eq_mtf_uptrend":      "golden_cross",
    "india_fo_high_iv_rank":     "iron_condor",
    "india_fo_pcr_extreme_bearish": "long_put",
    "india_fo_max_pain_proximity":  "straddle",
    "india_fo_gamma_play":          "long_call",
}


def _resolve_strategy(template_id: str) -> str:
    if template_id in _TEMPLATE_TO_STRATEGY:
        return _TEMPLATE_TO_STRATEGY[template_id]
    from packages.backtest_engine.strategies import STRATEGY_REGISTRY
    from packages.backtest_engine.options_backtest import OPTIONS_STRATEGY_REGISTRY
    if template_id in STRATEGY_REGISTRY or template_id in OPTIONS_STRATEGY_REGISTRY:
        return template_id
    return "golden_cross"


async def _run_backtest_job(job_id: str, request: dict) -> None:
    """Background task — dispatches to equity or options backtest engine."""
    from packages.data_adapters.yfinance_adapter import YFinanceAdapter
    import numpy as np

    _jobs[job_id]["status"] = "running"
    try:
        market = request.get("market", "US").upper()
        asset_class = request.get("assetClass", "EQUITY").upper()
        adapter = YFinanceAdapter(market=market)

        candles = await adapter.get_candles(
            request["symbol"], "1day", request["startDate"], request["endDate"]
        )
        if len(candles) < 50:
            raise ValueError(f"Insufficient data: {len(candles)} bars")

        closes     = np.array([c["close"]     for c in candles], dtype=np.float64)
        highs      = np.array([c["high"]      for c in candles], dtype=np.float64)
        lows       = np.array([c["low"]       for c in candles], dtype=np.float64)
        timestamps = np.array([c["timestamp"] for c in candles], dtype=np.float64)

        if asset_class == "EQUITY_OPTIONS":
            from packages.backtest_engine.options_backtest import (
                OptionsBacktestConfig, run_options_backtest, OPTIONS_STRATEGY_REGISTRY
            )
            opts_strategy = request.get("optionsStrategy", "long_call")
            # Fall back: if template maps to an equity strategy, default to long_call
            if opts_strategy not in OPTIONS_STRATEGY_REGISTRY:
                resolved = _resolve_strategy(request.get("templateId", "long_call"))
                opts_strategy = resolved if resolved in OPTIONS_STRATEGY_REGISTRY else "long_call"

            opts_config = OptionsBacktestConfig(
                symbol=request["symbol"],
                strategy_name=opts_strategy,
                start_date=request["startDate"],
                end_date=request["endDate"],
                initial_capital=float(request.get("initialCapital", 100_000)),
                commission_pct=float(request.get("commissionPct", 0.001)),
                expiry_days=int(request.get("expiryDays", 30)),
                strike_offset_pct=float(request.get("strikeOffsetPct", 0.0)),
                wing_width_pct=float(request.get("wingWidthPct", 0.05)),
            )
            result = run_options_backtest(opts_config, timestamps, closes, highs, lows)
        else:
            from packages.backtest_engine.engine import BacktestConfig, run_backtest
            from packages.backtest_engine.strategies import STRATEGY_REGISTRY

            strategy_key = _resolve_strategy(request.get("templateId", "golden_cross"))
            # If key resolved to an options strategy, fallback to golden_cross
            if strategy_key not in STRATEGY_REGISTRY:
                strategy_key = "golden_cross"
            strategy_fn = STRATEGY_REGISTRY[strategy_key]
            entry_signals, exit_signals = strategy_fn(closes, highs, lows)

            config = BacktestConfig(
                symbol=request["symbol"],
                strategy_name=request.get("templateId", strategy_key),
                start_date=request["startDate"],
                end_date=request["endDate"],
                initial_capital=float(request.get("initialCapital", 100_000)),
                position_sizing=request.get("positionSizing", "pct_equity"),
                commission_pct=float(request.get("commissionPct", 0.001)),
            )
            result = run_backtest(config, timestamps, closes, highs, lows, entry_signals, exit_signals)

        _jobs[job_id]["status"] = "complete"
        _jobs[job_id]["result"] = result
        _jobs[job_id]["resultId"] = result["id"]
    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)

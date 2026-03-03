"""Orchestrates backtest runs: fetch data -> build signals -> run engine -> store results."""
import asyncio
from datetime import datetime, date
from uuid import uuid4
import numpy as np

from packages.data_adapters.base import DataAdapter, StorageService
from packages.backtest_engine.engine import BacktestConfig, run_backtest
from packages.backtest_engine.strategies import STRATEGY_REGISTRY


class BacktestService:
    def __init__(self, data_adapter: DataAdapter, storage: StorageService):
        self.adapter = data_adapter
        self.storage = storage

    async def run(self, job_id: str, request: dict) -> None:
        """
        Run a backtest job. Updates storage status throughout.

        request keys: symbol, templateId (maps to strategy name), startDate, endDate,
                     initialCapital, positionSizing, commissionPct
        """
        await self.storage.update_backtest_status(job_id, "running")
        try:
            # 1. Fetch candles
            candles = await self.adapter.get_candles(
                request["symbol"],
                "1day",
                request["startDate"],
                request["endDate"],
            )
            if len(candles) < 210:
                raise ValueError(f"Insufficient data: {len(candles)} bars (need >= 210)")

            # 2. Build NumPy arrays
            closes     = np.array([c["close"]     for c in candles], dtype=np.float64)
            highs      = np.array([c["high"]      for c in candles], dtype=np.float64)
            lows       = np.array([c["low"]       for c in candles], dtype=np.float64)
            timestamps = np.array([c["timestamp"] for c in candles], dtype=np.float64)

            # 3. Get strategy signals
            # Use the template ID as strategy key; fall back to golden_cross if not found
            # (scan template IDs like "us_eq_golden_cross" are resolved by the caller;
            # if passed through directly, default to golden_cross rather than crashing)
            template_id = request.get("templateId", "golden_cross")
            strategy_fn = STRATEGY_REGISTRY.get(template_id) or STRATEGY_REGISTRY["golden_cross"]
            entry_signals, exit_signals = strategy_fn(closes, highs, lows)

            # 4. Build config and run engine
            config = BacktestConfig(
                symbol=request["symbol"],
                strategy_name=template_id,
                start_date=request["startDate"],
                end_date=request["endDate"],
                initial_capital=float(request.get("initialCapital", 100_000)),
                position_sizing=request.get("positionSizing", "pct_equity"),
                commission_pct=float(request.get("commissionPct", 0.001)),
            )
            result = run_backtest(config, timestamps, closes, highs, lows, entry_signals, exit_signals)

            # 5. Store result
            await self.storage.save_backtest_result(job_id, result)
            await self.storage.update_backtest_status(job_id, "complete", result_id=result["id"])
        except Exception as e:
            await self.storage.update_backtest_status(job_id, "failed", error=str(e))
            raise

"""
Multi-Timeframe (MTF) scan engine — FR-008.

A signal is emitted only when conditions are satisfied on ALL configured
timeframes simultaneously.  Each timeframe block has its own indicator
conditions; the overall strength score is the average pass-rate across
all timeframe blocks.
"""
import asyncio
import json
import pathlib
import time
from typing import Optional
from uuid import uuid4

import numpy as np
from pydantic import BaseModel

from packages.data_adapters.base import DataAdapter
from packages.scan_engine.scanner import (
    _compute_indicators,
    _compute_support_resistance,
    _compute_exit_targets,
    _evaluate_condition,
    _safe_last,
)

TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"


class MTFTimeframeBlock(BaseModel):
    """Conditions for one timeframe within an MTF rule."""
    timeframe: str          # e.g. "1week", "1day"
    min_candles: int
    label: str              # e.g. "Weekly Trend", "Daily Entry"
    conditions: list[dict]


class MTFScanRule(BaseModel):
    id: str
    name: str
    description: str
    market: str
    asset_class: str
    signal_name: str
    template_id: str
    timeframe_conditions: list[MTFTimeframeBlock]
    # satisfy_all: if True (default), all blocks must pass
    satisfy_all: bool = True


def load_mtf_template(template_id: str) -> MTFScanRule:
    path = TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"MTF template not found: {template_id}")
    data = json.loads(path.read_text())
    if data.get("type") != "mtf":
        raise ValueError(f"Template {template_id} is not an MTF template")
    return MTFScanRule(**data)


class MTFScanEngine:
    """
    Evaluates MTFScanRule conditions across multiple timeframes.

    For each symbol:
    1. Fetch candle data for every required timeframe in parallel.
    2. Compute indicators independently per timeframe.
    3. Evaluate each block's conditions.
    4. Emit a result only if all blocks pass (or satisfy_all=False for partial).
    """

    def __init__(self, data_adapter: DataAdapter):
        self._adapter = data_adapter

    async def run(self, rule: MTFScanRule, symbols: list[str]) -> list[dict]:
        """Run rule against all symbols concurrently."""
        tasks = [self._evaluate(rule, symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    async def _evaluate(self, rule: MTFScanRule, symbol: str) -> Optional[dict]:
        try:
            from datetime import date, timedelta
            today = date.today()
            # Fetch enough history for weekly indicators (200 weeks ≈ 4 years)
            from_date = (today - timedelta(days=365 * 4)).isoformat()
            to_date = today.isoformat()

            # Fetch all required timeframes in parallel
            fetch_tasks = [
                self._adapter.get_candles(symbol, block.timeframe, from_date, to_date)
                for block in rule.timeframe_conditions
            ]
            all_candles = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            # Evaluate each timeframe block
            block_results: list[dict] = []
            all_passed = True

            for block, candles in zip(rule.timeframe_conditions, all_candles):
                if isinstance(candles, Exception) or not candles \
                        or len(candles) < block.min_candles:
                    all_passed = False
                    block_results.append({
                        "label": block.label,
                        "timeframe": block.timeframe,
                        "passed": False,
                        "conditions_met": 0,
                        "total_conditions": len(block.conditions),
                    })
                    continue

                indicators = _compute_indicators(candles)
                met = sum(
                    1 for cond in block.conditions
                    if _evaluate_condition(cond, indicators)
                )
                passed = met == len(block.conditions)
                if not passed:
                    all_passed = False

                block_results.append({
                    "label": block.label,
                    "timeframe": block.timeframe,
                    "passed": passed,
                    "conditions_met": met,
                    "total_conditions": len(block.conditions),
                    "_indicators": indicators,
                    "_candles": candles,
                })

            should_emit = all_passed if rule.satisfy_all else any(
                b["passed"] for b in block_results
            )
            if not should_emit:
                return None

            # Overall strength = average pass-rate across all blocks
            total_met = sum(b["conditions_met"] for b in block_results)
            total_conds = sum(b["total_conditions"] for b in block_results)
            strength = (total_met / total_conds * 100) if total_conds > 0 else 0.0

            # Use daily block for entry price / S/R / exit targets
            # (fall back to the last block if no 1day block)
            daily_block = next(
                (b for b in block_results if b.get("timeframe") == "1day" and "_candles" in b),
                next((b for b in block_results if "_candles" in b), None)
            )

            entry_price = float("nan")
            sr: dict = {"support": [], "resistance": []}
            exit_targets: dict = {"stopLoss": None, "targetPrice": None, "riskReward": None}
            chart_candles: list = []
            indicator_values: dict = {}

            if daily_block:
                candles_d = daily_block["_candles"]
                inds_d = daily_block["_indicators"]
                entry_price = float(inds_d.get("close", float("nan")))
                sr = _compute_support_resistance(candles_d, entry_price)
                atr_val = inds_d.get("atr", float("nan"))
                exit_targets = _compute_exit_targets(
                    entry_price, sr["support"], sr["resistance"], atr_val
                )
                chart_candles = [
                    {"t": c["timestamp"], "c": round(c["close"], 4)}
                    for c in candles_d[-60:]
                ]
                indicator_values = {
                    k: v for k, v in inds_d.items()
                    if not k.startswith("_") and isinstance(v, (int, float)) and not np.isnan(v)
                }

            triggered_timeframes = [
                f"{b['label']} ({b['timeframe']})"
                for b in block_results if b["passed"]
            ]

            return {
                "id": str(uuid4()),
                "symbol": symbol,
                "market": rule.market,
                "assetClass": rule.asset_class,
                "signalName": rule.signal_name,
                "templateId": rule.template_id,
                "timeframe": "MTF",
                "strengthScore": round(strength, 2),
                "timestamp": int(time.time() * 1000),
                "indicatorValues": indicator_values,
                "entryPrice": round(entry_price, 4) if not np.isnan(entry_price) else None,
                "stopLoss": exit_targets["stopLoss"],
                "targetPrice": exit_targets["targetPrice"],
                "riskReward": exit_targets["riskReward"],
                "supportLevels": sr["support"],
                "resistanceLevels": sr["resistance"],
                "recentCandles": chart_candles,
                "triggeredTimeframes": triggered_timeframes,
                "mtfBlocks": [
                    {"label": b["label"], "timeframe": b["timeframe"], "passed": b["passed"],
                     "score": f"{b['conditions_met']}/{b['total_conditions']}"}
                    for b in block_results
                ],
            }

        except Exception:
            return None

"""FastAPI router for scan engine endpoints."""
import asyncio
from collections import Counter
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from packages.scan_engine.scanner import ScanEngine, ScanRule
from packages.scan_engine.template_loader import list_templates, load_template, load_mtf_template
from packages.scan_engine.mtf_scanner import MTFScanEngine
from packages.data_adapters.yfinance_adapter import YFinanceAdapter

router = APIRouter(prefix="/api/scan", tags=["scan"])

# Default US equity symbol universe — S&P 500 top 20 by market cap
DEFAULT_US_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK-B", "JPM", "V",
    "MA", "UNH", "XOM", "HD", "PG",
    "JNJ", "COST", "AVGO", "MRK", "ABBV",
]

# In-memory result cache (last N scan results)
_result_cache: list[dict] = []
_MAX_CACHE_SIZE = 500


class ScanRunRequest(BaseModel):
    templateId: str
    symbols: Optional[list[str]] = None  # defaults to DEFAULT_US_SYMBOLS


class MultiScanRunRequest(BaseModel):
    templateIds: list[str]
    symbols: Optional[list[str]] = None  # defaults to DEFAULT_US_SYMBOLS


def _get_adapter():
    """Return a YFinanceAdapter for US market data."""
    return YFinanceAdapter(market="US")


@router.get("/templates")
async def get_templates() -> list[dict]:
    """Return all available scan templates with summary metadata."""
    try:
        return list_templates()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/run")
async def run_scan(request: ScanRunRequest) -> list[dict]:
    """
    Run a scan template against a list of symbols.

    Uses mock data adapter when no live adapter is configured.
    Results are cached in-memory for retrieval via GET /api/scan/results.
    """
    global _result_cache

    try:
        rule: ScanRule = load_template(request.templateId)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    symbols = request.symbols if request.symbols else DEFAULT_US_SYMBOLS

    adapter = _get_adapter()
    engine = ScanEngine(adapter)

    try:
        results = await engine.run(rule, symbols)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scan failed: {exc}")

    # Cache results (keep most recent up to _MAX_CACHE_SIZE)
    _result_cache.extend(results)
    if len(_result_cache) > _MAX_CACHE_SIZE:
        _result_cache = _result_cache[-_MAX_CACHE_SIZE:]

    return results


@router.post("/run-multi")
async def run_multi_scan(request: MultiScanRunRequest) -> list[dict]:
    """
    Run multiple scan templates in parallel against the same symbol list.

    Results are annotated with `signalCount` (how many templates fired for that
    symbol) and sorted so high-confluence symbols appear first.
    """
    global _result_cache

    symbols = request.symbols if request.symbols else DEFAULT_US_SYMBOLS
    adapter = _get_adapter()
    engine = ScanEngine(adapter)

    # Load all requested templates (skip missing or MTF templates silently)
    tasks = []
    for tid in request.templateIds:
        try:
            rule = load_template(tid)  # raises ValueError for MTF templates
            tasks.append(engine.run(rule, symbols))
        except (FileNotFoundError, ValueError):
            pass

    if not tasks:
        raise HTTPException(status_code=404, detail="No valid templates found")

    nested = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: list[dict] = []
    for batch in nested:
        if isinstance(batch, list):
            all_results.extend(batch)

    # Annotate each result with how many distinct signals fired for its symbol
    symbol_signal_count = Counter(r["symbol"] for r in all_results)
    for r in all_results:
        r["signalCount"] = symbol_signal_count[r["symbol"]]

    # Sort: multi-signal symbols first, then by strength descending
    all_results.sort(key=lambda r: (-r["signalCount"], -r.get("strengthScore", 0)))

    _result_cache.extend(all_results)
    if len(_result_cache) > _MAX_CACHE_SIZE:
        _result_cache = _result_cache[-_MAX_CACHE_SIZE:]

    return all_results


@router.post("/run-mtf")
async def run_mtf_scan(request: ScanRunRequest) -> list[dict]:
    """
    Run a single MTF template against the symbol list.
    Returns results annotated with triggeredTimeframes and mtfBlocks.
    """
    global _result_cache
    try:
        rule = load_mtf_template(request.templateId)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    symbols = request.symbols if request.symbols else DEFAULT_US_SYMBOLS
    engine = MTFScanEngine(_get_adapter())

    try:
        results = await engine.run(rule, symbols)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MTF scan failed: {exc}")

    _result_cache.extend(results)
    if len(_result_cache) > _MAX_CACHE_SIZE:
        _result_cache = _result_cache[-_MAX_CACHE_SIZE:]

    return results


@router.get("/results")
async def get_results(limit: int = 50) -> list[dict]:
    """Return the last N scan results from the in-memory cache."""
    if limit < 1:
        limit = 1
    return _result_cache[-limit:]

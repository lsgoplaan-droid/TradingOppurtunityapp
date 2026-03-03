"""FastAPI router for India-specific scan engine endpoints (NSE Equity + F&O)."""
import asyncio
from collections import Counter
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from packages.scan_engine.template_loader import list_templates, load_template, load_mtf_template
from packages.scan_engine.india_scanner import IndiaScanEngine
from packages.scan_engine.mtf_scanner import MTFScanEngine
from packages.data_adapters.yfinance_adapter import YFinanceAdapter

router = APIRouter(prefix="/api/india-scan", tags=["india-scan"])

# Default India (NSE) symbol universe — Nifty 50 top 20 by market cap
DEFAULT_INDIA_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
    "BHARTIARTL", "SBIN", "WIPRO", "BAJFINANCE", "LT",
    "ASIANPAINT", "MARUTI", "KOTAKBANK", "AXISBANK", "ULTRACEMCO",
    "TITAN", "NESTLEIND", "SUNPHARMA", "HCLTECH", "ONGC",
]


class IndiaScanRunRequest(BaseModel):
    templateId: str
    symbols: Optional[list[str]] = None  # defaults to DEFAULT_INDIA_SYMBOLS


class IndiaMultiScanRunRequest(BaseModel):
    templateIds: list[str]
    symbols: Optional[list[str]] = None  # defaults to DEFAULT_INDIA_SYMBOLS


def _get_india_adapter():
    """Return a YFinanceAdapter for India (NSE) market data."""
    return YFinanceAdapter(market="INDIA")


@router.get("/templates")
async def get_india_templates() -> list[dict]:
    """Return only India market templates."""
    try:
        all_templates = list_templates()
        return [t for t in all_templates if t.get("market") == "INDIA"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/run-multi")
async def run_india_multi_scan(request: IndiaMultiScanRunRequest) -> list[dict]:
    """Run multiple India scan templates in parallel; annotates signalCount."""
    symbols = request.symbols if request.symbols else DEFAULT_INDIA_SYMBOLS
    adapter = _get_india_adapter()
    engine = IndiaScanEngine(adapter)

    tasks = []
    for tid in request.templateIds:
        try:
            rule = load_template(tid)
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

    symbol_signal_count = Counter(r["symbol"] for r in all_results)
    for r in all_results:
        r["signalCount"] = symbol_signal_count[r["symbol"]]

    all_results.sort(key=lambda r: (-r["signalCount"], -r.get("strengthScore", 0)))
    return all_results


@router.post("/run-mtf")
async def run_india_mtf_scan(request: IndiaScanRunRequest) -> list[dict]:
    """Run a single India MTF template against the symbol list."""
    try:
        rule = load_mtf_template(request.templateId)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    symbols = request.symbols if request.symbols else DEFAULT_INDIA_SYMBOLS
    engine = MTFScanEngine(_get_india_adapter())

    try:
        results = await engine.run(rule, symbols)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"India MTF scan failed: {exc}")

    return results


@router.post("/run")
async def run_india_scan(request: IndiaScanRunRequest) -> list[dict]:
    """
    Run an India scan template against a list of NSE symbols.

    Uses mock data adapter when no live adapter is configured.
    Supports both EQUITY and EQUITY_OPTIONS templates.
    """
    try:
        rule = load_template(request.templateId)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    symbols = request.symbols if request.symbols else DEFAULT_INDIA_SYMBOLS

    adapter = _get_india_adapter()
    engine = IndiaScanEngine(adapter)

    try:
        results = await engine.run(rule, symbols)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"India scan failed: {exc}")

    return results

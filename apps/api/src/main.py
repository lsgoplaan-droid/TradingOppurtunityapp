from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.src.routers.scan import router as scan_router
from apps.api.src.routers.india_scan import router as india_scan_router
from apps.api.src.routers.backtest import router as backtest_router
from apps.api.src.routers.watchlist import router as watchlist_router

app = FastAPI(
    title="TradingOppurtunityApp API",
    description="Trading opportunity scanning and backtesting API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan_router)
app.include_router(india_scan_router)
app.include_router(backtest_router)
app.include_router(watchlist_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

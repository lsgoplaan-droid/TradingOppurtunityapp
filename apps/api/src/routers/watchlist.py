"""In-memory watchlist CRUD API."""
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])

_watchlists: dict[str, dict] = {}


class WatchlistCreate(BaseModel):
    name: str
    symbols: list[str]
    market: str = "US"  # "US" | "INDIA" | "ALL"


@router.get("")
async def list_watchlists() -> list[dict]:
    return list(_watchlists.values())


@router.post("")
async def create_watchlist(body: WatchlistCreate) -> dict:
    wl_id = str(uuid4())
    wl = {"id": wl_id, "name": body.name, "symbols": body.symbols, "market": body.market}
    _watchlists[wl_id] = wl
    return wl


@router.get("/{watchlist_id}")
async def get_watchlist(watchlist_id: str) -> dict:
    if watchlist_id not in _watchlists:
        raise HTTPException(404, f"Watchlist not found: {watchlist_id}")
    return _watchlists[watchlist_id]


@router.delete("/{watchlist_id}")
async def delete_watchlist(watchlist_id: str) -> dict:
    if watchlist_id not in _watchlists:
        raise HTTPException(404, f"Watchlist not found: {watchlist_id}")
    _watchlists.pop(watchlist_id)
    return {"deleted": watchlist_id}

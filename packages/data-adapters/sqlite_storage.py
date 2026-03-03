"""SQLite-backed StorageService for local development."""
import json
import sqlite3
import time
import pathlib
from typing import Optional
from packages.data_adapters.base import StorageService


class SQLiteStorageService(StorageService):
    def __init__(self, db_path: str = "trading_app.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS scan_results (
                    id TEXT PRIMARY KEY,
                    symbol TEXT,
                    market TEXT,
                    asset_class TEXT,
                    data TEXT,
                    created_at REAL
                );
                CREATE TABLE IF NOT EXISTS backtest_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT,
                    result_id TEXT,
                    error TEXT,
                    result_data TEXT,
                    created_at REAL,
                    updated_at REAL
                );
                CREATE TABLE IF NOT EXISTS watchlists (
                    id TEXT PRIMARY KEY,
                    data TEXT,
                    updated_at REAL
                );
                CREATE TABLE IF NOT EXISTS iv_history (
                    symbol TEXT,
                    expiry TEXT,
                    date TEXT,
                    iv REAL,
                    PRIMARY KEY (symbol, expiry, date)
                );
            """)
            conn.commit()
        finally:
            conn.close()

    # -- Scan results ----------------------------------------------------------

    async def save_scan_result(self, result: dict) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO scan_results (id, symbol, market, asset_class, data, created_at) VALUES (?,?,?,?,?,?)",
                (result["id"], result["symbol"], result["market"], result["assetClass"],
                 json.dumps(result), time.time())
            )
            conn.commit()
        finally:
            conn.close()

    async def get_scan_results(self, limit=100, asset_class=None, market=None) -> list[dict]:
        conn = self._get_conn()
        try:
            q = "SELECT data FROM scan_results WHERE 1=1"
            params = []
            if asset_class:
                q += " AND asset_class = ?"; params.append(asset_class)
            if market:
                q += " AND market = ?"; params.append(market)
            q += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(q, params).fetchall()
            return [json.loads(r[0]) for r in rows]
        finally:
            conn.close()

    # -- Backtest results ------------------------------------------------------

    async def save_backtest_result(self, job_id: str, result: dict) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE backtest_jobs SET result_data=?, result_id=?, updated_at=? WHERE job_id=?",
                (json.dumps(result), result["id"], time.time(), job_id)
            )
            conn.commit()
        finally:
            conn.close()

    async def get_backtest_result(self, job_id: str) -> Optional[dict]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT result_data FROM backtest_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return None
        finally:
            conn.close()

    async def update_backtest_status(
        self,
        job_id: str,
        status: str,
        error: Optional[str] = None,
        result_id: Optional[str] = None,
    ) -> None:
        conn = self._get_conn()
        try:
            # Upsert
            existing = conn.execute(
                "SELECT job_id FROM backtest_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            now = time.time()
            if existing:
                conn.execute(
                    "UPDATE backtest_jobs SET status=?, error=?, result_id=?, updated_at=? WHERE job_id=?",
                    (status, error, result_id, now, job_id)
                )
            else:
                conn.execute(
                    "INSERT INTO backtest_jobs (job_id, status, error, result_id, result_data, created_at, updated_at) VALUES (?,?,?,?,NULL,?,?)",
                    (job_id, status, error, result_id, now, now)
                )
            conn.commit()
        finally:
            conn.close()

    # -- Watchlists ------------------------------------------------------------

    async def save_watchlist(self, watchlist: dict) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO watchlists (id, data, updated_at) VALUES (?,?,?)",
                (watchlist["id"], json.dumps(watchlist), time.time())
            )
            conn.commit()
        finally:
            conn.close()

    async def get_watchlists(self) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT data FROM watchlists ORDER BY updated_at DESC"
            ).fetchall()
            return [json.loads(r[0]) for r in rows]
        finally:
            conn.close()

    async def get_watchlist(self, watchlist_id: str) -> Optional[dict]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT data FROM watchlists WHERE id=?", (watchlist_id,)
            ).fetchone()
            return json.loads(row[0]) if row else None
        finally:
            conn.close()

    # -- IV history ------------------------------------------------------------

    async def save_iv_record(self, symbol: str, expiry: str, date: str, iv: float) -> None:
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO iv_history (symbol, expiry, date, iv) VALUES (?,?,?,?)",
                (symbol, expiry, date, iv)
            )
            conn.commit()
        finally:
            conn.close()

    async def get_iv_history(self, symbol: str, expiry: str, days: int = 252) -> list[dict]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT date, iv FROM iv_history WHERE symbol=? AND expiry=? ORDER BY date DESC LIMIT ?",
                (symbol, expiry, days)
            ).fetchall()
            return [{"date": r[0], "iv": r[1]} for r in rows]
        finally:
            conn.close()

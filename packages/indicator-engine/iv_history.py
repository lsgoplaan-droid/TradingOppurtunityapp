"""
IV history store — persists daily IV readings for IVR/IVP computation.
Uses SQLite locally; schema compatible with DynamoDB migration in Phase 7.
"""
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional


class IVHistoryStore:
    """Stores and retrieves historical IV data for IVR/IVP computation."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "iv_history.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS iv_history (
                    symbol TEXT NOT NULL,
                    expiry TEXT NOT NULL,
                    date TEXT NOT NULL,
                    iv REAL NOT NULL,
                    PRIMARY KEY (symbol, expiry, date)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_date ON iv_history(symbol, date)")
            conn.commit()
        finally:
            conn.close()

    def save_iv(self, symbol: str, expiry: str, date: str, iv: float) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO iv_history (symbol, expiry, date, iv) VALUES (?, ?, ?, ?)",
                (symbol.upper(), expiry, date, iv),
            )
            conn.commit()
        finally:
            conn.close()

    def get_iv_history(
        self, symbol: str, expiry: str = "ANY", days: int = 252
    ) -> list[float]:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        conn = sqlite3.connect(self._db_path)
        try:
            if expiry == "ANY":
                rows = conn.execute(
                    "SELECT iv FROM iv_history WHERE symbol=? AND date>=? ORDER BY date",
                    (symbol.upper(), cutoff),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT iv FROM iv_history WHERE symbol=? AND expiry=? AND date>=? ORDER BY date",
                    (symbol.upper(), expiry, cutoff),
                ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows]

    def get_current_iv(self, symbol: str, expiry: str = "ANY") -> Optional[float]:
        """Returns most recent IV record for symbol."""
        conn = sqlite3.connect(self._db_path)
        try:
            if expiry == "ANY":
                row = conn.execute(
                    "SELECT iv FROM iv_history WHERE symbol=? ORDER BY date DESC LIMIT 1",
                    (symbol.upper(),),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT iv FROM iv_history WHERE symbol=? AND expiry=? ORDER BY date DESC LIMIT 1",
                    (symbol.upper(), expiry),
                ).fetchone()
        finally:
            conn.close()
        return row[0] if row else None

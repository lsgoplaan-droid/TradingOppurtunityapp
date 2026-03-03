"""Tests for IVHistoryStore."""
import pytest
import tempfile
import os
from datetime import datetime, timedelta
from packages.indicator_engine.iv_history import IVHistoryStore

# Use dates within the last 30 days so the days= cutoff always includes them.
_TODAY = datetime.now().strftime("%Y-%m-%d")
_YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
_EXPIRY = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")


def test_save_and_retrieve_iv():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_iv.db")
        store = IVHistoryStore(db_path=db_path)
        store.save_iv("NIFTY", _EXPIRY, _YESTERDAY, 0.18)
        store.save_iv("NIFTY", _EXPIRY, _TODAY, 0.20)
        history = store.get_iv_history("NIFTY", _EXPIRY, days=365)
        assert len(history) == 2
        assert 0.18 in history
        assert 0.20 in history


def test_get_current_iv():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_iv.db")
        store = IVHistoryStore(db_path=db_path)
        store.save_iv("AAPL", _EXPIRY, _YESTERDAY, 0.25)
        store.save_iv("AAPL", _EXPIRY, _TODAY, 0.30)
        iv = store.get_current_iv("AAPL", _EXPIRY)
        assert iv == 0.30


def test_empty_history_returns_empty_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_iv.db")
        store = IVHistoryStore(db_path=db_path)
        history = store.get_iv_history("UNKNOWN", days=365)
        assert history == []

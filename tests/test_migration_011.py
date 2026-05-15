"""Phase 15: schema migration adds iCal-sync columns + index."""
from __future__ import annotations

import sqlite3

from school_test_engine.storage import run_migrations


def _columns(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _index_names(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA index_list({table})")}


def test_users_has_ical_columns(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    cols = _columns(conn, "users")
    assert "ical_feed_url" in cols
    assert "ical_last_sync_at" in cols
    assert "ical_last_sync_summary" in cols


def test_scheduled_events_has_external_columns(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    cols = _columns(conn, "scheduled_events")
    assert "external_uid" in cols
    assert "external_source" in cols


def test_unique_index_on_external_uid(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    assert "idx_events_external_uid" in _index_names(conn, "scheduled_events")

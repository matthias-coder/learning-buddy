from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import events_repo, run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def test_list_for_calendar_returns_all_kas_sorted_by_date(conn):
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-01")
    events_repo.create(conn, uid, "Englisch", "klausur", "2026-05-15")
    events_repo.create(conn, uid, "Bio", "test", "2026-07-10")
    rows = events_repo.list_for_calendar(conn, uid)
    dates = [r["event_date"] for r in rows]
    assert dates == ["2026-05-15", "2026-06-01", "2026-07-10"]


def test_list_for_calendar_scopes_by_user(conn):
    a = users_repo.create_user(conn, name="A")
    b = users_repo.create_user(conn, name="B")
    events_repo.create(conn, a, "Mathe", "klassenarbeit", "2026-06-01")
    events_repo.create(conn, b, "Englisch", "klausur", "2026-05-15")
    rows = events_repo.list_for_calendar(conn, a)
    assert len(rows) == 1
    assert rows[0]["subject"] == "Mathe"

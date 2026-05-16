"""users_repo.update_user persists calendar filter columns (Phase 17)."""
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def test_defaults_are_one_and_future(conn):
    uid = users_repo.create_user(conn, name="T")
    row = users_repo.get_user(conn, uid)
    assert row["calendar_show_klausuren"] == 1
    assert row["calendar_show_ferien"] == 1
    assert row["calendar_show_frei"] == 1
    assert row["calendar_show_events"] == 1
    assert row["calendar_timeframe"] == "future"


def test_update_calendar_filters_roundtrip(conn):
    uid = users_repo.create_user(conn, name="T")
    users_repo.update_user(
        conn, uid,
        calendar_show_klausuren=0,
        calendar_show_ferien=1,
        calendar_show_frei=0,
        calendar_show_events=1,
        calendar_timeframe="past",
    )
    row = users_repo.get_user(conn, uid)
    assert row["calendar_show_klausuren"] == 0
    assert row["calendar_show_ferien"] == 1
    assert row["calendar_show_frei"] == 0
    assert row["calendar_show_events"] == 1
    assert row["calendar_timeframe"] == "past"


def test_none_does_not_change_existing_value(conn):
    uid = users_repo.create_user(conn, name="T")
    users_repo.update_user(conn, uid, calendar_show_klausuren=0, calendar_timeframe="past")
    users_repo.update_user(conn, uid, calendar_show_klausuren=None, calendar_timeframe=None)
    row = users_repo.get_user(conn, uid)
    assert row["calendar_show_klausuren"] == 0
    assert row["calendar_timeframe"] == "past"

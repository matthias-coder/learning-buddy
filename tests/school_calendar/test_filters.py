from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.school_calendar.filters import CalendarFilters
from school_test_engine.storage import run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def test_defaults_all_kinds_on_future():
    f = CalendarFilters.defaults()
    assert f.show_klausuren is True
    assert f.show_ferien is True
    assert f.show_frei is True
    assert f.show_events is True
    assert f.timeframe == "future"


def test_from_user_row_reads_db_state(conn):
    uid = users_repo.create_user(conn, name="T")
    users_repo.update_user(conn, uid, calendar_show_klausuren=0, calendar_timeframe="past")
    row = users_repo.get_user(conn, uid)
    f = CalendarFilters.from_user_row(row)
    assert f.show_klausuren is False
    assert f.show_ferien is True
    assert f.timeframe == "past"


def test_with_kind_set_returns_new_instance():
    f = CalendarFilters.defaults()
    f2 = f.with_kind_set("ferien", False)
    assert f.show_ferien is True   # original unchanged
    assert f2.show_ferien is False


def test_active_kinds_reflects_toggles():
    f = CalendarFilters.defaults().with_kind_set("frei", False).with_kind_set("event", False)
    assert f.active_kinds() == {"klausur", "ferien"}

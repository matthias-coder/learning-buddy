"""End-to-end: sync iCal fixture → calendar contents → filter toggle → banner."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from school_test_engine.ical_sync import service
from school_test_engine.school_calendar.filters import CalendarFilters
from school_test_engine.school_calendar.service import (
    ferien_banner_state, list_entries,
)
from school_test_engine.storage import run_migrations, users_repo


FIXTURE = Path(__file__).parent / "fixtures" / "schulkalender_mini.ics"


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def test_full_loop_sync_filter_banner(monkeypatch, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://example.com/feed")

    ics_bytes = FIXTURE.read_bytes()
    monkeypatch.setattr(service, "_fetch", lambda url, timeout=10.0: ics_bytes)
    result = service.sync_feed(conn, uid)
    assert result.error is None
    # Sommerferien + Pädagogischer Tag + Herbstferien + Mathewettbewerb = 4
    assert result.cal_added == 4

    # All filters default-on, future timeframe — today before Herbst, after Sommer.
    f = CalendarFilters.defaults()
    entries = list_entries(conn, uid, date(2026, 9, 1), f)
    titles = {e.title for e in entries}
    assert "Herbstferien" in titles
    assert "Pädagogischer Tag" not in titles   # vergangen → futurefilter strippt

    # Banner countdown to Herbstferien
    state = ferien_banner_state(conn, uid, date(2026, 9, 26))
    assert state.mode == "countdown"
    assert state.vacation_title == "Herbstferien"

    # Toggle Ferien filter off → only events remain
    f2 = f.with_kind_set("ferien", False).with_kind_set("klausur", False)\
          .with_kind_set("frei", False)
    entries2 = list_entries(conn, uid, date(2026, 1, 1), f2)
    assert {e.title for e in entries2} == {"Mathematikwettbewerb Klassenstufe 8"}

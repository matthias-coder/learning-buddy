from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.school_calendar.service import (
    FerienBannerState, ferien_banner_state,
)
from school_test_engine.storage import calendar_events_repo, run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, name="C")


def test_hidden_when_no_vacations(conn, uid):
    state = ferien_banner_state(conn, uid, date(2026, 5, 15))
    assert state.mode == "hidden"


def test_countdown_to_next_vacation(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Herbstferien",
                                start_date="2026-10-19", end_date="2026-10-31")
    state = ferien_banner_state(conn, uid, date(2026, 9, 26))
    assert state.mode == "countdown"
    assert state.days == 23
    assert state.vacation_title == "Herbstferien"
    assert "23" in state.label
    assert "Herbstferien" in state.label


def test_countdown_label_for_one_day_uses_morgen(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommerferien",
                                start_date="2026-07-07", end_date="2026-08-15")
    state = ferien_banner_state(conn, uid, date(2026, 7, 6))
    assert state.days == 1
    assert "Morgen" in state.label


def test_in_vacation_remaining_days(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommerferien",
                                start_date="2026-07-07", end_date="2026-08-15")
    state = ferien_banner_state(conn, uid, date(2026, 8, 10))
    assert state.mode == "in_vacation"
    assert state.days == 5
    assert "5" in state.label
    assert "Sommerferien" in state.label


def test_in_vacation_zero_days_is_last_day(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommerferien",
                                start_date="2026-07-07", end_date="2026-08-15")
    state = ferien_banner_state(conn, uid, date(2026, 8, 15))
    assert state.mode == "in_vacation"
    assert state.days == 0
    assert "Letzter Ferientag" in state.label


def test_frei_kind_does_not_trigger_banner(conn, uid):
    """Single-day frei (Pädagogischer Tag) MUST NOT show as ferien banner."""
    calendar_events_repo.create(conn, user_id=uid, kind="frei", title="Päd. Tag",
                                start_date="2026-05-28", end_date="2026-05-28")
    state = ferien_banner_state(conn, uid, date(2026, 5, 15))
    assert state.mode == "hidden"

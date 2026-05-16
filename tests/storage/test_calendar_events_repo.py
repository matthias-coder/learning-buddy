"""calendar_events_repo CRUD + list_for_user with kind+timeframe filtering."""
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import (
    calendar_events_repo, run_migrations, users_repo,
)


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
    return users_repo.create_user(conn, name="Clemens")


def test_create_and_read_back(conn, uid):
    eid = calendar_events_repo.create(
        conn, user_id=uid, kind="ferien", title="Sommerferien",
        start_date="2026-07-07", end_date="2026-08-15",
        external_uid="uid-A", external_source="schulportal_hessen",
    )
    assert eid > 0
    row = conn.execute("SELECT * FROM calendar_events WHERE id = ?", (eid,)).fetchone()
    assert row["title"] == "Sommerferien"
    assert row["kind"] == "ferien"
    assert row["external_source"] == "schulportal_hessen"


def test_list_for_user_future_timeframe(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Past",
                                start_date="2024-07-01", end_date="2024-08-01")
    calendar_events_repo.create(conn, user_id=uid, kind="event", title="Future",
                                start_date="2030-01-01", end_date="2030-01-01")
    rows = calendar_events_repo.list_for_user(
        conn, uid, today="2026-05-15", timeframe="future",
        kinds={"ferien", "event"},
    )
    titles = [r["title"] for r in rows]
    assert titles == ["Future"]


def test_list_for_user_past_timeframe(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Past",
                                start_date="2024-07-01", end_date="2024-08-01")
    calendar_events_repo.create(conn, user_id=uid, kind="event", title="Future",
                                start_date="2030-01-01", end_date="2030-01-01")
    rows = calendar_events_repo.list_for_user(
        conn, uid, today="2026-05-15", timeframe="past",
        kinds={"ferien", "event"},
    )
    titles = [r["title"] for r in rows]
    assert titles == ["Past"]


def test_list_for_user_all_timeframe(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Past",
                                start_date="2024-07-01", end_date="2024-08-01")
    calendar_events_repo.create(conn, user_id=uid, kind="event", title="Future",
                                start_date="2030-01-01", end_date="2030-01-01")
    rows = calendar_events_repo.list_for_user(
        conn, uid, today="2026-05-15", timeframe="all",
        kinds={"ferien", "event"},
    )
    assert len(rows) == 2


def test_list_for_user_filters_by_kinds(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="F",
                                start_date="2030-01-01", end_date="2030-01-10")
    calendar_events_repo.create(conn, user_id=uid, kind="event", title="E",
                                start_date="2030-01-15", end_date="2030-01-15")
    rows = calendar_events_repo.list_for_user(
        conn, uid, today="2026-05-15", timeframe="all", kinds={"ferien"},
    )
    titles = [r["title"] for r in rows]
    assert titles == ["F"]


def test_update_by_external_uid_changes_title_and_dates(conn, uid):
    calendar_events_repo.create(
        conn, user_id=uid, kind="ferien", title="Old",
        start_date="2026-07-07", end_date="2026-08-15",
        external_uid="uid-A",
    )
    changed = calendar_events_repo.update_by_external_uid(
        conn, user_id=uid, external_uid="uid-A",
        kind="ferien", title="New", start_date="2026-07-08", end_date="2026-08-16",
    )
    assert changed is True
    row = conn.execute("SELECT title, start_date, end_date FROM calendar_events").fetchone()
    assert row["title"] == "New"
    assert row["start_date"] == "2026-07-08"


def test_delete_by_external_uid_removes_row(conn, uid):
    calendar_events_repo.create(
        conn, user_id=uid, kind="event", title="X",
        start_date="2026-01-01", end_date="2026-01-01",
        external_uid="uid-X",
    )
    assert calendar_events_repo.delete_by_external_uid(conn, uid, "uid-X") is True
    rows = conn.execute("SELECT id FROM calendar_events").fetchall()
    assert rows == []


def test_update_by_external_uid_returns_false_when_uid_missing(conn, uid):
    changed = calendar_events_repo.update_by_external_uid(
        conn, user_id=uid, external_uid="nonexistent",
        kind="ferien", title="X", start_date="2026-01-01", end_date="2026-01-01",
    )
    assert changed is False


def test_delete_by_external_uid_returns_false_when_uid_missing(conn, uid):
    assert calendar_events_repo.delete_by_external_uid(conn, uid, "nonexistent") is False


def test_find_active_vacation_returns_current_ferien(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommer",
                                start_date="2026-07-07", end_date="2026-08-15")
    row = calendar_events_repo.find_active_vacation(conn, uid, "2026-07-20")
    assert row is not None
    assert row["title"] == "Sommer"


def test_find_active_vacation_ignores_single_day_frei(conn, uid):
    """Bewegliche Feiertage (kind='frei') triggern den Banner nicht."""
    calendar_events_repo.create(conn, user_id=uid, kind="frei", title="Päd. Tag",
                                start_date="2026-05-15", end_date="2026-05-15")
    row = calendar_events_repo.find_active_vacation(conn, uid, "2026-05-15")
    assert row is None


def test_find_active_vacation_returns_none_outside_range(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommer",
                                start_date="2026-07-07", end_date="2026-08-15")
    row = calendar_events_repo.find_active_vacation(conn, uid, "2026-09-01")
    assert row is None


def test_find_next_vacation_returns_earliest_future(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Herbst",
                                start_date="2026-10-19", end_date="2026-10-31")
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Weihnachten",
                                start_date="2026-12-22", end_date="2027-01-06")
    row = calendar_events_repo.find_next_vacation(conn, uid, "2026-05-15")
    assert row is not None
    assert row["title"] == "Herbst"


def test_find_next_vacation_ignores_frei_kind(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="frei", title="Brückentag",
                                start_date="2026-05-29", end_date="2026-05-29")
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommer",
                                start_date="2026-07-07", end_date="2026-08-15")
    row = calendar_events_repo.find_next_vacation(conn, uid, "2026-05-15")
    assert row["title"] == "Sommer"

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.storage import (
    assessments_repo, events_repo, run_migrations, users_repo,
)


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def test_past_klausur_without_grade_returned(conn):
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-04-01")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 1),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["subject"] == "Mathe"
    assert row["assessment_id"] is None
    assert row["grade"] is None


def test_past_klausur_with_grade_returned(conn):
    uid = users_repo.create_user(conn, name="T")
    eid = events_repo.create(conn, uid, "Englisch", "klausur", "2026-04-15")
    assessments_repo.create(
        conn, uid, "Englisch", "schriftlich", "2026-04-15",
        grade=2.5, scheduled_event_id=eid,
    )
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 1),
    )
    assert len(rows) == 1
    assert rows[0]["assessment_id"] is not None
    assert rows[0]["grade"] == 2.5


def test_future_klausur_excluded(conn):
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Bio", "test", "2026-07-01")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 1),
    )
    assert rows == []


def test_today_klausur_not_yet_past(conn):
    # end_date == today should NOT count as past (spec edge case)
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klausur", "2026-05-18")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 18),
    )
    assert rows == []


def test_non_klausur_kind_excluded(conn):
    # "sonstiges" kind exists in the CHECK constraint but is not a KA.
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "sonstiges", "2026-04-01")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 1),
    )
    assert rows == []


def test_scoped_by_user(conn):
    a = users_repo.create_user(conn, name="A")
    b = users_repo.create_user(conn, name="B")
    events_repo.create(conn, a, "Mathe", "klausur", "2026-04-01")
    events_repo.create(conn, b, "Englisch", "klausur", "2026-04-02")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, a, today=date(2026, 5, 1),
    )
    assert len(rows) == 1
    assert rows[0]["subject"] == "Mathe"


def test_ordered_by_date_desc(conn):
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klausur", "2026-03-01")
    events_repo.create(conn, uid, "Englisch", "klausur", "2026-04-01")
    events_repo.create(conn, uid, "Bio", "test", "2026-02-01")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 1),
    )
    dates = [r["event_date"] for r in rows]
    assert dates == ["2026-04-01", "2026-03-01", "2026-02-01"]

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.school_calendar.filters import CalendarFilters
from school_test_engine.school_calendar.service import (
    group_by_month, list_entries,
)
from school_test_engine.storage import (
    calendar_events_repo, events_repo, run_migrations, users_repo,
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
    return users_repo.create_user(conn, name="C")


def test_list_entries_merges_klausuren_and_calendar_chronologically(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-15")
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommer",
                                start_date="2026-07-07", end_date="2026-08-15")
    calendar_events_repo.create(conn, user_id=uid, kind="frei", title="Päd. Tag",
                                start_date="2026-05-28", end_date="2026-05-28")
    entries = list_entries(conn, uid, date(2026, 5, 1), CalendarFilters.defaults())
    titles = [e.title for e in entries]
    assert titles[0] == "Päd. Tag"
    assert titles[1].startswith("Mathe")
    assert titles[2] == "Sommer"


def test_list_entries_filters_klausur_out(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-15")
    f = CalendarFilters.defaults().with_kind_set("klausur", False)
    entries = list_entries(conn, uid, date(2026, 5, 1), f)
    assert entries == []


def test_list_entries_respects_timeframe_for_klausuren(conn, uid):
    events_repo.create(conn, uid, "Past", "klassenarbeit", "2024-05-01")
    events_repo.create(conn, uid, "Future", "klassenarbeit", "2030-05-01")
    f = CalendarFilters.defaults()  # future
    entries = list_entries(conn, uid, date(2026, 5, 15), f)
    subjects = [e.subject for e in entries]
    assert subjects == ["Future"]


def test_list_entries_empty_active_kinds_returns_empty(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2030-06-15")
    f = CalendarFilters(False, False, False, False, "future")
    assert list_entries(conn, uid, date(2026, 1, 1), f) == []


def test_group_by_month_returns_sections_in_chronological_order(conn, uid):
    events_repo.create(conn, uid, "A", "klassenarbeit", "2026-05-10")
    events_repo.create(conn, uid, "B", "klassenarbeit", "2026-07-03")
    events_repo.create(conn, uid, "C", "klassenarbeit", "2026-05-20")
    entries = list_entries(conn, uid, date(2026, 1, 1), CalendarFilters.defaults())
    groups = group_by_month(entries)
    labels = [g[0] for g in groups]
    assert labels == ["Mai 2026", "Juli 2026"]
    assert [e.subject for e in groups[0][1]] == ["A", "C"]


def test_klausur_entry_title_includes_subject_and_kind(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-15")
    entries = list_entries(conn, uid, date(2026, 5, 1), CalendarFilters.defaults())
    assert entries[0].title == "Mathe Klassenarbeit"

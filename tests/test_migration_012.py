"""Phase 17: schema migration adds calendar_events + user filter columns."""
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import run_migrations


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def _columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _index_names(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA index_list({table})")}


def test_calendar_events_table_exists_with_columns(conn):
    cols = _columns(conn, "calendar_events")
    assert {"id", "user_id", "kind", "title", "start_date", "end_date",
            "external_uid", "external_source", "created_at"}.issubset(cols)


def test_calendar_events_kind_check_constraint(conn):
    from school_test_engine.storage import users_repo
    uid = users_repo.create_user(conn, name="T")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO calendar_events (user_id, kind, title, start_date, end_date) "
            "VALUES (?, 'invalid_kind', 'x', '2026-01-01', '2026-01-01')",
            (uid,),
        )
        conn.commit()


def test_calendar_events_unique_external_uid_per_user(conn):
    from school_test_engine.storage import users_repo
    uid = users_repo.create_user(conn, name="T")
    conn.execute(
        "INSERT INTO calendar_events (user_id, kind, title, start_date, end_date, external_uid) "
        "VALUES (?, 'ferien', 'F1', '2026-07-07', '2026-08-16', 'uid-A')",
        (uid,),
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO calendar_events (user_id, kind, title, start_date, end_date, external_uid) "
            "VALUES (?, 'ferien', 'F2', '2026-10-19', '2026-10-31', 'uid-A')",
            (uid,),
        )
        conn.commit()


def test_users_has_calendar_filter_columns(conn):
    cols = _columns(conn, "users")
    assert {"calendar_show_klausuren", "calendar_show_ferien",
            "calendar_show_frei", "calendar_show_events",
            "calendar_timeframe"}.issubset(cols)

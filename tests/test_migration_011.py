"""Phase 15: schema migration adds iCal-sync columns + index."""
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


def _columns(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _index_names(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA index_list({table})")}


def test_users_has_ical_columns(conn):
    cols = _columns(conn, "users")
    assert "ical_feed_url" in cols
    assert "ical_last_sync_at" in cols
    assert "ical_last_sync_summary" in cols


def test_scheduled_events_has_external_columns(conn):
    cols = _columns(conn, "scheduled_events")
    assert "external_uid" in cols
    assert "external_source" in cols


def test_unique_index_on_external_uid(conn):
    assert "idx_events_external_uid" in _index_names(conn, "scheduled_events")


def test_partial_index_allows_multiple_null_external_uids(conn):
    """The partial index `WHERE external_uid IS NOT NULL` must NOT prevent
    multiple manual rows (where external_uid is NULL) for the same user."""
    from school_test_engine.storage import users_repo, events_repo

    uid = users_repo.create_user(conn, name="Tester")
    # Two manual events (external_uid stays NULL) for the same user must coexist.
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-15")
    events_repo.create(conn, uid, "Englisch", "klassenarbeit", "2026-05-16")
    rows = list(conn.execute(
        "SELECT id FROM scheduled_events WHERE user_id = ? AND external_uid IS NULL",
        (uid,),
    ))
    assert len(rows) == 2


def test_unique_index_blocks_duplicate_external_uid(conn):
    """Two rows with the same (user_id, external_uid) and non-NULL UID must
    raise IntegrityError."""
    from school_test_engine.storage import users_repo

    uid = users_repo.create_user(conn, name="Tester")
    conn.execute(
        "INSERT INTO scheduled_events (user_id, subject, kind, event_date, topics, external_uid) "
        "VALUES (?, 'Mathe', 'klassenarbeit', '2026-05-15', '[]', 'dup-uid-1')",
        (uid,),
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO scheduled_events (user_id, subject, kind, event_date, topics, external_uid) "
            "VALUES (?, 'Englisch', 'klassenarbeit', '2026-05-16', '[]', 'dup-uid-1')",
            (uid,),
        )
        conn.commit()


def test_users_repo_update_user_persists_ical_fields(conn):
    from school_test_engine.storage import users_repo
    uid = users_repo.create_user(conn, name="Test")
    users_repo.update_user(
        conn, uid,
        ical_feed_url="https://example.com/feed",
        ical_last_sync_at="2026-05-15T10:00:00",
        ical_last_sync_summary='{"added":1}',
    )
    row = users_repo.get_user(conn, uid)
    assert row["ical_feed_url"] == "https://example.com/feed"
    assert row["ical_last_sync_at"] == "2026-05-15T10:00:00"
    assert row["ical_last_sync_summary"] == '{"added":1}'


def test_users_repo_update_user_clears_ical_fields_with_none(conn):
    from school_test_engine.storage import users_repo
    uid = users_repo.create_user(conn, name="Test")
    users_repo.update_user(conn, uid, ical_feed_url="https://x.com/feed")
    users_repo.update_user(conn, uid, ical_feed_url=None)
    row = users_repo.get_user(conn, uid)
    assert row["ical_feed_url"] is None

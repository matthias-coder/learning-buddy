import pytest

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import daily_sessions_repo


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, "Clemens", "🧒")


def test_get_for_today_returns_none_when_missing(conn, uid):
    assert daily_sessions_repo.get_for_today(conn, uid, "2026-05-14") is None


def test_start_session_inserts(conn, uid):
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14",
        test_id=None, attempt_id=None,
        started_at="2026-05-14T08:00:00",
    )
    row = daily_sessions_repo.get_for_today(conn, uid, "2026-05-14")
    assert row is not None
    assert row["session_date"] == "2026-05-14"
    assert row["completed_at"] is None


def test_complete_session_sets_completed_at(conn, uid):
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14",
        test_id=None, attempt_id=None,
        started_at="2026-05-14T08:00:00",
    )
    daily_sessions_repo.complete_session(
        conn, uid, "2026-05-14", completed_at="2026-05-14T08:05:00",
    )
    row = daily_sessions_repo.get_for_today(conn, uid, "2026-05-14")
    assert row["completed_at"] == "2026-05-14T08:05:00"


def test_list_recent_completed_dates_returns_only_completed(conn, uid):
    # Three sessions: two completed, one in-progress
    for d in ["2026-05-12", "2026-05-13"]:
        daily_sessions_repo.start_session(
            conn, uid, d, test_id=None, attempt_id=None, started_at=d + "T08:00:00",
        )
        daily_sessions_repo.complete_session(conn, uid, d, completed_at=d + "T08:05:00")
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14", test_id=None, attempt_id=None, started_at="2026-05-14T08:00:00",
    )
    dates = daily_sessions_repo.list_recent_completed_dates(
        conn, uid, since="2026-05-01", until="2026-05-14",
    )
    assert set(dates) == {"2026-05-12", "2026-05-13"}


def _make_test_and_attempt(conn, uid):
    """Insert raw rows into tests + attempts to satisfy FK constraints."""
    cur = conn.execute(
        """
        INSERT INTO tests
            (title, subject, grade, school_type, description, time_limit_min,
             notenschluessel, source_json, imported_at, user_id)
        VALUES ('T', 'M', 8, 'realschule', NULL, NULL, '{}', '{}', ?, ?)
        """,
        ("2026-05-14T08:00:00", uid),
    )
    test_id = cur.lastrowid
    cur = conn.execute(
        """
        INSERT INTO attempts
            (test_id, started_at, points_possible, shuffle_seed, completed, current_index, user_id)
        VALUES (?, ?, 10, NULL, 0, 0, ?)
        """,
        (test_id, "2026-05-14T08:00:00", uid),
    )
    attempt_id = cur.lastrowid
    conn.commit()
    return test_id, attempt_id


def test_find_by_attempt_returns_session(conn, uid):
    test_id, attempt_id = _make_test_and_attempt(conn, uid)
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14", test_id=test_id, attempt_id=attempt_id,
        started_at="2026-05-14T08:00:00",
    )
    row = daily_sessions_repo.find_by_attempt(conn, attempt_id)
    assert row is not None
    assert row["session_date"] == "2026-05-14"


def test_find_by_attempt_returns_none_when_missing(conn, uid):
    assert daily_sessions_repo.find_by_attempt(conn, 99999) is None


def test_user_isolation(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    daily_sessions_repo.start_session(
        conn, a, "2026-05-14", test_id=None, attempt_id=None, started_at="2026-05-14T08:00:00",
    )
    assert daily_sessions_repo.get_for_today(conn, a, "2026-05-14") is not None
    assert daily_sessions_repo.get_for_today(conn, b, "2026-05-14") is None

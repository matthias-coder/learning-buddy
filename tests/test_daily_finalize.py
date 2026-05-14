import pytest
from datetime import datetime

from school_test_engine.storage import (
    connect, run_migrations, users_repo, attempts_repo, daily_sessions_repo,
)
from school_test_engine.daily.finalize import finalize_if_daily


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


def _create_basic_test_and_attempt(conn, uid):
    cur = conn.execute(
        """INSERT INTO tests (title, subject, grade, school_type, description,
                              time_limit_min, notenschluessel, source_json,
                              imported_at, is_study, user_id)
           VALUES ('T', 'Daily-5', 8, 'Realschule', '', NULL, '{}', '{}', '2026-01-01', 1, ?)""",
        (uid,),
    )
    test_id = cur.lastrowid
    aid = attempts_repo.start_attempt(conn, test_id, 10, uid)
    return test_id, aid


def test_finalize_completes_open_session(conn, uid):
    test_id, aid = _create_basic_test_and_attempt(conn, uid)
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14",
        test_id=test_id, attempt_id=aid,
        started_at="2026-05-14T08:00:00",
    )
    completed = finalize_if_daily(conn, aid)
    assert completed is True
    row = daily_sessions_repo.get_for_today(conn, uid, "2026-05-14")
    assert row["completed_at"] is not None


def test_finalize_returns_false_for_non_daily_attempt(conn, uid):
    test_id, aid = _create_basic_test_and_attempt(conn, uid)
    # NO daily_sessions row — just a regular attempt
    completed = finalize_if_daily(conn, aid)
    assert completed is False


def test_finalize_returns_false_when_already_completed(conn, uid):
    test_id, aid = _create_basic_test_and_attempt(conn, uid)
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14",
        test_id=test_id, attempt_id=aid,
        started_at="2026-05-14T08:00:00",
    )
    daily_sessions_repo.complete_session(conn, uid, "2026-05-14", completed_at="2026-05-14T08:05:00")
    # Second call should not re-finalize
    completed = finalize_if_daily(conn, aid)
    assert completed is False

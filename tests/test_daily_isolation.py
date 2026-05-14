import pytest

from school_test_engine.storage import (
    connect, run_migrations, users_repo, daily_sessions_repo,
)


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_two_users_have_independent_sessions(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    daily_sessions_repo.start_session(
        conn, a, "2026-05-14", test_id=None, attempt_id=None,
        started_at="2026-05-14T08:00:00",
    )
    assert daily_sessions_repo.get_for_today(conn, a, "2026-05-14") is not None
    assert daily_sessions_repo.get_for_today(conn, b, "2026-05-14") is None


def test_delete_user_cascade_removes_daily_sessions(conn):
    uid = users_repo.create_user(conn, "Wegmacher")
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14", test_id=None, attempt_id=None,
        started_at="2026-05-14T08:00:00",
    )
    users_repo.delete_user(conn, uid)
    assert conn.execute(
        "SELECT COUNT(*) FROM daily_sessions WHERE user_id = ?", (uid,)
    ).fetchone()[0] == 0

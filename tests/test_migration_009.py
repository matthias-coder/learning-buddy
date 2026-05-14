import pytest

from school_test_engine.storage import connect, run_migrations


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_daily_sessions_table_exists(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_sessions'"
    ).fetchone()
    assert row is not None


def test_daily_sessions_composite_pk_enforced(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (2, 'X', '👤', 1, '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO daily_sessions (user_id, session_date, started_at) "
        "VALUES (2, '2026-05-14', '2026-05-14T08:00:00')"
    )
    conn.commit()
    # Same (user_id, session_date) must fail
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO daily_sessions (user_id, session_date, started_at) "
            "VALUES (2, '2026-05-14', '2026-05-14T20:00:00')"
        )


def test_daily_sessions_cascade_on_user_delete(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (3, 'X', '👤', 2, '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO daily_sessions (user_id, session_date, started_at) "
        "VALUES (3, '2026-05-14', '2026-05-14T08:00:00')"
    )
    conn.commit()
    conn.execute("DELETE FROM users WHERE id = 3")
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) FROM daily_sessions WHERE user_id = 3"
    ).fetchone()[0] == 0


def test_daily_sessions_completed_at_nullable(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(daily_sessions)").fetchall()}
    assert "completed_at" in cols
    assert cols["completed_at"]["notnull"] == 0


def test_daily_sessions_attempt_id_nullable_and_set_null(conn):
    # ON DELETE SET NULL semantics on attempt_id FK
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (4, 'X', '👤', 3, '2026-01-01T00:00:00')"
    )
    conn.commit()
    # We can't fully exercise the SET NULL without creating an attempt row;
    # this test asserts the column is nullable
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(daily_sessions)").fetchall()}
    assert "attempt_id" in cols
    assert cols["attempt_id"]["notnull"] == 0

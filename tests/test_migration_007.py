import pytest

from school_test_engine.storage import connect, run_migrations


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_users_has_ai_style_briefing_column(conn):
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "ai_style_briefing" in cols


def test_prompt_drafts_table_exists(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='prompt_drafts'"
    ).fetchone()
    assert row is not None


def test_prompt_drafts_composite_primary_key(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (2, 'Test', '👤', 1, '2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.execute(
        "INSERT INTO prompt_drafts (user_id, subject, last_topic, last_count, last_dist) "
        "VALUES (2, 'Mathe', 'Funktionen', 10, 'auto')"
    )
    # Duplicate (user_id, subject) must fail
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO prompt_drafts (user_id, subject, last_topic, last_count, last_dist) "
            "VALUES (2, 'Mathe', 'X', 10, 'auto')"
        )


def test_prompt_drafts_cascade_on_user_delete(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (3, 'Test', '👤', 2, '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO prompt_drafts (user_id, subject, last_topic, last_count, last_dist) "
        "VALUES (3, 'Mathe', 'X', 10, 'auto')"
    )
    conn.commit()
    conn.execute("DELETE FROM users WHERE id = 3")
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) FROM prompt_drafts WHERE user_id = 3"
    ).fetchone()[0] == 0

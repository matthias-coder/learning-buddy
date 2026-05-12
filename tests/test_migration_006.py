import pytest

from school_test_engine.storage import connect, run_migrations


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_scheduled_events_table_exists(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_events'"
    )
    assert cur.fetchone() is not None


def test_assessments_table_exists(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='assessments'"
    )
    assert cur.fetchone() is not None


def test_assessments_event_fk_set_null_on_event_delete(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (2, 'Test', '👤', 1, '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO scheduled_events (id, user_id, subject, kind, event_date, topics) "
        "VALUES (10, 2, 'Mathe', 'klassenarbeit', '2026-05-15', '[]')"
    )
    conn.execute(
        "INSERT INTO assessments "
        "(id, user_id, subject, category, assessment_date, grade, scheduled_event_id) "
        "VALUES (100, 2, 'Mathe', 'schriftlich', '2026-05-15', 2.0, 10)"
    )
    conn.commit()
    conn.execute("DELETE FROM scheduled_events WHERE id = 10")
    conn.commit()
    row = conn.execute("SELECT scheduled_event_id FROM assessments WHERE id = 100").fetchone()
    assert row["scheduled_event_id"] is None


def test_cascade_on_user_delete_assessments_and_events(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (2, 'Test', '👤', 1, '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO scheduled_events (user_id, subject, kind, event_date, topics) "
        "VALUES (2, 'Mathe', 'klassenarbeit', '2026-05-15', '[]')"
    )
    conn.execute(
        "INSERT INTO assessments (user_id, subject, category, assessment_date, grade) "
        "VALUES (2, 'Mathe', 'schriftlich', '2026-05-15', 2.0)"
    )
    conn.commit()
    conn.execute("DELETE FROM users WHERE id = 2")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM scheduled_events WHERE user_id = 2").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM assessments WHERE user_id = 2").fetchone()[0] == 0

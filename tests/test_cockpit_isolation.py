import pytest

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import events_repo, assessments_repo


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_two_users_dont_see_each_others_events(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    events_repo.create(conn, a, "Mathe", "klassenarbeit", "2026-06-01", topics=[])
    events_repo.create(conn, b, "Bio", "klassenarbeit", "2026-06-02", topics=[])
    assert len(events_repo.list_all(conn, a)) == 1
    assert len(events_repo.list_all(conn, b)) == 1
    assert events_repo.list_all(conn, a)[0]["subject"] == "Mathe"


def test_two_users_dont_see_each_others_assessments(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    assessments_repo.create(conn, a, "Mathe", "schriftlich", "2026-06-01", grade=2.0)
    assessments_repo.create(conn, b, "Mathe", "schriftlich", "2026-06-02", grade=4.0)
    assert assessments_repo.list_all(conn, a)[0]["grade"] == 2.0
    assert assessments_repo.list_all(conn, b)[0]["grade"] == 4.0


def test_delete_user_cascade_removes_events_and_assessments(conn):
    uid = users_repo.create_user(conn, "Wegmacher")
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-01", topics=[])
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-06-01", grade=2.0, scheduled_event_id=eid)
    users_repo.delete_user(conn, uid)
    assert conn.execute("SELECT COUNT(*) FROM scheduled_events WHERE user_id = ?", (uid,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM assessments WHERE user_id = ?", (uid,)).fetchone()[0] == 0

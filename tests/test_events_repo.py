import pytest

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import events_repo


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


def test_create_minimal(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=["Funktionen"])
    row = events_repo.get(conn, eid)
    assert row["subject"] == "Mathe"
    assert row["kind"] == "klassenarbeit"
    assert row["event_date"] == "2026-05-20"


def test_create_topics_stored_as_json(conn, uid):
    eid = events_repo.create(conn, uid, "Bio", "klassenarbeit", "2026-06-01", topics=["Zellbiologie", "Genetik"])
    row = events_repo.get(conn, eid)
    import json
    assert json.loads(row["topics"]) == ["Zellbiologie", "Genetik"]


def test_list_upcoming_filters_past_events(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-04-01", topics=[])  # past
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-01", topics=[])  # future
    upcoming = events_repo.list_upcoming(conn, uid, today="2026-05-12", limit=3)
    assert len(upcoming) == 1
    assert upcoming[0]["event_date"] == "2026-06-01"


def test_list_upcoming_sorted_ascending(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-15", topics=[])
    events_repo.create(conn, uid, "Englisch", "klassenarbeit", "2026-05-20", topics=[])
    upcoming = events_repo.list_upcoming(conn, uid, today="2026-05-12", limit=3)
    assert [r["event_date"] for r in upcoming] == ["2026-05-20", "2026-06-15"]


def test_list_upcoming_respects_limit(conn, uid):
    for i in range(5):
        events_repo.create(conn, uid, "Mathe", "klassenarbeit", f"2026-06-{i+1:02d}", topics=[])
    upcoming = events_repo.list_upcoming(conn, uid, today="2026-05-12", limit=3)
    assert len(upcoming) == 3


def test_list_all_includes_past(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-01-15", topics=[])
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-15", topics=[])
    all_events = events_repo.list_all(conn, uid)
    assert len(all_events) == 2


def test_update_changes_fields(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=["A"])
    events_repo.update(conn, eid, event_date="2026-05-27", topics=["B", "C"], note="Verschoben")
    row = events_repo.get(conn, eid)
    assert row["event_date"] == "2026-05-27"
    assert row["note"] == "Verschoben"
    import json
    assert json.loads(row["topics"]) == ["B", "C"]


def test_delete_removes_row(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=[])
    events_repo.delete(conn, eid)
    assert events_repo.get(conn, eid) is None


def test_user_isolation(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    events_repo.create(conn, a, "Mathe", "klassenarbeit", "2026-06-01", topics=[])
    assert len(events_repo.list_all(conn, a)) == 1
    assert len(events_repo.list_all(conn, b)) == 0

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


@pytest.fixture
def user_id(conn):
    return users_repo.create_user(conn, name="Tester")


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


def test_create_persists_external_uid_and_source(conn, user_id):
    eid = events_repo.create(
        conn, user_id, "Mathe", "klassenarbeit", "2026-06-01",
        external_uid="abc-klausur-1@host", external_source="schulportal_hessen",
    )
    row = events_repo.get(conn, eid)
    assert row["external_uid"] == "abc-klausur-1@host"
    assert row["external_source"] == "schulportal_hessen"


def test_list_with_external_uid_returns_only_synced_events(conn, user_id):
    events_repo.create(conn, user_id, "Mathe", "klassenarbeit", "2026-06-01")  # manual, no uid
    events_repo.create(
        conn, user_id, "Englisch", "klassenarbeit", "2026-06-08",
        external_uid="x-klausur-1@h", external_source="schulportal_hessen",
    )
    rows = events_repo.list_with_external_uid(conn, user_id)
    assert len(rows) == 1
    assert rows[0]["external_uid"] == "x-klausur-1@h"


def test_update_by_external_uid_changes_only_synced_fields(conn, user_id):
    import json
    eid = events_repo.create(
        conn, user_id, "Englisch", "klassenarbeit", "2026-06-08",
        topics=["Vocab", "Grammar"], note="manuell ergänzt",
        external_uid="x-klausur-1@h", external_source="schulportal_hessen",
    )
    events_repo.update_by_external_uid(
        conn, user_id, "x-klausur-1@h",
        subject="Englisch", kind="klassenarbeit", event_date="2026-06-15",
    )
    row = events_repo.get(conn, eid)
    assert row["event_date"] == "2026-06-15"
    # topics + note unangetastet
    assert json.loads(row["topics"]) == ["Vocab", "Grammar"]
    assert row["note"] == "manuell ergänzt"

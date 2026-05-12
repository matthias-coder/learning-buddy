import pytest

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import assessments_repo, events_repo


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
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0)
    row = assessments_repo.get(conn, aid)
    assert row["subject"] == "Mathe"
    assert row["grade"] == 2.0
    assert row["scheduled_event_id"] is None


def test_create_with_event_link(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0, scheduled_event_id=eid)
    row = assessments_repo.get(conn, aid)
    assert row["scheduled_event_id"] == eid


def test_list_by_subject(conn, uid):
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0)
    assessments_repo.create(conn, uid, "Englisch", "schriftlich", "2026-05-22", grade=3.0)
    assessments_repo.create(conn, uid, "Mathe", "muendlich", "2026-04-01", grade=2.5)
    rows = assessments_repo.list_by_subject(conn, uid, "Mathe")
    assert len(rows) == 2
    # newest first
    assert rows[0]["assessment_date"] == "2026-05-20"


def test_list_all_chronological_desc(conn, uid):
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0)
    assessments_repo.create(conn, uid, "Bio", "muendlich", "2026-04-01", grade=2.5)
    rows = assessments_repo.list_all(conn, uid)
    assert [r["assessment_date"] for r in rows] == ["2026-05-20", "2026-04-01"]


def test_find_by_event(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0, scheduled_event_id=eid)
    row = assessments_repo.find_by_event(conn, eid)
    assert row is not None
    assert row["id"] == aid


def test_find_by_event_returns_none_if_no_link(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=[])
    assert assessments_repo.find_by_event(conn, eid) is None


def test_update_changes_fields(conn, uid):
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=3.0)
    assessments_repo.update(conn, aid, grade=2.5, note="korrigiert")
    row = assessments_repo.get(conn, aid)
    assert row["grade"] == 2.5
    assert row["note"] == "korrigiert"


def test_delete_removes_row(conn, uid):
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0)
    assessments_repo.delete(conn, aid)
    assert assessments_repo.get(conn, aid) is None


def test_points_optional(conn, uid):
    aid = assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", "2026-05-20",
        grade=2.0, points=38, max_points=50, note="gut"
    )
    row = assessments_repo.get(conn, aid)
    assert row["points"] == 38
    assert row["max_points"] == 50

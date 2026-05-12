import json
import pytest
from datetime import date

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import events_repo, assessments_repo
from school_test_engine.cockpit import service as cockpit


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


def test_upcoming_events_for_menu_returns_pending(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=["Funktionen"])
    events_repo.create(conn, uid, "Englisch", "klassenarbeit", "2026-06-01", topics=["Vocab U5"])
    result = cockpit.upcoming_events_for_menu(conn, uid, today=date(2026, 5, 12))
    assert len(result) == 2
    assert result[0].subject == "Mathe"
    assert result[0].days_until == 8
    assert result[0].topics == ["Funktionen"]
    assert result[0].linked_assessment_id is None


def test_upcoming_events_for_menu_marks_linked_assessment(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0, scheduled_event_id=eid)
    result = cockpit.upcoming_events_for_menu(conn, uid, today=date(2026, 5, 12))
    assert result[0].linked_assessment_id == aid


def test_upcoming_events_for_menu_excludes_past(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-04-01", topics=[])
    result = cockpit.upcoming_events_for_menu(conn, uid, today=date(2026, 5, 12))
    assert result == []

import json
import pytest
from datetime import date

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import events_repo, assessments_repo
from school_test_engine.cockpit import service as cockpit
from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import attempts_repo
from pathlib import Path


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


def test_upcoming_events_dedupes_when_event_has_multiple_assessments(conn, uid):
    # Edge case: same event has both schriftlich and muendlich assessment.
    # The LEFT-JOIN approach would multiply rows and corrupt LIMIT.
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=[])
    events_repo.create(conn, uid, "Englisch", "klassenarbeit", "2026-05-21", topics=[])
    events_repo.create(conn, uid, "Bio", "klassenarbeit", "2026-05-22", topics=[])
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0, scheduled_event_id=eid)
    assessments_repo.create(conn, uid, "Mathe", "muendlich", "2026-05-20", grade=1.5, scheduled_event_id=eid)
    result = cockpit.upcoming_events_for_menu(conn, uid, today=date(2026, 5, 12), limit=3)
    # Should be 3 distinct events: Mathe, Englisch, Bio
    assert len(result) == 3
    assert [r.subject for r in result] == ["Mathe", "Englisch", "Bio"]
    # First (Mathe) has linked_assessment_id pointing to one of the two assessments
    assert result[0].linked_assessment_id is not None


def _seed_test_and_attempt(conn, user_id, subject, finished_at, note_value):
    """Helper: import a test for `subject`, create one finished attempt with given note."""
    # Build a minimal test JSON inline rather than relying on file
    payload = json.dumps({
        "schema_version": 1,
        "title": "x",
        "subject": subject,
        "grade": 8,
        "notenschluessel": {"1": 90, "2": 75, "3": 60, "4": 45, "5": 20, "6": 0},
        "questions": [
            {
                "id": "q1",
                "type": "single_choice",
                "topic": "t",
                "difficulty": "mittel",
                "points": 10,
                "prompt": "p",
                "choices": [{"id": "a", "text": "a"}, {"id": "b", "text": "b"}],
                "correct": ["a"],
            }
        ],
    })
    test_id = import_from_string(conn, payload, user_id=user_id)
    aid = attempts_repo.start_attempt(conn, test_id, 10, user_id)
    attempts_repo.finish_attempt(conn, aid, points_earned=10, percent=100, note=note_value)
    conn.execute("UPDATE attempts SET finished_at = ? WHERE id = ?", (finished_at, aid))
    conn.commit()
    return test_id, aid


def test_comparison_uses_attempts_between_prev_ka_and_this_ka(conn, uid):
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-03-01T10:00:00Z", note_value=3)  # before prev KA
    prev_eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-04-01", topics=[])
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-04-01", grade=3.0, scheduled_event_id=prev_eid)
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-04-15T10:00:00Z", note_value=2)  # in window
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-05-01T10:00:00Z", note_value=2)  # in window
    this_eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-15", topics=[])
    this_aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-15", grade=2.0, scheduled_event_id=this_eid)

    cmp = cockpit.comparison_for_assessment(conn, this_aid)
    assert cmp is not None
    assert cmp.attempts_count == 2
    assert cmp.attempts_grade_avg == pytest.approx(2.0)
    assert cmp.real_grade == 2.0
    assert cmp.delta_label == "App-Übungen und echte KA waren sehr ähnlich"


def test_comparison_first_ka_uses_all_attempts_before(conn, uid):
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-03-01T10:00:00Z", note_value=2)
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-04-01T10:00:00Z", note_value=2)
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-15", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-15", grade=3.0, scheduled_event_id=eid)
    cmp = cockpit.comparison_for_assessment(conn, aid)
    assert cmp is not None
    assert cmp.attempts_count == 2
    assert cmp.delta_label.startswith("Du warst in der KA schlechter")


def test_comparison_filters_by_subject(conn, uid):
    _seed_test_and_attempt(conn, uid, "Englisch", "2026-04-15T10:00:00Z", note_value=1)
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-15", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-15", grade=2.0, scheduled_event_id=eid)
    cmp = cockpit.comparison_for_assessment(conn, aid)
    assert cmp is None  # no Mathe attempts in window


def test_comparison_none_for_unlinked_assessment(conn, uid):
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-15", grade=2.0)
    assert cockpit.comparison_for_assessment(conn, aid) is None


def test_comparison_app_better_label(conn, uid):
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-05-01T10:00:00Z", note_value=4)
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-15", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-15", grade=2.0, scheduled_event_id=eid)
    cmp = cockpit.comparison_for_assessment(conn, aid)
    assert cmp.delta_label.startswith("Du warst in der KA besser")


def test_subject_grade_average_both_categories(conn, uid):
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-04-01", grade=2.0)
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-01", grade=3.0)
    assessments_repo.create(conn, uid, "Mathe", "muendlich", "2026-04-15", grade=2.0)
    avg = cockpit.subject_grade_average(conn, uid, "Mathe")
    assert avg.schriftlich_avg == 2.5
    assert avg.muendlich_avg == 2.0
    assert avg.zeugnis_estimate == pytest.approx(2.25)


def test_subject_grade_average_only_schriftlich(conn, uid):
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-04-01", grade=2.0)
    avg = cockpit.subject_grade_average(conn, uid, "Mathe")
    assert avg.schriftlich_avg == 2.0
    assert avg.muendlich_avg is None
    assert avg.zeugnis_estimate == 2.0


def test_subject_grade_average_empty(conn, uid):
    avg = cockpit.subject_grade_average(conn, uid, "Mathe")
    assert avg.schriftlich_avg is None
    assert avg.muendlich_avg is None
    assert avg.zeugnis_estimate is None


def test_aggregate_comparison_needs_three_or_more(conn, uid):
    # only 2 comparable assessments → None
    for i, d in enumerate(["2026-03-15", "2026-04-15"]):
        _seed_test_and_attempt(conn, uid, "Mathe", f"2026-0{2+i}-25T10:00:00Z", note_value=2)
        eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", d, topics=[])
        assessments_repo.create(conn, uid, "Mathe", "schriftlich", d, grade=2.0, scheduled_event_id=eid)
    assert cockpit.aggregate_comparison(conn, uid) is None


def test_aggregate_comparison_returns_mean_delta(conn, uid):
    dates = ["2026-02-15", "2026-03-15", "2026-04-15"]
    for i, d in enumerate(dates):
        _seed_test_and_attempt(conn, uid, "Mathe", f"2026-0{1+i}-25T10:00:00Z", note_value=3)
        eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", d, topics=[])
        assessments_repo.create(conn, uid, "Mathe", "schriftlich", d, grade=2.0, scheduled_event_id=eid)
    agg = cockpit.aggregate_comparison(conn, uid)
    assert agg is not None
    assert agg.count == 3
    assert agg.avg_delta == pytest.approx(-1.0)  # real 2 - app 3 = -1

import json

import pytest

from school_test_engine.error_book.queries import list_open_entries, count_open
from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import (
    connect, run_migrations, users_repo, attempts_repo,
)


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


def _import_one_question_test(conn, uid, subject: str = "Mathe", topic: str = "Bruchrechnung"):
    payload = {
        "schema_version": 1,
        "title": "T1",
        "subject": subject,
        "grade": 8,
        "school_type": "Realschule",
        "questions": [
            {
                "id": "q1",
                "type": "single_choice",
                "topic": topic,
                "difficulty": "mittel",
                "points": 2,
                "prompt": f"Frage zu {topic}?",
                "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                "correct": ["a"],
            },
        ],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (test_id,)
    ).fetchone()["id"]
    return test_id, qid


def _run_attempt(conn, uid, test_id, qid, *, is_correct: int, points: int = 2):
    """Helper: laufender Attempt, eine Antwort, finish."""
    attempt_id = attempts_repo.start_attempt(conn, test_id, points, uid)
    attempts_repo.upsert_answer(
        conn, attempt_id, qid, response=["a" if is_correct else "b"],
        points_earned=(points if is_correct else 0.0), is_correct=bool(is_correct),
    )
    attempts_repo.finish_attempt(
        conn,
        attempt_id,
        points_earned=(points if is_correct else 0.0),
        percent=(100.0 if is_correct else 0.0),
        note=1 if is_correct else 6,
    )
    return attempt_id


def test_one_wrong_answer_appears_in_book(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)

    entries = list_open_entries(conn, uid)
    assert len(entries) == 1
    assert entries[0].question_id == qid
    assert entries[0].subject == "Mathe"
    assert entries[0].topic == "Bruchrechnung"
    assert entries[0].wrong_count == 1
    assert entries[0].consecutive_correct == 0


def test_wrong_then_right_stays_with_streak_one(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    _run_attempt(conn, uid, test_id, qid, is_correct=1)
    entries = list_open_entries(conn, uid)
    assert len(entries) == 1
    assert entries[0].consecutive_correct == 1


def test_wrong_then_two_right_is_evicted(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    _run_attempt(conn, uid, test_id, qid, is_correct=1)
    _run_attempt(conn, uid, test_id, qid, is_correct=1)
    assert list_open_entries(conn, uid) == []


def test_wrong_right_wrong_breaks_streak(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    _run_attempt(conn, uid, test_id, qid, is_correct=1)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    entries = list_open_entries(conn, uid)
    assert len(entries) == 1
    assert entries[0].consecutive_correct == 0


def test_wrong_only_in_is_study_test_does_not_count(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    # Forciere is_study=1
    conn.execute("UPDATE tests SET is_study = 1 WHERE id = ?", (test_id,))
    conn.commit()
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    assert list_open_entries(conn, uid) == []


def test_eviction_via_err_copy(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    # Simuliere Kopie über err:-ext_id (zweiter Test, eine Frage, ext_id pointing to qid)
    copy_test_id = _import_one_question_test(conn, uid)[0]
    copy_qid = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (copy_test_id,)
    ).fetchone()["id"]
    conn.execute("UPDATE tests SET is_study = 1 WHERE id = ?", (copy_test_id,))
    conn.execute("UPDATE questions SET ext_id = ? WHERE id = ?", (f"err:{qid}", copy_qid))
    conn.commit()
    # 2× richtig in der Kopie → Original wird evicted
    _run_attempt(conn, uid, copy_test_id, copy_qid, is_correct=1)
    _run_attempt(conn, uid, copy_test_id, copy_qid, is_correct=1)
    assert list_open_entries(conn, uid) == []


def test_subject_filter(conn, uid):
    test_m, qid_m = _import_one_question_test(conn, uid, subject="Mathe")
    test_e, qid_e = _import_one_question_test(conn, uid, subject="Englisch")
    _run_attempt(conn, uid, test_m, qid_m, is_correct=0)
    _run_attempt(conn, uid, test_e, qid_e, is_correct=0)
    assert {e.question_id for e in list_open_entries(conn, uid, subject="Mathe")} == {qid_m}
    assert {e.question_id for e in list_open_entries(conn, uid, subject="Englisch")} == {qid_e}


def test_ordering_wrong_count_desc(conn, uid):
    t1, q1 = _import_one_question_test(conn, uid, topic="A")
    t2, q2 = _import_one_question_test(conn, uid, topic="B")
    # q1: 3× falsch, q2: 1× falsch
    for _ in range(3):
        _run_attempt(conn, uid, t1, q1, is_correct=0)
    _run_attempt(conn, uid, t2, q2, is_correct=0)
    entries = list_open_entries(conn, uid)
    assert [e.question_id for e in entries] == [q1, q2]


def test_count_open_per_subject(conn, uid):
    t1, q1 = _import_one_question_test(conn, uid, subject="Mathe")
    t2, q2 = _import_one_question_test(conn, uid, subject="Englisch")
    _run_attempt(conn, uid, t1, q1, is_correct=0)
    _run_attempt(conn, uid, t2, q2, is_correct=0)
    assert count_open(conn, uid) == {"Mathe": 1, "Englisch": 1}


def test_prompt_excerpt_truncates_at_80(conn, uid):
    # Frage mit langem Prompt
    long_prompt = "A" * 200
    payload = {
        "schema_version": 1,
        "title": "T", "subject": "Mathe", "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": "X", "difficulty": "mittel",
            "points": 1, "prompt": long_prompt,
            "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "correct": ["a"],
        }],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    entries = list_open_entries(conn, uid)
    assert len(entries[0].prompt_excerpt) <= 80
    assert entries[0].prompt_excerpt.endswith("…")

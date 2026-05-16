import json

import pytest

from school_test_engine.error_book.builder import build_practice_test
from school_test_engine.error_book.queries import list_open_entries
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


def _make_payload(title="T", subject="Mathe"):
    return {
        "schema_version": 1,
        "title": title, "subject": subject, "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": "Bruchrechnung",
            "difficulty": "mittel", "points": 2, "prompt": "Was ist 1/2 + 1/3?",
            "choices": [{"id": "a", "text": "5/6"}, {"id": "b", "text": "1/5"}],
            "correct": ["a"],
        }],
    }


def _answer(conn, uid, test_id, qid, correct: bool):
    points = 2 if correct else 0
    aid = attempts_repo.start_attempt(conn, test_id, 2, uid)
    attempts_repo.upsert_answer(
        conn, aid, qid,
        response=["a"] if correct else ["b"],
        points_earned=points, is_correct=correct,
    )
    attempts_repo.finish_attempt(conn, aid, float(points), 100.0 if correct else 0.0, 1 if correct else 6)


def test_full_loop_wrong_then_two_correct_via_practice_evicts(conn):
    uid = users_repo.create_user(conn, "Clemens", "🧒")

    # Schritt 1: regulären Test importieren, falsch beantworten
    orig_test = import_from_string(conn, json.dumps(_make_payload()), user_id=uid)
    orig_qid = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (orig_test,)
    ).fetchone()["id"]
    _answer(conn, uid, orig_test, orig_qid, correct=False)

    # Schritt 2: Frage ist im Heft
    assert len(list_open_entries(conn, uid)) == 1

    # Schritt 3: Fehler-Übungs-Test bauen
    practice_test = build_practice_test(conn, uid, subject="Mathe")
    assert practice_test is not None
    practice_qid = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (practice_test,)
    ).fetchone()["id"]
    assert practice_qid != orig_qid

    # Schritt 4: 1× richtig in der Kopie — bleibt im Heft mit streak=1
    _answer(conn, uid, practice_test, practice_qid, correct=True)
    entries = list_open_entries(conn, uid)
    assert len(entries) == 1
    assert entries[0].consecutive_correct == 1

    # Schritt 5: erneut bauen → Resume-Pfad nicht möglich (Attempt finished),
    # neuer Übungs-Test darf gebaut werden
    practice_test_2 = build_practice_test(conn, uid, subject="Mathe")
    assert practice_test_2 != practice_test
    practice_qid_2 = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (practice_test_2,)
    ).fetchone()["id"]
    # Schritt 6: 2. richtige Antwort → evicted
    _answer(conn, uid, practice_test_2, practice_qid_2, correct=True)
    assert list_open_entries(conn, uid) == []

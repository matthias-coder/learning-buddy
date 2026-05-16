import json

import pytest

from school_test_engine.error_book.builder import has_open_errors
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


def _import_and_fail(conn, uid, subject: str = "Mathe"):
    payload = {
        "schema_version": 1,
        "title": "T", "subject": subject, "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": "X", "difficulty": "mittel",
            "points": 2, "prompt": "P",
            "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "correct": ["a"],
        }],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
    aid = attempts_repo.start_attempt(conn, test_id, 2, uid)
    attempts_repo.upsert_answer(
        conn, aid, qid, response=["b"], points_earned=0.0, is_correct=False
    )
    attempts_repo.finish_attempt(conn, aid, 0.0, 0.0, 6)


def test_has_open_errors_false_on_empty(conn, uid):
    assert has_open_errors(conn, uid) is False
    assert has_open_errors(conn, uid, subject="Mathe") is False


def test_has_open_errors_true_after_fail(conn, uid):
    _import_and_fail(conn, uid, subject="Mathe")
    assert has_open_errors(conn, uid) is True
    assert has_open_errors(conn, uid, subject="Mathe") is True
    assert has_open_errors(conn, uid, subject="Englisch") is False


from school_test_engine.error_book.builder import _root_question_id


class _Row(dict):
    def __getitem__(self, k):
        return super().__getitem__(k) if k in self else None


def test_root_question_id_direct():
    row = _Row(id=42, ext_id="q1")
    assert _root_question_id(row) == 42


def test_root_question_id_from_err_copy():
    row = _Row(id=99, ext_id="err:42")
    assert _root_question_id(row) == 42


def test_root_question_id_handles_none_ext_id():
    row = _Row(id=42, ext_id=None)
    assert _root_question_id(row) == 42


def test_root_question_id_ignores_other_prefixes():
    row = _Row(id=42, ext_id="dq1")
    assert _root_question_id(row) == 42


from school_test_engine.error_book.builder import build_practice_test


def test_build_practice_returns_none_when_no_errors(conn, uid):
    assert build_practice_test(conn, uid, subject="Mathe") is None


def test_build_practice_creates_is_study_test_with_err_ext_id(conn, uid):
    _import_and_fail(conn, uid, subject="Mathe")
    # Hole root_qid
    root_qid = conn.execute(
        "SELECT a.question_id AS qid FROM answers a "
        "JOIN attempts att ON att.id = a.attempt_id "
        "WHERE a.is_correct = 0 LIMIT 1"
    ).fetchone()["qid"]

    test_id = build_practice_test(conn, uid, subject="Mathe")
    assert test_id is not None

    row = conn.execute(
        "SELECT subject, is_study, title, description FROM tests WHERE id = ?",
        (test_id,),
    ).fetchone()
    assert row["subject"] == "Mathe"
    assert row["is_study"] == 1
    assert row["title"].startswith("Fehler-Übung – Mathe – ")
    assert row["description"] == "Wiederholung von Fragen, die noch nicht sitzen."

    copies = conn.execute(
        "SELECT ext_id FROM questions WHERE test_id = ?", (test_id,)
    ).fetchall()
    assert len(copies) == 1
    assert copies[0]["ext_id"] == f"err:{root_qid}"


def test_build_practice_caps_at_limit(conn, uid):
    # 12 falsche Fragen importieren
    for i in range(12):
        payload = {
            "schema_version": 1,
            "title": f"T{i}", "subject": "Mathe", "grade": 8, "school_type": "Realschule",
            "questions": [{
                "id": "q1", "type": "single_choice", "topic": f"T{i}",
                "difficulty": "mittel", "points": 1, "prompt": f"P{i}",
                "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                "correct": ["a"],
            }],
        }
        test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
        qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
        aid = attempts_repo.start_attempt(conn, test_id, 1, uid)
        attempts_repo.upsert_answer(conn, aid, qid, response=["b"], points_earned=0.0, is_correct=False)
        attempts_repo.finish_attempt(conn, aid, 0.0, 0.0, 6)

    practice_id = build_practice_test(conn, uid, subject="Mathe", limit=10)
    n_copies = conn.execute(
        "SELECT COUNT(*) AS n FROM questions WHERE test_id = ?", (practice_id,)
    ).fetchone()["n"]
    assert n_copies == 10


def test_build_practice_flattens_chain(conn, uid):
    # Frage falsch → Kopie A baut sich (err:qid) → Kopie A wird wieder falsch beantwortet
    # → bauen wir nochmal: neue Kopie B sollte ext_id err:{root}, NICHT err:{copy_a}
    _import_and_fail(conn, uid, subject="Mathe")
    root_qid = conn.execute(
        "SELECT a.question_id AS qid FROM answers a "
        "JOIN attempts att ON att.id = a.attempt_id "
        "WHERE a.is_correct = 0 LIMIT 1"
    ).fetchone()["qid"]

    practice_1 = build_practice_test(conn, uid, subject="Mathe")
    copy_a_qid = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (practice_1,)
    ).fetchone()["id"]
    # Antwort falsch auf die Kopie A
    aid = attempts_repo.start_attempt(conn, practice_1, 1, uid)
    attempts_repo.upsert_answer(conn, aid, copy_a_qid, response=["b"], points_earned=0.0, is_correct=False)
    attempts_repo.finish_attempt(conn, aid, 0.0, 0.0, 6)

    # Eintrag ist immer noch offen → wieder bauen
    practice_2 = build_practice_test(conn, uid, subject="Mathe")
    assert practice_2 != practice_1  # neuer Test, weil practice_1 schon completed ist
    copy_b_ext = conn.execute(
        "SELECT ext_id FROM questions WHERE test_id = ?", (practice_2,)
    ).fetchone()["ext_id"]
    assert copy_b_ext == f"err:{root_qid}", "Kette muss flach bleiben"


def test_build_practice_resumes_open_attempt(conn, uid):
    _import_and_fail(conn, uid, subject="Mathe")
    test_id_1 = build_practice_test(conn, uid, subject="Mathe")
    # Starte Attempt, finish NICHT
    attempts_repo.start_attempt(conn, test_id_1, 2, uid)

    # Erneuter Aufruf darf KEINEN neuen Test bauen, sondern den existierenden zurückgeben
    test_id_2 = build_practice_test(conn, uid, subject="Mathe")
    assert test_id_2 == test_id_1


def test_build_practice_copies_payload_fields(conn, uid):
    payload = {
        "schema_version": 1,
        "title": "T", "subject": "Mathe", "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": "Bruchrechnung",
            "difficulty": "schwer", "points": 5,
            "prompt": "Was ist 1/2 + 1/3?",
            "prompt_math": "\\frac{1}{2} + \\frac{1}{3}",
            "explanation": "Auf gemeinsamen Nenner bringen.",
            "choices": [{"id": "a", "text": "5/6"}, {"id": "b", "text": "1/5"}],
            "correct": ["a"],
        }],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
    aid = attempts_repo.start_attempt(conn, test_id, 5, uid)
    attempts_repo.upsert_answer(conn, aid, qid, response=["b"], points_earned=0.0, is_correct=False)
    attempts_repo.finish_attempt(conn, aid, 0.0, 0.0, 6)

    practice_id = build_practice_test(conn, uid, subject="Mathe")
    copy = conn.execute(
        "SELECT type, topic, difficulty, points, prompt, prompt_math, payload, explanation, position "
        "FROM questions WHERE test_id = ?", (practice_id,)
    ).fetchone()
    assert copy["type"] == "single_choice"
    assert copy["topic"] == "Bruchrechnung"
    assert copy["difficulty"] == "schwer"
    assert copy["points"] == 5
    assert copy["prompt"] == "Was ist 1/2 + 1/3?"
    assert copy["prompt_math"] == "\\frac{1}{2} + \\frac{1}{3}"
    assert copy["explanation"] == "Auf gemeinsamen Nenner bringen."
    assert copy["position"] == 0

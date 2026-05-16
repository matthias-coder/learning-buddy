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

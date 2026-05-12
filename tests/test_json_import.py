import json
from pathlib import Path

import pytest

from school_test_engine.importer.json_import import ImportError, import_from_string
from school_test_engine.models.test import Test
from school_test_engine.storage import connect, run_migrations

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_import_mathe_example(conn):
    source = (EXAMPLES / "mathe-lineare-gleichungen.json").read_text(encoding="utf-8")
    test_id = import_from_string(conn, source, user_id=1)
    assert test_id == 1
    row = conn.execute("SELECT * FROM tests WHERE id = ?", (test_id,)).fetchone()
    assert row["subject"] == "Mathe"
    questions = conn.execute(
        "SELECT * FROM questions WHERE test_id = ? ORDER BY position", (test_id,)
    ).fetchall()
    assert len(questions) == 5


def test_import_englisch_example(conn):
    source = (EXAMPLES / "englisch-irregular-verbs.json").read_text(encoding="utf-8")
    test_id = import_from_string(conn, source, user_id=1)
    row = conn.execute("SELECT * FROM tests WHERE id = ?", (test_id,)).fetchone()
    assert row["subject"] == "Englisch"


def test_invalid_json_gives_helpful_error(conn):
    with pytest.raises(ImportError) as exc:
        import_from_string(conn, "{ this is not JSON }", user_id=1)
    assert "JSON" in str(exc.value)


def test_missing_required_field_names_field(conn):
    bad = {
        "schema_version": 1,
        "subject": "Mathe",
        "grade": 8,
        "questions": [],
    }
    with pytest.raises(ImportError) as exc:
        import_from_string(conn, json.dumps(bad), user_id=1)
    msg = str(exc.value)
    assert "title" in msg


def test_correct_id_must_exist_in_choices(conn):
    bad_test = {
        "schema_version": 1,
        "title": "Broken",
        "subject": "Mathe",
        "grade": 8,
        "questions": [
            {
                "id": "q1",
                "type": "single_choice",
                "topic": "x",
                "difficulty": "leicht",
                "points": 1,
                "prompt": "?",
                "choices": [
                    {"id": "a", "text": "x"},
                    {"id": "b", "text": "y"},
                ],
                "correct": ["c"],
            }
        ],
    }
    with pytest.raises(ImportError) as exc:
        import_from_string(conn, json.dumps(bad_test), user_id=1)
    assert "correct" in str(exc.value)


def test_duplicate_question_ids_rejected(conn):
    bad_test = {
        "schema_version": 1,
        "title": "Dupes",
        "subject": "Mathe",
        "grade": 8,
        "questions": [
            {
                "id": "q1", "type": "single_choice", "topic": "x", "difficulty": "leicht",
                "points": 1, "prompt": "?",
                "choices": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}],
                "correct": ["a"],
            },
            {
                "id": "q1", "type": "single_choice", "topic": "x", "difficulty": "leicht",
                "points": 1, "prompt": "?",
                "choices": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}],
                "correct": ["a"],
            },
        ],
    }
    with pytest.raises(ImportError) as exc:
        import_from_string(conn, json.dumps(bad_test), user_id=1)
    assert "mehrfach" in str(exc.value).lower() or "q1" in str(exc.value)


def test_extra_field_rejected(conn):
    # Catch typos like "promt" instead of "prompt"
    bad_test = {
        "schema_version": 1,
        "title": "Typo",
        "subject": "Mathe",
        "grade": 8,
        "questions": [
            {
                "id": "q1", "type": "single_choice", "topic": "x", "difficulty": "leicht",
                "points": 1, "prompt": "?", "promt": "typo!",
                "choices": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}],
                "correct": ["a"],
            }
        ],
    }
    with pytest.raises(ImportError) as exc:
        import_from_string(conn, json.dumps(bad_test), user_id=1)
    assert "promt" in str(exc.value).lower() or "extra" in str(exc.value).lower()


def test_notenschluessel_default_applied(conn):
    source = (EXAMPLES / "mathe-lineare-gleichungen.json").read_text(encoding="utf-8")
    test = Test.model_validate_json(source)
    schluessel = test.effective_notenschluessel()
    assert schluessel[1] == 92
    assert schluessel[6] == 0

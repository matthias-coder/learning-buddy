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
    assert "Tippfehler" in str(exc.value)


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


# --- Bug #4: tolerant parsing + friendly German errors -----------------------

def _valid_source() -> str:
    return (EXAMPLES / "mathe-lineare-gleichungen.json").read_text(encoding="utf-8")


def test_import_strips_json_code_fence(conn):
    source = "```json\n" + _valid_source() + "\n```"
    assert import_from_string(conn, source, user_id=1) > 0


def test_import_strips_plain_code_fence(conn):
    source = "```\n" + _valid_source() + "\n```"
    assert import_from_string(conn, source, user_id=1) > 0


def test_import_ignores_prose_before_and_after(conn):
    source = "Hier ist dein Test:\n\n" + _valid_source() + "\n\nViel Erfolg beim Lernen!"
    assert import_from_string(conn, source, user_id=1) > 0


def test_import_fence_with_prose(conn):
    source = "Klar!\n```json\n" + _valid_source() + "\n```\nSag Bescheid, wenn du mehr brauchst."
    assert import_from_string(conn, source, user_id=1) > 0


def test_no_json_gives_friendly_german_message(conn):
    with pytest.raises(ImportError) as exc:
        import_from_string(conn, "Das ist nur Text ohne Test.", user_id=1)
    msg = str(exc.value)
    assert "sieht nicht nach einem Test aus" in msg
    assert "Expecting" not in msg and "Zeile 1, Spalte 1" not in msg


def test_json_array_is_not_a_test(conn):
    with pytest.raises(ImportError) as exc:
        import_from_string(conn, "[1, 2, 3]", user_id=1)
    assert "sieht nicht nach einem Test aus" in str(exc.value)


def test_broken_json_gives_german_message(conn):
    with pytest.raises(ImportError) as exc:
        import_from_string(conn, '{"title": "x", ', user_id=1)
    msg = str(exc.value)
    assert "Expecting" not in msg and "Unterminated" not in msg


def test_missing_field_message_is_german_and_names_question(conn):
    data = json.loads(_valid_source())
    del data["questions"][2]["prompt"]
    with pytest.raises(ImportError) as exc:
        import_from_string(conn, json.dumps(data), user_id=1)
    msg = str(exc.value)
    assert "Frage 3" in msg
    assert "„prompt“" in msg
    assert "fehlt" in msg
    assert "Field required" not in msg


def test_missing_top_level_field_message_is_german(conn):
    data = json.loads(_valid_source())
    del data["title"]
    with pytest.raises(ImportError) as exc:
        import_from_string(conn, json.dumps(data), user_id=1)
    msg = str(exc.value)
    assert "„title“" in msg and "fehlt" in msg
    assert "Field required" not in msg


def test_wrong_value_message_has_no_english_pydantic_text(conn):
    data = json.loads(_valid_source())
    data["questions"][0]["difficulty"] = "extrem"
    with pytest.raises(ImportError) as exc:
        import_from_string(conn, json.dumps(data), user_id=1)
    msg = str(exc.value)
    assert "Input should be" not in msg
    assert "Frage 1" in msg and "„difficulty“" in msg


def test_binary_file_gives_german_message(conn, tmp_path):
    from school_test_engine.importer.json_import import import_from_file
    p = tmp_path / "bild.json"
    p.write_bytes(b"\xff\xfe\x00\x80\x81\x82")
    with pytest.raises(ImportError) as exc:
        import_from_file(conn, p, user_id=1)
    assert "Textdatei" in str(exc.value)

"""Duplicate-import detection (#12a)."""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from school_test_engine.importer.json_import import (
    find_duplicate,
    find_duplicate_in_file,
    import_from_string,
)
from school_test_engine.storage import connect, run_migrations, users_repo

TEST = {
    "schema_version": 1, "title": "Brüche", "subject": "Mathe", "grade": 8,
    "school_type": "Realschule",
    "questions": [{
        "id": "q1", "type": "short_answer", "topic": "t", "difficulty": "leicht",
        "points": 1, "prompt": "1+1?", "accepted_answers": ["2"],
    }],
}


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "t.sqlite3")
    run_migrations(c)
    yield c
    c.close()


def test_no_duplicate_initially(conn):
    uid = users_repo.create_user(conn, "A", "x")
    assert find_duplicate(conn, json.dumps(TEST), uid) is None


def test_detects_identical_test_despite_formatting(conn):
    uid = users_repo.create_user(conn, "A", "x")
    tid = import_from_string(conn, json.dumps(TEST), uid)
    pretty = "```json\n" + json.dumps(TEST, indent=4, ensure_ascii=False) + "\n```"
    assert find_duplicate(conn, pretty, uid) == tid


def test_changed_test_is_no_duplicate(conn):
    uid = users_repo.create_user(conn, "A", "x")
    import_from_string(conn, json.dumps(TEST), uid)
    other = json.loads(json.dumps(TEST))
    other["questions"][0]["prompt"] = "2+2?"
    assert find_duplicate(conn, json.dumps(other), uid) is None


def test_duplicate_is_per_user(conn):
    a = users_repo.create_user(conn, "A", "x")
    b = users_repo.create_user(conn, "B", "x")
    import_from_string(conn, json.dumps(TEST), a)
    assert find_duplicate(conn, json.dumps(TEST), b) is None


def test_invalid_input_returns_none(conn):
    uid = users_repo.create_user(conn, "A", "x")
    assert find_duplicate(conn, "kein json", uid) is None
    assert find_duplicate(conn, '{"title": "x"}', uid) is None


def test_find_duplicate_in_file(conn, tmp_path):
    uid = users_repo.create_user(conn, "A", "x")
    tid = import_from_string(conn, json.dumps(TEST), uid)
    f = tmp_path / "t.json"
    f.write_text(json.dumps(TEST), encoding="utf-8")
    assert find_duplicate_in_file(conn, f, uid) == tid
    assert find_duplicate_in_file(conn, tmp_path / "missing.json", uid) is None


def test_import_function_still_allows_duplicates(conn):
    uid = users_repo.create_user(conn, "A", "x")
    a = import_from_string(conn, json.dumps(TEST), uid)
    b = import_from_string(conn, json.dumps(TEST), uid)
    assert a != b


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Win:
    def __init__(self, uid):
        self.active_user_id = uid


def _count(conn):
    return conn.execute("SELECT COUNT(*) AS n FROM tests").fetchone()["n"]


@pytest.mark.parametrize("answer,expected", [
    (QMessageBox.StandardButton.No, 1),
    (QMessageBox.StandardButton.Yes, 2),
])
def test_wizard_asks_before_duplicate_paste_import(app, conn, monkeypatch, answer, expected):
    from school_test_engine.ui.pages.import_wizard import ImportPage
    uid = users_repo.create_user(conn, "A", "x")
    import_from_string(conn, json.dumps(TEST), uid)
    asked = []

    def _question(parent, title, text, *a, **k):
        asked.append(text)
        return answer
    monkeypatch.setattr(QMessageBox, "question", staticmethod(_question))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    page = ImportPage(_Win(uid), conn)
    page.paste_edit.setPlainText(json.dumps(TEST))
    page._import_text()
    assert asked == ["Diesen Test gibt es schon in der Bibliothek. Trotzdem noch einmal importieren?"]
    assert _count(conn) == expected

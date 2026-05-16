import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import pytest

from PySide6.QtWidgets import QApplication

from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import connect, run_migrations, users_repo, attempts_repo
from school_test_engine.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


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


def _import_and_fail(conn, uid, subject="Mathe"):
    payload = {
        "schema_version": 1,
        "title": "T", "subject": subject, "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": "X",
            "difficulty": "mittel", "points": 2, "prompt": "P",
            "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "correct": ["a"],
        }],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
    aid = attempts_repo.start_attempt(conn, test_id, 2, uid)
    attempts_repo.upsert_answer(conn, aid, qid, response=["b"], points_earned=0.0, is_correct=False)
    attempts_repo.finish_attempt(conn, aid, 0.0, 0.0, 6)


def test_show_error_book_swaps_to_page(qt_app, conn, uid):
    window = MainWindow(conn)
    window.set_active_user(uid)
    window.show_error_book()
    assert window.stack.currentWidget() is window.error_book_page


def test_start_error_book_practice_routes_to_runner(qt_app, conn, uid):
    _import_and_fail(conn, uid)
    window = MainWindow(conn)
    window.set_active_user(uid)
    window.start_error_book_practice("Mathe")
    assert window.stack.currentWidget() is window.runner_page


def test_start_error_book_practice_no_errors_does_not_route(qt_app, conn, uid, monkeypatch):
    """0 offene Fehler im Fach → keine Runner-Navigation, ggf. Info-Box."""
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    window = MainWindow(conn)
    window.set_active_user(uid)
    current_before = window.stack.currentWidget()
    window.start_error_book_practice("Mathe")
    assert window.stack.currentWidget() is current_before

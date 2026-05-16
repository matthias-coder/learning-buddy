import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
from PySide6.QtWidgets import QApplication

from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import connect, run_migrations, users_repo, attempts_repo
from school_test_engine.ui.pages.error_book import ErrorBookPage


class _MockWindow:
    def __init__(self, conn, uid):
        self.conn = conn
        self.active_user_id = uid
        self.started_practice = None

    def start_error_book_practice(self, subject):
        self.started_practice = subject


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    return app


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


def _import_and_fail(conn, uid, subject="Mathe", topic="X"):
    payload = {
        "schema_version": 1,
        "title": "T", "subject": subject, "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": topic,
            "difficulty": "mittel", "points": 2, "prompt": f"Frage {topic}",
            "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "correct": ["a"],
        }],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
    aid = attempts_repo.start_attempt(conn, test_id, 2, uid)
    attempts_repo.upsert_answer(conn, aid, qid, response=["b"], points_earned=0.0, is_correct=False)
    attempts_repo.finish_attempt(conn, aid, 0.0, 0.0, 6)


def test_page_empty_state_shows_when_no_errors(qt_app, conn, uid):
    window = _MockWindow(conn, uid)
    page = ErrorBookPage(window, conn)
    page.show()
    page.reload()
    assert page.empty_label.isVisible()


def test_page_subject_pill_counts(qt_app, conn, uid):
    _import_and_fail(conn, uid, subject="Mathe", topic="A")
    _import_and_fail(conn, uid, subject="Mathe", topic="B")
    _import_and_fail(conn, uid, subject="Englisch", topic="C")
    page = ErrorBookPage(_MockWindow(conn, uid), conn)
    page.reload()
    assert page._subject_buttons["Mathe"].text() == "Mathe · 2"
    assert page._subject_buttons["Englisch"].text() == "Englisch · 1"
    # Andere Fächer sind ungetargeted
    assert page._subject_buttons["Bio"].isEnabled() is False


def test_page_renders_entry_cards_for_active_subject(qt_app, conn, uid):
    _import_and_fail(conn, uid, subject="Mathe", topic="A")
    page = ErrorBookPage(_MockWindow(conn, uid), conn)
    page.reload()
    # 1 Card + 1 stretch in list_layout
    assert page._list_layout.count() >= 1


def test_page_per_subject_empty_state(qt_app, conn, uid):
    _import_and_fail(conn, uid, subject="Mathe", topic="A")
    page = ErrorBookPage(_MockWindow(conn, uid), conn)
    page.reload()
    # Wechsle aktiv zu einem leeren Fach
    page._current_subject = "Englisch"
    page.reload()
    # Page kehrt zu Mathe als default zurück, weil Englisch == 0
    assert page._current_subject == "Mathe"


def test_page_practice_button_count_caps_at_10(qt_app, conn, uid):
    for i in range(15):
        _import_and_fail(conn, uid, subject="Mathe", topic=f"T{i}")
    page = ErrorBookPage(_MockWindow(conn, uid), conn)
    page.reload()
    assert page.practice_button_count() == 10


def test_page_trigger_practice_calls_window(qt_app, conn, uid):
    _import_and_fail(conn, uid, subject="Mathe", topic="A")
    window = _MockWindow(conn, uid)
    page = ErrorBookPage(window, conn)
    page.reload()
    page.trigger_practice()
    assert window.started_practice == "Mathe"


def test_subject_switch_drops_old_subject_cards(qt_app, conn, uid):
    """Regression: nach _select_subject müssen alte Subject-Cards SOFORT
    aus dem Layout verschwinden (nicht erst nach Event-Loop-Tick).
    Sonst zeigt die Page kurz Mathe + Englisch-Cards übereinander."""
    _import_and_fail(conn, uid, subject="Mathe", topic="A")
    _import_and_fail(conn, uid, subject="Mathe", topic="B")
    _import_and_fail(conn, uid, subject="Englisch", topic="C")
    page = ErrorBookPage(_MockWindow(conn, uid), conn)
    page.reload()
    # Mathe default → 2 Cards + 1 Stretch im Layout
    assert page._list_layout.count() == 3
    page._select_subject("Englisch")
    # Nach Switch sollte Layout nur noch 1 Card + 1 Stretch enthalten,
    # NICHT 3 (2 alte Mathe + 1 neue Englisch).
    assert page._list_layout.count() == 2

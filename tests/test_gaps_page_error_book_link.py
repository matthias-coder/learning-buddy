import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.ui.pages.gaps import GapsPage


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


class _MockWindow:
    def __init__(self, conn, uid):
        self.conn = conn
        self.active_user_id = uid
        self.show_error_book_called = False

    def show_error_book(self):
        self.show_error_book_called = True


def test_gaps_page_has_footer_button_routing_to_error_book(qt_app, conn, uid):
    window = _MockWindow(conn, uid)
    page = GapsPage(window, conn)
    # Find the button by text
    buttons = page.findChildren(QPushButton)
    matching = [b for b in buttons if "Fehler nochmal" in b.text()]
    assert matching, "Footer-Button 'Fehler nochmal üben' fehlt"
    matching[0].click()
    assert window.show_error_book_called is True

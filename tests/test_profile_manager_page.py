import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from school_test_engine.storage import connect, run_migrations, users_repo


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    users_repo.create_user(c, "Clemens")
    yield c
    c.close()


class FakeWindow:
    def __init__(self, conn):
        self.conn = conn
        self.active_user_id = None
        self.back_calls = 0

    def _navigate_back(self):
        self.back_calls += 1


def test_back_button_navigates_back(app, conn):
    from school_test_engine.ui.pages.profile_manager import ProfileManagerPage

    win = FakeWindow(conn)
    page = ProfileManagerPage(win, conn)
    page.show_for("picker")
    assert page.back_btn.text() == "← Zurück"
    page.back_btn.click()
    assert win.back_calls == 1

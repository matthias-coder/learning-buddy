"""Bugreport 1.0.1 #12: profile name limits, duplicate names, birthday reset label."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from school_test_engine.storage import connect, run_migrations, users_repo


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


@pytest.fixture
def messages(monkeypatch):
    calls = []
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *a, **kw: calls.append(a[1:]) or QMessageBox.StandardButton.Ok),
    )
    yield calls


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test.sqlite3")
    run_migrations(c)
    users_repo.create_user(c, "Anna")
    yield c
    c.close()


class FakeWindow:
    def __init__(self, conn):
        self.conn = conn
        self.active_user_id = None
        self.back_calls = 0

    def _navigate_back(self):
        self.back_calls += 1


def _page(conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    win = FakeWindow(conn)
    return ProfileEditPage(win, conn), win


def _names(conn):
    return [u["name"] for u in users_repo.list_users(conn)]


def test_name_length_is_limited(app, conn):
    page, _ = _page(conn)
    page.show_for(None, "picker")
    assert 0 < page.name_edit.maxLength() <= 40


def test_duplicate_name_is_rejected_case_insensitive(app, conn, messages):
    page, win = _page(conn)
    page.show_for(None, "picker")
    page.name_edit.setText(" anna ")
    page._save()
    assert [n.casefold() for n in _names(conn)].count("anna") == 1
    assert win.back_calls == 0
    assert any("Anna" in " ".join(map(str, m)) or "anna" in " ".join(map(str, m)) for m in messages)


def test_saving_existing_profile_keeps_its_own_name(app, conn, messages):
    uid = int(users_repo.list_users(conn)[0]["id"])
    page, win = _page(conn)
    page.show_for(uid, "manager")
    page._save()
    assert win.back_calls == 1


def test_birthday_reset_button_is_not_called_delete(app, conn):
    page, _ = _page(conn)
    page.show_for(None, "picker")
    texts = [b.text() for b in page.findChildren(QPushButton) if b.isVisibleTo(page)]
    assert "Zurücksetzen" in texts
    assert "Löschen" not in texts  # profile delete is hidden for a new profile


def test_long_name_is_elided_in_manager_row(app, conn):
    from school_test_engine.ui.pages.profile_manager import _ProfileRow
    users_repo.create_user(conn, "X" * 300)
    row_data = [u for u in users_repo.list_users(conn) if u["name"].startswith("X")][0]
    row = _ProfileRow(row_data, on_edit=lambda: None, on_delete=lambda: None, is_active=False)
    assert row.sizeHint().width() < 1000

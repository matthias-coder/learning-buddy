import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from school_test_engine.storage import connect, run_migrations, users_repo


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
    """Headless tests can't dismiss modal QMessageBox calls — patch them out."""
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes))


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


class FakeWindow:
    def __init__(self, conn):
        self.conn = conn
        self.active_user_id = None
        self.shown = []

    def show_profile_picker(self):
        self.shown.append("picker")

    def show_profile_manager(self, return_to: str = "picker"):
        self.shown.append(f"manager({return_to})")

    def show_menu(self):
        self.shown.append("menu")


def test_create_mode_empty_fields(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    p = ProfileEditPage(FakeWindow(conn), conn)
    p.show_for(user_id=None, return_to="picker")
    assert p.name_edit.text() == ""


def test_edit_mode_loads_existing_user(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    uid = users_repo.create_user(conn, "Bestand", "👤")
    users_repo.update_user(conn, uid, ai_style_briefing="Mein Stil")
    p = ProfileEditPage(FakeWindow(conn), conn)
    p.show_for(user_id=uid, return_to="manager")
    assert p.name_edit.text() == "Bestand"
    assert p.style_edit.toPlainText() == "Mein Stil"


def test_save_create_mode_creates_user(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    win = FakeWindow(conn)
    p = ProfileEditPage(win, conn)
    p.show_for(user_id=None, return_to="picker")
    p.name_edit.setText("NeuerUser")
    p._save()
    users = users_repo.list_users(conn)
    assert any(u["name"] == "NeuerUser" for u in users)
    assert win.shown == ["picker"]


def test_save_edit_mode_updates_user(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    uid = users_repo.create_user(conn, "Alt", "👤")
    win = FakeWindow(conn)
    p = ProfileEditPage(win, conn)
    p.show_for(user_id=uid, return_to="manager")
    p.name_edit.setText("Neu")
    p._save()
    row = users_repo.get_user(conn, uid)
    assert row["name"] == "Neu"
    assert win.shown == ["manager(manager)"]


def test_save_empty_name_does_not_create(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    win = FakeWindow(conn)
    p = ProfileEditPage(win, conn)
    p.show_for(user_id=None, return_to="picker")
    p.name_edit.setText("   ")
    n_before = len(users_repo.list_users(conn))
    p._save()
    n_after = len(users_repo.list_users(conn))
    assert n_after == n_before


def test_cancel_creates_nothing(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    win = FakeWindow(conn)
    p = ProfileEditPage(win, conn)
    p.show_for(user_id=None, return_to="picker")
    p.name_edit.setText("Cancelled")
    n_before = len(users_repo.list_users(conn))
    p._cancel()
    n_after = len(users_repo.list_users(conn))
    assert n_after == n_before
    assert win.shown == ["picker"]


def test_return_to_routes_correctly(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    for target, expected in [("picker", "picker"), ("manager", "manager(manager)"), ("menu", "menu")]:
        win = FakeWindow(conn)
        p = ProfileEditPage(win, conn)
        p.show_for(user_id=None, return_to=target)
        p.name_edit.setText(f"User-{target}")
        p._save()
        assert win.shown == [expected], f"target={target}: got {win.shown}"

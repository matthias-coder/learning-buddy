"""Phase 15: ProfileEditPage has an iCal-Feed-URL field that round-trips through users.ical_feed_url."""
from __future__ import annotations

import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from school_test_engine.storage import connect, run_migrations, users_repo


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
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
    def show_profile_manager(self, return_to="picker"):
        self.shown.append(f"manager({return_to})")
    def show_menu(self):
        self.shown.append("menu")


def test_field_persists_to_users_ical_feed_url(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    uid = users_repo.create_user(conn, name="Clemens")
    p = ProfileEditPage(FakeWindow(conn), conn)
    p.show_for(user_id=uid, return_to="manager")
    p.ical_feed_url_edit.setPlainText("https://start.schulportal.hessen.de/feed?t=abc")
    p._save()
    row = users_repo.get_user(conn, uid)
    assert row["ical_feed_url"] == "https://start.schulportal.hessen.de/feed?t=abc"


def test_field_loads_existing_url(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x.example/feed")
    p = ProfileEditPage(FakeWindow(conn), conn)
    p.show_for(user_id=uid, return_to="manager")
    assert p.ical_feed_url_edit.toPlainText() == "https://x.example/feed"


def test_field_clears_url_when_emptied(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x.example/feed")
    p = ProfileEditPage(FakeWindow(conn), conn)
    p.show_for(user_id=uid, return_to="manager")
    p.ical_feed_url_edit.setPlainText("")
    p._save()
    row = users_repo.get_user(conn, uid)
    assert row["ical_feed_url"] is None


def test_field_strips_whitespace_before_save(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    uid = users_repo.create_user(conn, name="Clemens")
    p = ProfileEditPage(FakeWindow(conn), conn)
    p.show_for(user_id=uid, return_to="manager")
    p.ical_feed_url_edit.setPlainText("   https://example.com/feed   \n")
    p._save()
    row = users_repo.get_user(conn, uid)
    assert row["ical_feed_url"] == "https://example.com/feed"


def test_reset_clears_field_in_create_mode(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    p = ProfileEditPage(FakeWindow(conn), conn)
    p.show_for(user_id=None, return_to="picker")
    assert p.ical_feed_url_edit.toPlainText() == ""


def test_field_rejects_non_https_url(app, conn, monkeypatch):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
        staticmethod(lambda *a, **kw: warnings.append(a) or QMessageBox.StandardButton.Ok))
    uid = users_repo.create_user(conn, name="Clemens")
    p = ProfileEditPage(FakeWindow(conn), conn)
    p.show_for(user_id=uid, return_to="manager")
    p.ical_feed_url_edit.setPlainText("ftp://nope.example/feed")
    p._save()
    row = users_repo.get_user(conn, uid)
    assert row["ical_feed_url"] is None
    assert len(warnings) == 1

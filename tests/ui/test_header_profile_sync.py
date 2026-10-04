"""Bugreport 1.0.1 #7: header chip must follow edits of the active profile,
and profile management must be reachable while logged in."""
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import run_migrations, users_repo


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    for name in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes))


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def window(conn):
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication
    from school_test_engine.ui.main_window import MainWindow
    uid = users_repo.create_user(conn, name="Anna")
    w = MainWindow(conn)
    w.set_active_user(uid)
    w.show()
    yield w
    w.close()
    w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def test_renaming_active_profile_updates_header_chip(window):
    window.show_profile_manager(return_to="menu")
    window.show_profile_edit(user_id=window.active_user_id, return_to="manager")
    window.profile_edit_page.name_edit.setText("Anna2")
    window.profile_edit_page.save_btn.click()
    assert window.header.chip.name.text() == "Anna2"


def test_logo_menu_offers_profile_management(window):
    labels = [a.text() for a in window.header._logo_menu._menu.actions()]
    assert "Profile verwalten" in labels


def test_profile_management_from_menu_returns_to_menu(window):
    window.show_profile_manager(return_to="menu")
    assert window.header.isVisible()
    window.profile_manager_page.back_btn.click()
    assert window._current[0] == "menu"

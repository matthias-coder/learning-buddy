from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.storage import (
    events_repo, run_migrations, users_repo,
)


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def test_banner_hidden_when_no_open_grades(conn):
    from school_test_engine.ui.main_window import MainWindow
    uid = users_repo.create_user(conn, name="T")
    win = MainWindow(conn)
    win.set_active_user(uid)
    # No past KAs → banner should NOT exist or be invisible
    banner = getattr(win.menu_page, "_open_grades_banner", None)
    assert banner is None or banner.isVisible() is False


def test_banner_visible_when_past_ka_without_grade(conn):
    from school_test_engine.ui.main_window import MainWindow
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klausur", "2026-04-01")
    win = MainWindow(conn)
    win.menu_page._today_override = date(2026, 5, 1)
    win.set_active_user(uid)
    win.menu_page.reload()
    assert win.menu_page._open_grades_banner is not None


def test_banner_count_reflects_db_state(conn):
    from school_test_engine.ui.main_window import MainWindow
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klausur", "2026-04-01")
    events_repo.create(conn, uid, "Englisch", "klausur", "2026-04-15")
    events_repo.create(conn, uid, "Bio", "test", "2026-04-20")
    win = MainWindow(conn)
    win.menu_page._today_override = date(2026, 5, 1)
    win.set_active_user(uid)
    win.menu_page.reload()
    banner = win.menu_page._open_grades_banner
    assert banner is not None
    assert "3 offene Noten" in banner._label.text()

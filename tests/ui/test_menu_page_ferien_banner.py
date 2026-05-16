from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.storage import (
    calendar_events_repo, run_migrations, users_repo,
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


class _StubWindow:
    def __init__(self, conn, uid):
        self.conn = conn
        self.active_user_id = uid

    # stubs for all methods MenuPage.reload() tries to connect to
    def show_library(self): pass
    def show_gaps(self): pass
    def show_history(self): pass
    def start_daily_five(self): pass
    def show_school_calendar(self): pass


def _open_menu(conn, uid, today):
    from school_test_engine.ui.pages.menu import MenuPage
    win = _StubWindow(conn, uid)
    page = MenuPage(win, today=today)
    page.reload()
    return page


def test_banner_renders_when_next_vacation_exists(conn):
    uid = users_repo.create_user(conn, name="C")
    calendar_events_repo.create(conn, user_id=uid, kind="ferien",
                                title="Herbstferien",
                                start_date="2026-10-19", end_date="2026-10-31")
    page = _open_menu(conn, uid, date(2026, 9, 26))
    assert page._ferien_banner is not None
    assert "Herbstferien" in page._ferien_banner._label.text()


def test_banner_hidden_when_no_vacation(conn):
    uid = users_repo.create_user(conn, name="C")
    page = _open_menu(conn, uid, date(2026, 5, 15))
    assert page._ferien_banner is None


def test_banner_refreshes_on_reload(conn):
    uid = users_repo.create_user(conn, name="C")
    page = _open_menu(conn, uid, date(2026, 5, 15))
    assert page._ferien_banner is None
    calendar_events_repo.create(conn, user_id=uid, kind="ferien",
                                title="Herbstferien",
                                start_date="2026-10-19", end_date="2026-10-31")
    page.reload()
    assert page._ferien_banner is not None

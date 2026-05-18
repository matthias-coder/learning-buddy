from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import run_migrations, users_repo


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


@pytest.fixture
def window(conn):
    from school_test_engine.ui.main_window import MainWindow
    uid = users_repo.create_user(conn, name="Test")
    w = MainWindow(conn)
    w.set_active_user(uid)
    return w


def test_navigate_initializes_empty_history(window):
    # set_active_user → show_menu; menu is root → history must be empty
    assert window._history == []


def test_navigate_to_grades_pushes_menu_onto_stack(window):
    window._navigate("grades")
    assert len(window._history) == 1
    assert window._history[0][0] == "menu"

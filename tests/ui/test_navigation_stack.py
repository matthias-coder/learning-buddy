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
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from school_test_engine.ui.main_window import MainWindow
    uid = users_repo.create_user(conn, name="Test")
    w = MainWindow(conn)
    w.set_active_user(uid)
    w.show()
    w.raise_()
    w.activateWindow()
    QTest.qWaitForWindowExposed(w)
    yield w
    w.close()
    w.deleteLater()
    # processEvents() alone does not run DeferredDelete outside an event loop;
    # a surviving QWebEngineView crashes at interpreter exit.
    from PySide6.QtCore import QEvent
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def test_navigate_initializes_empty_history(window):
    # set_active_user → show_menu; menu is root → history must be empty
    assert window._history == []


def test_navigate_to_grades_pushes_menu_onto_stack(window):
    window._navigate("grades")
    assert len(window._history) == 1
    assert window._history[0][0] == "menu"


def test_navigate_back_pops_to_previous_target(window):
    window._navigate("grades")
    window._navigate("assessment_edit")
    assert len(window._history) == 2
    window._navigate_back()
    assert len(window._history) == 1
    assert window._current[0] == "grades"


def test_navigate_to_menu_clears_history(window):
    window._navigate("grades")
    window._navigate("assessment_edit")
    window._navigate("menu")
    assert window._history == []
    assert window._current[0] == "menu"


def test_navigate_runner_does_not_push_to_stack(window):
    window._navigate("grades")
    before = len(window._history)
    window._navigate("runner", action="raw")
    # runner does NOT push grades onto stack
    assert len(window._history) == before


def test_navigate_dedupes_when_target_equals_current(window):
    # Clicking "Grades" twice in the logo menu should not stack two 'grades'.
    window._navigate("grades")
    window._navigate("grades")
    # menu was pushed once when first transitioning away; second call is dedup
    assert window._history == [("menu", {})]


def test_navigate_back_on_empty_stack_is_noop(window):
    # Fresh start: history empty; back should not crash
    window._navigate_back()
    assert window._current[0] == "menu"


def test_back_button_visibility_binds_to_history_depth(window):
    # Fresh / menu → not visible
    assert window.header.back_button.isVisible() is False
    # Push something → visible
    window._navigate("grades")
    assert window.header.back_button.isVisible() is True
    # Back to root → not visible
    window._navigate("menu")
    assert window.header.back_button.isVisible() is False


def test_esc_shortcut_triggers_back_when_visible(window):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window._navigate("grades")
    assert window._current[0] == "grades"
    # Simulate Esc key
    QTest.keyClick(window, Qt.Key.Key_Escape)
    # Wait for shortcut dispatch
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    assert window._current[0] == "menu"


def test_esc_shortcut_no_op_when_back_invisible(window):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QCoreApplication

    assert window.header.back_button.isVisible() is False  # on menu
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QCoreApplication.processEvents()
    # Still on menu — nothing changed
    assert window._current[0] == "menu"

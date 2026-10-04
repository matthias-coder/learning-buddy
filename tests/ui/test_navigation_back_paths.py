"""Back/Esc paths that previously dead-ended or re-entered a finished test.

Bugreport 1.0.1: #1 (profile manager), #2 (profile creation from picker),
#3 (back from results re-opened the runner and started a new attempt).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from school_test_engine.storage import run_migrations, users_repo

EXAMPLE = sorted((Path(__file__).parents[2] / "examples" / "ai-generated").glob("*.json"))[0]


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    calls = []
    for name in ("information", "warning"):
        monkeypatch.setattr(
            QMessageBox, name,
            staticmethod(lambda *a, _n=name, **kw: calls.append((_n, a)) or QMessageBox.StandardButton.Ok),
        )
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes),
    )
    yield calls


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    users_repo.create_user(c, name="Anna")
    yield c
    c.close()


@pytest.fixture
def window(conn):
    from PySide6.QtCore import QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from school_test_engine.ui.main_window import MainWindow
    w = MainWindow(conn)
    w.show_profile_picker()
    w.show()
    w.activateWindow()
    QTest.qWaitForWindowExposed(w)
    yield w
    w.close()
    w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def _press_esc(window):
    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtTest import QTest
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QCoreApplication.processEvents()


def _on_picker(window) -> bool:
    return (
        window._current[0] == "profile_picker"
        and window.stack.currentWidget() is window.profile_picker_page
        and not window.header.isVisible()
    )


# --- #2 profile creation from picker ----------------------------------------

def test_new_profile_from_picker_returns_to_picker_with_feedback(window, conn, _no_modal_dialogs):
    window.show_profile_edit(user_id=None, return_to="picker")
    page = window.profile_edit_page
    page.name_edit.setText("Dora")
    page.save_btn.click()

    assert _on_picker(window)
    assert [u["name"] for u in users_repo.list_users(conn)].count("Dora") == 1
    assert any("Dora" in " ".join(map(str, a)) for _n, a in _no_modal_dialogs)


def test_repeated_save_does_not_create_duplicates(window, conn):
    window.show_profile_edit(user_id=None, return_to="picker")
    page = window.profile_edit_page
    page.name_edit.setText("Dora")
    page._save()
    page._save()  # second click arriving before/after the page switch
    assert [u["name"] for u in users_repo.list_users(conn)].count("Dora") == 1


def test_cancel_new_profile_returns_to_picker(window):
    window.show_profile_edit(user_id=None, return_to="picker")
    window.profile_edit_page._cancel()
    assert _on_picker(window)


def test_esc_on_profile_edit_returns_to_picker(window):
    window.show_profile_edit(user_id=None, return_to="picker")
    _press_esc(window)
    assert _on_picker(window)


# --- #1 profile manager -------------------------------------------------------

def test_esc_on_profile_manager_returns_to_picker(window):
    window.show_profile_manager(return_to="picker")
    _press_esc(window)
    assert _on_picker(window)


def test_manager_back_button_returns_to_picker(window):
    window.show_profile_manager(return_to="picker")
    window.profile_manager_page.back_btn.click()
    assert _on_picker(window)


def test_esc_on_picker_is_noop(window):
    _press_esc(window)
    assert _on_picker(window)


# --- #3 back from results -----------------------------------------------------

def _finish_test(window, conn) -> int:
    from school_test_engine.importer.json_import import import_from_file
    uid = int(users_repo.list_users(conn)[0]["id"])
    window.set_active_user(uid)
    test_id = import_from_file(conn, EXAMPLE, user_id=uid)
    window.show_library()
    window.start_test(test_id)
    window.show_review(window.runner_page._attempt_id)
    window.runner_page.submit_final()
    assert window._current[0] == "results"
    return uid


def _attempt_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM attempts").fetchone()["n"]


def test_back_from_results_never_reenters_test(window, conn):
    _finish_test(window, conn)
    before = _attempt_count(conn)

    while window._history:
        window._navigate_back()
        assert window._current[0] not in ("runner", "review")

    assert _attempt_count(conn) == before


def test_back_from_results_goes_to_menu(window, conn):
    # Same target as the results page's own "← Zurück" button.
    _finish_test(window, conn)
    window._navigate_back()
    assert window._current[0] == "menu"


def test_header_back_from_review_returns_to_running_test(window, conn):
    from school_test_engine.importer.json_import import import_from_file
    uid = int(users_repo.list_users(conn)[0]["id"])
    window.set_active_user(uid)
    test_id = import_from_file(conn, EXAMPLE, user_id=uid)
    window.start_test(test_id)
    attempt_id = window.runner_page._attempt_id
    window.show_review(attempt_id)
    before = _attempt_count(conn)

    window._navigate_back()

    assert window._current[0] == "runner"
    assert window.runner_page._attempt_id == attempt_id
    assert _attempt_count(conn) == before

"""Phase 14 Track B: keyboard shortcuts module."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_install_runner_shortcuts_registers_all_keys(app):
    from school_test_engine.ui.keyboard_shortcuts import install_runner_shortcuts
    page = QWidget()
    fired = {"prev": 0, "next": 0, "mark": 0, "overview": 0, "abort": 0}
    shortcuts = install_runner_shortcuts(
        page,
        on_prev=lambda: fired.__setitem__("prev", fired["prev"] + 1),
        on_next=lambda: fired.__setitem__("next", fired["next"] + 1),
        on_mark=lambda: fired.__setitem__("mark", fired["mark"] + 1),
        on_overview=lambda: fired.__setitem__("overview", fired["overview"] + 1),
        on_abort=lambda: fired.__setitem__("abort", fired["abort"] + 1),
    )
    assert len(shortcuts) == 7
    seqs = {s.key().toString() for s in shortcuts}
    assert "Left" in seqs
    assert "Right" in seqs
    assert "Return" in seqs or "Enter" in seqs
    assert "M" in seqs
    assert "O" in seqs
    assert "Esc" in seqs


def test_right_arrow_fires_on_next(app):
    from school_test_engine.ui.keyboard_shortcuts import install_runner_shortcuts
    page = QWidget()
    page.resize(200, 200)
    fired = {"next": 0}
    install_runner_shortcuts(
        page,
        on_prev=lambda: None,
        on_next=lambda: fired.__setitem__("next", fired["next"] + 1),
        on_mark=lambda: None,
        on_overview=lambda: None,
        on_abort=lambda: None,
    )
    page.show()
    QTest.qWaitForWindowExposed(page)
    QTest.keyClick(page, Qt.Key.Key_Right)
    QApplication.processEvents()
    assert fired["next"] == 1
    page.close()


def test_m_key_fires_on_mark(app):
    from school_test_engine.ui.keyboard_shortcuts import install_runner_shortcuts
    page = QWidget()
    page.resize(200, 200)
    fired = {"mark": 0}
    install_runner_shortcuts(
        page,
        on_prev=lambda: None,
        on_next=lambda: None,
        on_mark=lambda: fired.__setitem__("mark", fired["mark"] + 1),
        on_overview=lambda: None,
        on_abort=lambda: None,
    )
    page.show()
    QTest.qWaitForWindowExposed(page)
    QTest.keyClick(page, Qt.Key.Key_M)
    QApplication.processEvents()
    assert fired["mark"] == 1
    page.close()


def test_runner_page_installs_shortcuts(app, tmp_path):
    """The RunnerPage actually installs the shortcuts when constructed."""
    import sqlite3
    from school_test_engine.storage import run_migrations, users_repo
    from school_test_engine.ui.pages.runner import RunnerPage

    db = tmp_path / "r.db"
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    run_migrations(c)

    class _StubWindow:
        def __init__(self, conn):
            self.conn = conn
            self.active_user_id = users_repo.create_user(conn, "Test", "👤")
        def show_results(self, *a, **kw): pass
        def show_menu(self, *a, **kw): pass

    win = _StubWindow(c)
    page = RunnerPage(win, c)
    assert hasattr(page, "_shortcuts")
    assert len(page._shortcuts) == 7
    assert hasattr(page, "cheat_sheet")

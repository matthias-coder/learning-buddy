"""Phase 14 Track A: App is rebranded to 'Learning Buddy'."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.storage import run_migrations


@pytest.fixture(scope="module")
def app():
    inst = QApplication.instance() or QApplication([])
    return inst


def test_application_name_is_learning_buddy(app):
    from school_test_engine import app as app_module
    src = app_module.__file__
    text = open(src, encoding="utf-8").read()
    assert 'setApplicationName("Learning Buddy")' in text
    assert 'setApplicationDisplayName("Learning Buddy")' in text


def test_main_window_title_is_learning_buddy(app, tmp_path):
    db = tmp_path / "lb.db"
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    run_migrations(c)
    from school_test_engine.ui.main_window import MainWindow
    win = MainWindow(c)
    assert win.windowTitle() == "Learning Buddy"

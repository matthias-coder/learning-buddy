"""End-to-end test for Phase 18: vergangene KA in Schulkalender → click →
assessment_edit prefill → save → back via stack → badge wechselt → banner-
count dekrementiert."""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.storage import (
    assessments_repo, events_repo, run_migrations, users_repo,
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


def test_e2e_grade_nachtrag_flow_via_banner(conn):
    from school_test_engine.ui.main_window import MainWindow

    uid = users_repo.create_user(conn, name="Clemens")
    eid = events_repo.create(conn, uid, "Mathe", "klausur", "2026-04-01")

    win = MainWindow(conn)
    win.menu_page._today_override = date(2026, 5, 1)
    win.school_calendar_page._today_override = date(2026, 5, 1)
    win.set_active_user(uid)
    win.menu_page.reload()

    # 1. Banner is visible with count=1 on MenuPage
    banner = win.menu_page._open_grades_banner
    assert banner is not None
    assert "1 offene Note" in banner._label.text()

    # 2. Click banner → navigate to school_calendar with initial_tab='past'
    win.show_school_calendar(initial_tab="past")
    assert win._current[0] == "school_calendar"
    assert win.school_calendar_page._filters.timeframe == "past"

    # 3. Click the past KA → assessment_edit prefill
    win.school_calendar_page._open_klausur(eid)
    assert win._current[0] == "assessment_edit"
    assert win.assessment_edit_page._prefill_event_id == eid
    assert win.assessment_edit_page.subject.isEnabled() is False

    # 4. Simulate saving a 2.5 → create assessment row + navigate back
    assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", "2026-04-01",
        grade=2.5, scheduled_event_id=eid,
    )
    win._navigate_back()  # would normally be called by assessment_edit._save
    assert win._current[0] == "school_calendar"

    # 5. Back again → menu, banner should be gone
    win._navigate_back()
    win.menu_page.reload()
    assert win._current[0] == "menu"
    assert win.menu_page._open_grades_banner is None

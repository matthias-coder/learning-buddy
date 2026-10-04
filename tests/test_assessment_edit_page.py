"""Phase 13: AssessmentEditPage is the inline-page replacement for AssessmentDialog."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.storage import assessments_repo, events_repo, users_repo
from school_test_engine.storage import run_migrations


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    run_migrations(c)
    yield c
    c.close()


class _StubWindow:
    def __init__(self, conn):
        self.conn = conn
        self.active_user_id: int | None = None
        self.navigated_to: str | None = None
        self.current_page = None  # set by tests for _navigate_back routing

    def show_grades(self):
        self.navigated_to = "grades"

    def show_menu(self):
        self.navigated_to = "menu"

    def show_events(self):
        self.navigated_to = "events"

    def _navigate_back(self):
        # Mirrors MainWindow's history-stack pop; for tests we re-derive the
        # target from the page's recorded _return_to since the test bypasses
        # the real window dispatcher.
        rt = getattr(self.current_page, "_return_to", "grades")
        if rt == "menu":
            self.show_menu()
        elif rt == "events":
            self.show_events()
        else:
            self.show_grades()


def test_assessment_edit_page_constructs(app, conn):
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    page = AssessmentEditPage(win, conn)
    assert page is not None


def test_assessment_edit_page_save_creates(app, conn):
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    page = AssessmentEditPage(win, conn)
    win.current_page = page
    page.show_for(assessment_id=None, return_to="grades", prefill_subject="Mathe")
    page.grade.set_value(2.0)
    page._save()
    rows = assessments_repo.list_by_subject(conn, uid, "Mathe")
    assert len(rows) == 1
    assert rows[0]["grade"] == 2.0
    assert win.navigated_to == "grades"


def test_assessment_edit_page_edit_mode_loads(app, conn):
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    aid = assessments_repo.create(
        conn, uid, "Englisch", "schriftlich", "2026-04-15",
        grade=2.5, points=None, max_points=None, note=None,
        scheduled_event_id=None,
    )
    page = AssessmentEditPage(win, conn)
    page.show_for(assessment_id=aid, return_to="grades")
    assert not page.delete_btn.isHidden()
    assert abs(page.grade.value() - 2.5) < 0.01
    assert page.subject.currentText() == "Englisch"


def test_assessment_edit_page_delete(app, conn, monkeypatch):
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    aid = assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", "2026-04-15",
        grade=3.0, points=None, max_points=None, note=None,
        scheduled_event_id=None,
    )
    page = AssessmentEditPage(win, conn)
    win.current_page = page
    page.show_for(assessment_id=aid, return_to="menu")
    page._delete()
    assert assessments_repo.get(conn, aid) is None
    assert win.navigated_to == "menu"


def test_assessment_edit_page_prefill_event_id(app, conn):
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    eid = events_repo.create(
        conn, uid, "Bio", "klassenarbeit", "2026-04-20",
        topics=[], note=None,
    )
    page = AssessmentEditPage(win, conn)
    win.current_page = page
    page.show_for(
        assessment_id=None, return_to="menu",
        prefill_subject="Bio", prefill_event_id=eid,
    )
    page.grade.set_value(2.0)
    page._save()
    rows = assessments_repo.list_by_subject(conn, uid, "Bio")
    assert len(rows) == 1
    assert rows[0]["scheduled_event_id"] == eid


def test_grade_selector_half_step(app, conn):
    from school_test_engine.ui.pages.assessment_edit import _GradeSelector
    sel = _GradeSelector(initial=2.0)
    assert sel.value() == 2.0
    sel.set_value(2.5)
    assert sel.value() == 2.5


def test_prefill_event_id_disables_subject_and_date(app, conn):
    """When opening from a past KA, subject + date are not editable —
    they reflect the KA, not arbitrary user choices."""
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    eid = events_repo.create(
        conn, uid, "Mathe", "klassenarbeit", "2026-04-15",
        topics=[], note=None,
    )
    page = AssessmentEditPage(win, conn)
    win.current_page = page
    page.show_for(
        assessment_id=None,
        return_to="grades",
        prefill_subject="Mathe",
        prefill_event_id=eid,
    )

    assert page.subject.isEnabled() is False
    assert page.date_edit.isEnabled() is False
    # Sanity: value is preserved
    assert page.subject.currentText() == "Mathe"


def test_edit_mode_keeps_subject_and_date_enabled(app, conn):
    """When editing an existing assessment, both fields remain enabled."""
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    eid = events_repo.create(
        conn, uid, "Englisch", "klassenarbeit", "2026-04-15",
        topics=[], note=None,
    )
    aid = assessments_repo.create(
        conn, uid, "Englisch", "schriftlich", "2026-04-15",
        grade=2.0, points=None, max_points=None, note=None,
        scheduled_event_id=eid,
    )
    page = AssessmentEditPage(win, conn)
    win.current_page = page
    page.show_for(assessment_id=aid)

    assert page.subject.isEnabled() is True
    assert page.date_edit.isEnabled() is True


def test_no_prefill_event_id_keeps_subject_and_date_enabled(app, conn):
    """When opened via 'Note hinzufügen' (no event link), both stay enabled."""
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    page = AssessmentEditPage(win, conn)
    win.current_page = page
    page.show_for(assessment_id=None)

    assert page.subject.isEnabled() is True
    assert page.date_edit.isEnabled() is True


def test_grade_six_cannot_become_six_and_a_half(app, conn):
    """Bug #6: valid German grades are 1-6, so 6,5 must be impossible."""
    from school_test_engine.ui.pages.assessment_edit import _GradeSelector
    sel = _GradeSelector(initial=6.0)
    assert not sel._half.isEnabled()
    sel._toggle_half()
    assert sel.value() == 6.0
    sel.set_value(5.5)
    assert sel._half.isEnabled()
    sel._set_int(6)
    assert sel.value() == 6.0
    assert not sel._half.isEnabled()


def test_grade_six_half_is_clamped_when_selecting_six(app, conn):
    from school_test_engine.ui.pages.assessment_edit import _GradeSelector
    sel = _GradeSelector(initial=5.5)
    sel._set_int(6)
    assert sel.value() == 6.0
    assert not sel._half.isChecked()


def test_save_never_stores_grade_above_six(app, conn):
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    page = AssessmentEditPage(win, conn)
    win.current_page = page
    page.show_for(assessment_id=None, return_to="grades", prefill_subject="Mathe")
    page.grade._value = 6.5  # bypass the selector guard
    page._save()
    rows = assessments_repo.list_by_subject(conn, uid, "Mathe")
    assert rows[0]["grade"] <= 6.0

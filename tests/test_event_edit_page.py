"""Phase 13: EventEditPage is the inline-page replacement for EventDialog."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.storage import events_repo, run_migrations, users_repo


@pytest.fixture(scope="module")
def app():
    inst = QApplication.instance() or QApplication([])
    return inst


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

    def show_events(self):
        self.navigated_to = "events"

    def show_menu(self):
        self.navigated_to = "menu"

    def _navigate_back(self):
        # Mirrors MainWindow's history-stack pop; for tests we re-derive the
        # target from the page's recorded _return_to since the test bypasses
        # the real window dispatcher.
        rt = getattr(self.current_page, "_return_to", "events")
        if rt == "menu":
            self.show_menu()
        else:
            self.show_events()


def test_event_edit_page_constructs(app, conn):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    win = _StubWindow(conn)
    page = EventEditPage(win, conn)
    assert page is not None


def test_event_edit_page_new_mode_shows_no_delete(app, conn):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    page = EventEditPage(win, conn)
    page.show_for(event_id=None, return_to="events")
    assert page.delete_btn.isVisible() is False
    assert "Klassenarbeit" in page.title_label.text() or "Termin" in page.title_label.text()


def test_event_edit_page_save_creates_event(app, conn):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    page = EventEditPage(win, conn)
    win.current_page = page
    page.show_for(event_id=None, return_to="events")
    page.subject.setCurrentText("Mathe")
    page.date_edit.setDate(page.date_edit.date())  # use default = today + 7
    page.topics_edit.setPlainText("Bruchrechnung\nGleichungen")
    page.note_edit.setText("Formelsammlung erlaubt")
    page._save()
    rows = events_repo.list_all(conn, uid)
    assert len(rows) == 1
    assert rows[0]["subject"] == "Mathe"
    assert rows[0]["note"] == "Formelsammlung erlaubt"
    assert win.navigated_to == "events"


def test_event_edit_page_edit_mode_loads_and_updates(app, conn):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    eid = events_repo.create(
        conn, uid, "Englisch", "test", "2026-06-01",
        topics=["Vocab"], note=None,
    )
    page = EventEditPage(win, conn)
    win.current_page = page
    page.show_for(event_id=eid, return_to="events")
    assert not page.delete_btn.isHidden()
    assert page.subject.currentText() == "Englisch"
    page.note_edit.setText("neue Notiz")
    page._save()
    row = events_repo.get(conn, eid)
    assert row["note"] == "neue Notiz"
    assert win.navigated_to == "events"


def test_event_edit_page_delete_removes_event(app, conn, monkeypatch):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    from PySide6.QtWidgets import QMessageBox
    # auto-confirm the deletion dialog
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    eid = events_repo.create(
        conn, uid, "Mathe", "klassenarbeit", "2026-06-01",
        topics=[], note=None,
    )
    page = EventEditPage(win, conn)
    win.current_page = page
    page.show_for(event_id=eid, return_to="menu")
    page._delete()
    assert events_repo.get(conn, eid) is None
    assert win.navigated_to == "menu"


def test_event_edit_page_cancel_navigates_back(app, conn):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    page = EventEditPage(win, conn)
    win.current_page = page
    page.show_for(event_id=None, return_to="menu")
    page._cancel()
    assert win.navigated_to == "menu"

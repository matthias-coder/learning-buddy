"""Phase 15: EventsPage has Sync button + injectable runner + status label."""
from __future__ import annotations

import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from school_test_engine.ical_sync.service import SyncResult
from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.ui.pages.events import EventsPage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


class FakeWindow:
    def __init__(self, conn):
        self.conn = conn
        self.active_user_id = None
    def show_menu(self):
        pass
    def show_event_edit(self, event_id, return_to):
        pass


def test_sync_button_calls_runner(app, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x/feed")
    win = FakeWindow(conn)
    win.active_user_id = uid
    calls: list = []
    def fake_runner(callback):
        calls.append("called")
        callback(SyncResult(added=3))
    page = EventsPage(win, conn, sync_runner=fake_runner)
    page.reload()
    page.sync_button.click()
    assert calls == ["called"]


def test_sync_button_disabled_during_run(app, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x/feed")
    win = FakeWindow(conn)
    win.active_user_id = uid
    captured: list = []
    def fake_runner(callback):
        captured.append(callback)
    page = EventsPage(win, conn, sync_runner=fake_runner)
    page.reload()
    page.sync_button.click()
    assert not page.sync_button.isEnabled()
    captured[0](SyncResult(added=3))
    assert page.sync_button.isEnabled()


def test_sync_result_shows_counts(app, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x/feed")
    win = FakeWindow(conn)
    win.active_user_id = uid
    page = EventsPage(win, conn, sync_runner=lambda cb: cb(SyncResult(added=3, updated=1)))
    page.reload()
    page.sync_button.click()
    text = page.sync_status_label.text()
    assert "3 neu" in text
    assert "1 verschoben" in text


def test_sync_result_shows_error(app, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x/feed")
    win = FakeWindow(conn)
    win.active_user_id = uid
    page = EventsPage(win, conn, sync_runner=lambda cb: cb(SyncResult(error="Timeout")))
    page.reload()
    page.sync_button.click()
    assert "Timeout" in page.sync_status_label.text()


def test_sync_button_disabled_when_no_url(app, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    # No ical_feed_url set
    win = FakeWindow(conn)
    win.active_user_id = uid
    page = EventsPage(win, conn)
    page.reload()
    assert not page.sync_button.isEnabled()
    assert "nicht verknüpft" in page.sync_status_label.text()

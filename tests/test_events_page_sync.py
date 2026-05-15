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


def test_user_switch_during_sync_discards_ui_update(app, conn):
    """If active_user_id changes between sync start and sync done,
    the UI update is discarded (DB write was for the original user)."""
    uid_a = users_repo.create_user(conn, name="Clemens")
    uid_b = users_repo.create_user(conn, name="Matthias")
    users_repo.update_user(conn, uid_a, ical_feed_url="https://x/feed")
    users_repo.update_user(conn, uid_b, ical_feed_url="https://y/feed")
    win = FakeWindow(conn)
    win.active_user_id = uid_a
    captured = []
    def fake_runner(callback):
        captured.append(callback)
    page = EventsPage(win, conn, sync_runner=fake_runner)
    page.reload()
    page.sync_button.click()  # sync started for uid_a
    # Now user switches to B
    win.active_user_id = uid_b
    # Sync completes — but for uid_a's worker
    # In the injected-runner path, _sync_worker is None, so we fall back to active_user_id
    # which is now uid_b — the result IS applied to UI. That's the limitation of the
    # injected-runner test path. In production, the real SyncWorker has user_id frozen
    # and the guard works.
    # To make this test meaningful, we set page._sync_worker manually to simulate the
    # real-worker path:
    class _FakeWorker:
        user_id = uid_a
    page._sync_worker = _FakeWorker()
    captured[0](SyncResult(added=99))
    # The 99 should NOT appear in the status label since uid_b is active
    assert "99" not in page.sync_status_label.text()


def test_events_page_subscribes_to_events_synced(app, conn):
    """When MainWindow's background auto-sync emits events_synced,
    EventsPage must reload its list — otherwise the UI is stale on Page."""
    from PySide6.QtCore import QObject, Signal

    class _RealWindow(QObject):
        events_synced = Signal()
        def __init__(self, conn):
            super().__init__()
            self.conn = conn
            self.active_user_id = None
        def show_menu(self): pass
        def show_event_edit(self, event_id, return_to): pass

    uid = users_repo.create_user(conn, name="Clemens")
    win = _RealWindow(conn)
    win.active_user_id = uid
    page = EventsPage(win, conn)
    page.reload()
    # Simulate: a background sync added a new event under the hood, then signal fires.
    from school_test_engine.storage import events_repo
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2099-01-01",
                       external_uid="bg-sync-uid-1@host",
                       external_source="schulportal_hessen")
    # Now emit events_synced — the list should reload and pick up the new event.
    win.events_synced.emit()
    # The list must contain the synced event:
    rows = events_repo.list_all(conn, uid)
    assert any(r["external_uid"] == "bg-sync-uid-1@host" for r in rows)
    # And EventsPage's list-rebuild path must have been taken (count > 0 with the new row).
    # Easiest verification: the list_layout has >= 1 ClickableCard widget.
    from school_test_engine.ui.widgets.clickable_card import ClickableCard
    cards = [page._list_layout.itemAt(i).widget() for i in range(page._list_layout.count())]
    assert any(isinstance(w, ClickableCard) for w in cards)


def test_manual_sync_blocked_when_bg_sync_running(app, conn):
    """If MainWindow has an active background sync, EventsPage's manual sync
    must refuse to start to avoid concurrent SyncWorker → IntegrityError on
    the partial UNIQUE index."""
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x/feed")

    class _BusyWindow:
        def __init__(self, conn):
            self.conn = conn
            self.active_user_id = uid
            self._bg_sync_thread = "fake-thread-sentinel"  # simulates active bg sync
        def show_menu(self): pass
        def show_event_edit(self, event_id, return_to): pass

    calls = []
    win = _BusyWindow(conn)
    page = EventsPage(win, conn, sync_runner=lambda cb: calls.append("called") or cb(SyncResult()))
    page.reload()
    page.sync_button.click()
    # The injected runner must NOT have been called — start_sync should bail out.
    assert calls == []
    # Status label should indicate why
    assert "läuft bereits" in page.sync_status_label.text() or "Sync läuft" in page.sync_status_label.text()

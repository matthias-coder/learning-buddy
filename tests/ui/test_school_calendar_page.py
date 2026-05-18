from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.storage import (
    calendar_events_repo, events_repo, run_migrations, users_repo,
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


class _StubWindow:
    def __init__(self, conn, user_id):
        self.conn = conn
        self.active_user_id = user_id
        self.opened_event_id: int | None = None
        self.last_call: tuple[str, dict] | None = None

    def show_event_edit(self, event_id, return_to="menu"):
        self.opened_event_id = event_id
        self.last_call = ("show_event_edit", {"event_id": event_id})

    def show_assessment_edit(self, **kwargs):
        cleaned = {k: v for k, v in kwargs.items() if v is not None}
        self.last_call = ("show_assessment_edit", cleaned)


def test_page_renders_chronological_entries_from_both_sources(conn):
    uid = users_repo.create_user(conn, name="C")
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2030-06-15")
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommer",
                                start_date="2030-07-07", end_date="2030-08-15")
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=date(2030, 5, 1))
    page.reload()
    titles = [c._entry.title for c in page._cards]
    assert titles == ["Mathe Klassenarbeit", "Sommer"]


def test_chip_toggle_persists_filter(conn):
    uid = users_repo.create_user(conn, name="C")
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=date(2030, 5, 1))
    page.reload()
    page._on_chip_toggled("ferien", False)
    row = users_repo.get_user(conn, uid)
    assert row["calendar_show_ferien"] == 0


def test_tab_change_persists_timeframe(conn):
    uid = users_repo.create_user(conn, name="C")
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=date(2030, 5, 1))
    page.reload()
    page._on_timeframe_changed("past")
    row = users_repo.get_user(conn, uid)
    assert row["calendar_timeframe"] == "past"


def test_empty_states_when_all_filters_off(conn):
    uid = users_repo.create_user(conn, name="C")
    users_repo.update_user(
        conn, uid,
        calendar_show_klausuren=0, calendar_show_ferien=0,
        calendar_show_frei=0, calendar_show_events=0,
    )
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=date(2030, 5, 1))
    page.show()
    page.reload()
    assert page._empty_label.isVisible() is True
    assert "ausgeschaltet" in page._empty_label.text()


def test_klausur_click_opens_event_edit(conn):
    uid = users_repo.create_user(conn, name="C")
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2030-06-15")
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=date(2030, 5, 1))
    page.reload()
    assert len(page._cards) == 1
    page._cards[0]._maybe_emit_click()
    assert win.opened_event_id == eid


def test_click_past_klausur_without_grade_opens_assessment_edit_with_prefill(conn):
    from datetime import date as _date
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage

    uid = users_repo.create_user(conn, name="T")
    eid = events_repo.create(conn, uid, "Mathe", "klausur", "2026-04-01")

    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=_date(2026, 5, 1))
    page.reload()
    page._open_klausur(eid)

    assert win.last_call == ("show_assessment_edit", {
        "prefill_event_id": eid,
        "prefill_subject": "Mathe",
    })


def test_click_past_klausur_with_grade_opens_assessment_edit_in_edit_mode(conn):
    from datetime import date as _date
    from school_test_engine.storage import assessments_repo
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage

    uid = users_repo.create_user(conn, name="T")
    eid = events_repo.create(conn, uid, "Englisch", "klausur", "2026-04-15")
    aid = assessments_repo.create(
        conn, uid, "Englisch", "schriftlich", "2026-04-15",
        grade=2.0, scheduled_event_id=eid,
    )

    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=_date(2026, 5, 1))
    page.reload()
    page._open_klausur(eid)

    assert win.last_call == ("show_assessment_edit", {"assessment_id": aid})


def test_click_future_klausur_still_opens_event_edit(conn):
    from datetime import date as _date
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage

    uid = users_repo.create_user(conn, name="T")
    eid = events_repo.create(conn, uid, "Bio", "test", "2026-07-01")

    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=_date(2026, 5, 1))
    page.reload()
    page._open_klausur(eid)

    assert win.last_call == ("show_event_edit", {"event_id": eid})


def test_show_for_initial_tab_past_activates_tab_button(conn):
    from datetime import date as _date
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage

    uid = users_repo.create_user(conn, name="T")
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=_date(2026, 5, 1))
    page.show_for(initial_tab="past")
    assert page._tab_buttons["past"].isChecked() is True
    assert page._filters.timeframe == "past"


def test_show_for_no_initial_tab_uses_persisted_filter(conn):
    from datetime import date as _date
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage

    uid = users_repo.create_user(conn, name="T")
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=_date(2026, 5, 1))
    page.show_for()  # No initial_tab → defaults preserved
    # CalendarFilters.defaults() defines the default timeframe; just verify
    # show_for does not crash and a tab is selected.
    selected = [tf for tf, btn in page._tab_buttons.items() if btn.isChecked()]
    assert len(selected) == 1

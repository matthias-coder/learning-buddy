from __future__ import annotations

from datetime import date

import pytest

from school_test_engine.school_calendar.models import CalendarEntry


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _entry(**kw):
    base = dict(
        source="calendar", kind="ferien", title="Sommerferien",
        start_date=date(2026, 7, 7), end_date=date(2026, 8, 15),
        subject=None, entry_id=1,
    )
    base.update(kw)
    return CalendarEntry(**base)


def test_card_renders_date_for_single_day():
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard
    e = _entry(kind="klausur", source="klausur",
               start_date=date(2026, 5, 15), end_date=date(2026, 5, 15),
               title="Mathe Klassenarbeit", subject="Mathe")
    card = CalendarEntryCard(e)
    assert card._date_label.text() == "15.05."


def test_card_renders_date_range_for_multi_day():
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard
    card = CalendarEntryCard(_entry())
    assert card._date_label.text() == "07.07.–15.08."


def test_klausur_card_is_clickable_and_emits_signal():
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard
    e = _entry(kind="klausur", source="klausur", subject="Mathe",
               start_date=date(2026, 5, 15), end_date=date(2026, 5, 15),
               entry_id=42, title="Mathe Klassenarbeit")
    card = CalendarEntryCard(e)
    received: list[int] = []
    card.clicked.connect(received.append)
    card._maybe_emit_click()
    assert received == [42]


def test_non_klausur_card_does_not_emit_on_click():
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard
    card = CalendarEntryCard(_entry())     # kind='ferien'
    received: list[int] = []
    card.clicked.connect(received.append)
    card._maybe_emit_click()
    assert received == []


def test_past_klausur_without_grade_shows_offen_pill():
    from school_test_engine.school_calendar.models import GradeStatus
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard

    e = _entry(kind="klausur", source="klausur", subject="Mathe",
               start_date=date(2026, 4, 1), end_date=date(2026, 4, 1),
               entry_id=42, title="Mathe Klassenarbeit")
    gs = GradeStatus(assessment_id=None, grade=None)
    card = CalendarEntryCard(e, grade_status=gs)

    from PySide6.QtWidgets import QLabel
    labels = [lbl.text() for lbl in card.findChildren(QLabel)]
    assert any("Note offen" in t for t in labels)


def test_past_klausur_with_grade_shows_grade_pill():
    from school_test_engine.school_calendar.models import GradeStatus
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard

    e = _entry(kind="klausur", source="klausur", subject="Mathe",
               start_date=date(2026, 4, 1), end_date=date(2026, 4, 1),
               entry_id=42, title="Mathe Klassenarbeit")
    gs = GradeStatus(assessment_id=7, grade=2.5)
    card = CalendarEntryCard(e, grade_status=gs)

    from PySide6.QtWidgets import QLabel
    labels = [lbl.text() for lbl in card.findChildren(QLabel)]
    # GradePill formats half-step as "2,5"
    assert any(t == "2,5" for t in labels)


def test_future_klausur_no_grade_badge():
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard
    e = _entry(kind="klausur", source="klausur", subject="Mathe",
               start_date=date(2026, 12, 1), end_date=date(2026, 12, 1),
               entry_id=42, title="Mathe Klassenarbeit")
    card = CalendarEntryCard(e, grade_status=None)
    from PySide6.QtWidgets import QLabel
    labels = [lbl.text() for lbl in card.findChildren(QLabel)]
    assert not any("Note offen" in t for t in labels)

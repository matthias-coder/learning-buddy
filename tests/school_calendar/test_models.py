from __future__ import annotations

from datetime import date

import pytest

from school_test_engine.school_calendar.models import CalendarEntry


def test_calendar_entry_is_frozen():
    e = CalendarEntry(
        source="klausur", kind="klausur",
        title="Mathe Klassenarbeit",
        start_date=date(2026, 5, 15), end_date=date(2026, 5, 15),
        subject="Mathe", entry_id=42,
    )
    import dataclasses
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.title = "x"  # type: ignore


def test_is_multi_day_true_for_range():
    e = CalendarEntry(
        source="calendar", kind="ferien", title="Sommer",
        start_date=date(2026, 7, 7), end_date=date(2026, 8, 15),
        subject=None, entry_id=1,
    )
    assert e.is_multi_day is True


def test_is_multi_day_false_for_single_day():
    e = CalendarEntry(
        source="calendar", kind="frei", title="Päd. Tag",
        start_date=date(2026, 5, 12), end_date=date(2026, 5, 12),
        subject=None, entry_id=2,
    )
    assert e.is_multi_day is False

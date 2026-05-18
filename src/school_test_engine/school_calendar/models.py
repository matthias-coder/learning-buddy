from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

Source = Literal["klausur", "calendar"]
Kind = Literal["klausur", "ferien", "frei", "event"]


@dataclass(frozen=True)
class CalendarEntry:
    """A merged entry: KA from scheduled_events or a row from calendar_events."""
    source: Source
    kind: Kind
    title: str
    start_date: date
    end_date: date
    subject: str | None
    entry_id: int

    @property
    def is_multi_day(self) -> bool:
        return self.end_date > self.start_date


@dataclass(frozen=True)
class GradeStatus:
    """Holds the grade-link state for a past KA. Used by CalendarEntryCard.

    `assessment_id is None and grade is None` → "Note offen"
    Both set → grade was entered (display as GradePill).
    """
    assessment_id: int | None
    grade: float | None

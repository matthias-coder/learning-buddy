from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from typing import Literal

Timeframe = Literal["future", "all", "past"]
_KIND_TO_FIELD = {
    "klausur": "show_klausuren",
    "ferien": "show_ferien",
    "frei": "show_frei",
    "event": "show_events",
}


@dataclass(frozen=True)
class CalendarFilters:
    show_klausuren: bool
    show_ferien: bool
    show_frei: bool
    show_events: bool
    timeframe: Timeframe

    @classmethod
    def defaults(cls) -> "CalendarFilters":
        return cls(True, True, True, True, "future")

    @classmethod
    def from_user_row(cls, row: sqlite3.Row) -> "CalendarFilters":
        return cls(
            show_klausuren=bool(row["calendar_show_klausuren"]),
            show_ferien=bool(row["calendar_show_ferien"]),
            show_frei=bool(row["calendar_show_frei"]),
            show_events=bool(row["calendar_show_events"]),
            timeframe=row["calendar_timeframe"],
        )

    def with_kind_set(self, kind: str, value: bool) -> "CalendarFilters":
        field = _KIND_TO_FIELD[kind]
        return replace(self, **{field: value})

    def with_timeframe(self, tf: str) -> "CalendarFilters":
        return replace(self, timeframe=tf)  # type: ignore[arg-type]

    def active_kinds(self) -> set[str]:
        out: set[str] = set()
        if self.show_klausuren: out.add("klausur")
        if self.show_ferien:    out.add("ferien")
        if self.show_frei:      out.add("frei")
        if self.show_events:    out.add("event")
        return out

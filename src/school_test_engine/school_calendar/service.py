"""Schulkalender service: merge KAs + calendar_events, filter, group."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Literal

from ..storage import calendar_events_repo, events_repo
from .filters import CalendarFilters
from .models import CalendarEntry


_KIND_LABEL = {
    "klassenarbeit": "Klassenarbeit",
    "klausur": "Klausur",
    "test": "Test",
    "sonstiges": "Termin",
}

_MONTHS_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def list_entries(
    conn: sqlite3.Connection,
    user_id: int,
    today: date,
    filters: CalendarFilters,
) -> list[CalendarEntry]:
    active = filters.active_kinds()
    if not active:
        return []

    entries: list[CalendarEntry] = []

    if "klausur" in active:
        for row in events_repo.list_for_calendar(conn, user_id):
            entries.append(_from_klausur_row(row))

    cal_kinds = active - {"klausur"}
    if cal_kinds:
        for row in calendar_events_repo.list_for_user(
            conn, user_id,
            today=today.isoformat(),
            timeframe=filters.timeframe,
            kinds=cal_kinds,
        ):
            entries.append(_from_calendar_row(row))

    entries = _apply_timeframe(entries, today, filters.timeframe)
    entries.sort(key=lambda e: (e.start_date, e.kind, e.entry_id))
    return entries


def group_by_month(
    entries: list[CalendarEntry],
) -> list[tuple[str, list[CalendarEntry]]]:
    out: list[tuple[str, list[CalendarEntry]]] = []
    current_key: tuple[int, int] | None = None
    for e in entries:
        key = (e.start_date.year, e.start_date.month)
        if key != current_key:
            label = f"{_MONTHS_DE[e.start_date.month - 1]} {e.start_date.year}"
            out.append((label, []))
            current_key = key
        out[-1][1].append(e)
    return out


def _apply_timeframe(
    entries: list[CalendarEntry], today: date, timeframe: str
) -> list[CalendarEntry]:
    if timeframe == "future":
        return [e for e in entries if e.end_date >= today]
    if timeframe == "past":
        return [e for e in entries if e.end_date < today]
    return entries


def _from_klausur_row(row: sqlite3.Row) -> CalendarEntry:
    d = date.fromisoformat(row["event_date"])
    kind_label = _KIND_LABEL.get(row["kind"], row["kind"].title())
    title = f"{row['subject']} {kind_label}"
    return CalendarEntry(
        source="klausur",
        kind="klausur",
        title=title,
        start_date=d,
        end_date=d,
        subject=row["subject"],
        entry_id=row["id"],
    )


def _from_calendar_row(row: sqlite3.Row) -> CalendarEntry:
    return CalendarEntry(
        source="calendar",
        kind=row["kind"],
        title=row["title"],
        start_date=date.fromisoformat(row["start_date"]),
        end_date=date.fromisoformat(row["end_date"]),
        subject=None,
        entry_id=row["id"],
    )


@dataclass(frozen=True)
class FerienBannerState:
    mode: Literal["hidden", "countdown", "in_vacation"]
    label: str
    days: int | None
    target_date: date | None
    vacation_title: str | None


def ferien_banner_state(
    conn: sqlite3.Connection, user_id: int, today: date
) -> FerienBannerState:
    today_iso = today.isoformat()

    active = calendar_events_repo.find_active_vacation(conn, user_id, today_iso)
    if active is not None:
        end = date.fromisoformat(active["end_date"])
        remaining = (end - today).days
        title = active["title"]
        if remaining == 0:
            label = "Letzter Ferientag — morgen geht's wieder los."
        else:
            label = f"Noch {remaining} Tage {title} — genieß sie! 🌞"
        return FerienBannerState(
            mode="in_vacation", label=label, days=remaining,
            target_date=end, vacation_title=title,
        )

    upcoming = calendar_events_repo.find_next_vacation(conn, user_id, today_iso)
    if upcoming is not None:
        start = date.fromisoformat(upcoming["start_date"])
        days = (start - today).days
        title = upcoming["title"]
        if days == 1:
            label = f"Morgen geht's los: {title} starten!"
        else:
            label = f"Noch {days} Tage bis {title} — {start.strftime('%d.%m.%Y')}"
        return FerienBannerState(
            mode="countdown", label=label, days=days,
            target_date=start, vacation_title=title,
        )

    return FerienBannerState(
        mode="hidden", label="", days=None, target_date=None, vacation_title=None,
    )

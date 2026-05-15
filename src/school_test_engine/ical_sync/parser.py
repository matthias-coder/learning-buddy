"""Wrap the icalendar library and emit stdlib-only RawVEvent dataclasses.

This isolates the rest of the app from the icalendar API — if the library
ever needs to be swapped, only this file changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import icalendar


@dataclass(frozen=True)
class RawVEvent:
    uid: str
    summary: str
    description: str
    dtstart_date: str          # always ISO YYYY-MM-DD, normalized
    categories: tuple[str, ...]


def parse_events(ics_bytes: bytes) -> list[RawVEvent]:
    """Parse ics bytes. Raises ValueError when input is not a valid iCal."""
    try:
        cal = icalendar.Calendar.from_ical(ics_bytes)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Invalid iCal data: {e}") from e

    out: list[RawVEvent] = []
    for comp in cal.walk("VEVENT"):
        dtstart = comp.get("DTSTART")
        if dtstart is None:
            continue
        dt = dtstart.dt
        iso_date = (
            dt.date().isoformat() if isinstance(dt, datetime) else dt.isoformat()
        )
        out.append(RawVEvent(
            uid=str(comp.get("UID", "")),
            summary=str(comp.get("SUMMARY", "")),
            description=str(comp.get("DESCRIPTION", "")),
            dtstart_date=iso_date,
            categories=_categories(comp),
        ))
    return out


def _categories(comp) -> tuple[str, ...]:
    cat = comp.get("CATEGORIES")
    if cat is None:
        return ()
    # icalendar returns a vCategory object whose .cats holds the list
    if hasattr(cat, "cats"):
        return tuple(str(c) for c in cat.cats)
    return (str(cat),)

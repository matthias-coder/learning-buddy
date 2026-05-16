"""Wrap the icalendar library and emit stdlib-only RawVEvent dataclasses.

This isolates the rest of the app from the icalendar API — if the library
ever needs to be swapped, only this file changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import icalendar


@dataclass(frozen=True)
class RawVEvent:
    uid: str
    summary: str
    description: str
    dtstart_date: str          # always ISO YYYY-MM-DD, normalized
    dtend_date: str            # always ISO YYYY-MM-DD, normalized, inclusive
    categories: tuple[str, ...]

    @property
    def is_multi_day(self) -> bool:
        return self.dtend_date > self.dtstart_date


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
        start_iso = (
            dt.date().isoformat() if isinstance(dt, datetime) else dt.isoformat()
        )

        dtend = comp.get("DTEND")
        if dtend is None:
            end_iso = start_iso
        else:
            de = dtend.dt
            if isinstance(de, datetime):
                end_iso = de.date().isoformat()
            else:
                # DATE-only DTEND is exclusive → step back one day
                end_iso = (de - timedelta(days=1)).isoformat()

        out.append(RawVEvent(
            uid=str(comp.get("UID", "")),
            summary=str(comp.get("SUMMARY", "")),
            description=str(comp.get("DESCRIPTION", "")),
            dtstart_date=start_iso,
            dtend_date=end_iso,
            categories=_categories(comp),
        ))
    return out


def _categories(comp) -> tuple[str, ...]:
    cat = comp.get("CATEGORIES")
    if cat is None:
        return ()
    # Multiple CATEGORIES lines per VEVENT → icalendar wraps them in a list.
    if isinstance(cat, list):
        return tuple(str(c) for vcats in cat for c in vcats.cats)
    return tuple(str(c) for c in cat.cats)

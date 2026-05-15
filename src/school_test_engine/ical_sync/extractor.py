"""Turn a RawVEvent into an EventRecord by parsing DESCRIPTION.

DESCRIPTION format from Schulportal-Hessen:
    "Arbeit in Mathematik R8b (082M07-R)"
    "Lernkontrolle in Chemie R8b (082CH02-R)"
    "Klausur in Mathematik Q1 (Q1M01-G)"
    "Lernkontrolle in Religion - evangelisch (REV8_GcRab01-)"

If DESCRIPTION doesn't match, we return None (caller increments `skipped`).
No SUMMARY-fallback — YAGNI until evidence demands it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .parser import RawVEvent
from .subject_map import map_subject


@dataclass(frozen=True)
class EventRecord:
    external_uid: str
    subject: str         # post-mapping (e.g. "Mathe", not "Mathematik")
    kind: str            # 'klassenarbeit' | 'klausur' | 'test'
    event_date: str      # ISO YYYY-MM-DD


_DESC_PATTERN = re.compile(
    r"^(?P<kind_label>Arbeit|Lernkontrolle|Klausur)\s+in\s+"
    r"(?P<subject>.+?)"
    r"(?:\s+R\d+[a-z]?|\s+Q\d+)?"     # optional class designator
    r"\s*\([^)]+\)\s*$"
)

_KIND_MAP = {
    "Arbeit": "klassenarbeit",
    "Lernkontrolle": "test",
    "Klausur": "klausur",
}


def to_event_record(event: RawVEvent) -> EventRecord | None:
    m = _DESC_PATTERN.match(event.description.strip())
    if m is None:
        return None
    return EventRecord(
        external_uid=event.uid,
        subject=map_subject(m.group("subject").strip()),
        kind=_KIND_MAP[m.group("kind_label")],
        event_date=event.dtstart_date,
    )

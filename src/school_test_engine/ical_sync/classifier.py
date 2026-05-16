"""Classify VEVENTs from the Schulportal Hessen feed into kinds.

Returns one of:
    'klausur' — KAs / Lernkontrollen / Klausuren (UID contains '-klausur-')
    'ferien'  — multi-day school holidays (CATEGORIES Ferien/Feiertag + range)
    'frei'    — single-day off (Pädagogischer Tag etc.)
    'event'   — other school events (Wettbewerbe, AGs, Theater, ...)
    None      — skip; unknown / not relevant
"""
from __future__ import annotations

from typing import Literal

from .parser import RawVEvent

EventKind = Literal["klausur", "ferien", "frei", "event"]

_KLAUSUR_MARKER = "-klausur-"


def classify(event: RawVEvent) -> EventKind | None:
    """Classify a VEVENT into its kind, or None if it should be skipped."""
    if _KLAUSUR_MARKER in event.uid:
        return "klausur"

    cats_lower = {c.lower() for c in event.categories}

    if "ferien" in cats_lower or "feiertag" in cats_lower:
        return "ferien" if event.is_multi_day else "frei"

    if "arbeiten" in cats_lower:
        # CATEGORIES:Arbeiten WITHOUT -klausur- UID = Wettbewerb, Olympiade etc.
        return "event"

    return None


def is_klausur_event(event: RawVEvent) -> bool:
    """Backward-compat wrapper for Phase 15 callers."""
    return classify(event) == "klausur"

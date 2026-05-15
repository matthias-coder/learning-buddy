"""Identify Klassenarbeit/Lernkontrolle events by their UID marker.

The Schulportal-Hessen feed encodes school assessments with a stable
'-klausur-' substring in the UID. This is more reliable than parsing
CATEGORIES (which mixes AGs and assessments) or SUMMARY (which has
heterogeneous prose).
"""
from __future__ import annotations

from .parser import RawVEvent

_KLAUSUR_MARKER = "-klausur-"


def is_klausur_event(event: RawVEvent) -> bool:
    return _KLAUSUR_MARKER in event.uid

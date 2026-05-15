"""Phase 15: parser turns ICS bytes into RawVEvent dataclasses."""
from __future__ import annotations

from pathlib import Path

import pytest

from school_test_engine.ical_sync import parser


FIXTURE = Path(__file__).parent.parent / "fixtures" / "schulkalender_mini.ics"


def test_parse_returns_all_vevents():
    events = parser.parse_events(FIXTURE.read_bytes())
    assert len(events) == 4


def test_parse_extracts_uid_summary_description():
    events = parser.parse_events(FIXTURE.read_bytes())
    mathe = next(e for e in events if "Mathematik R8b" in e.summary)
    assert "klausur-9084" in mathe.uid
    assert mathe.summary == "Mathematik R8b Arbeit"
    assert mathe.description == "Arbeit in Mathematik R8b (082M07-R)"


def test_parse_dtstart_date_only_returns_iso_date():
    events = parser.parse_events(FIXTURE.read_bytes())
    sommer = next(e for e in events if e.summary == "Sommerferien")
    assert sommer.dtstart_date == "2025-07-07"


def test_parse_dtstart_with_tz_returns_iso_date():
    events = parser.parse_events(FIXTURE.read_bytes())
    mathe = next(e for e in events if "Mathematik R8b" in e.summary)
    assert mathe.dtstart_date == "2026-03-10"


def test_parse_extracts_categories():
    events = parser.parse_events(FIXTURE.read_bytes())
    sommer = next(e for e in events if e.summary == "Sommerferien")
    assert "Ferien" in sommer.categories


def test_parse_invalid_bytes_raises():
    with pytest.raises(ValueError):
        parser.parse_events(b"BEGIN:VCALENDAR\nINVALID")

"""Phase 15: parser turns ICS bytes into RawVEvent dataclasses."""
from __future__ import annotations

from pathlib import Path

import pytest

from school_test_engine.ical_sync import parser


FIXTURE = Path(__file__).parent.parent / "fixtures" / "schulkalender_mini.ics"


def test_parse_returns_all_vevents():
    events = parser.parse_events(FIXTURE.read_bytes())
    assert len(events) == 7


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


def test_parse_handles_multiline_description():
    """iCal line-folding: a DESCRIPTION that wraps across two physical lines
    must be reassembled into a single logical string by the parser."""
    events = parser.parse_events(FIXTURE.read_bytes())
    geo = next(e for e in events if "Geographie R8b" in e.summary)
    # No literal newline or leading space in the unfolded text:
    assert "\n" not in geo.description
    # The two folded fragments must end up adjacent:
    assert "ueber die Standard-Zeilenlaenge" in geo.description
    assert geo.description.endswith("(082GEO02-R)")


def test_dtend_date_for_date_only_event_is_inclusive():
    """DATE-only DTEND in iCal is exclusive — parser normalizes to inclusive."""
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:t1\nSUMMARY:Sommerferien\n"
        b"DTSTART;VALUE=DATE:20250707\nDTEND;VALUE=DATE:20250816\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    events = parser.parse_events(ics)
    assert len(events) == 1
    assert events[0].dtstart_date == "2025-07-07"
    assert events[0].dtend_date == "2025-08-15"
    assert events[0].is_multi_day is True


def test_dtend_date_for_datetime_event_is_same_day():
    """DATETIME DTEND on the same day means a same-day event."""
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:t2\nSUMMARY:KA\n"
        b"DTSTART;TZID=Europe/Berlin:20260310T093500\n"
        b"DTEND;TZID=Europe/Berlin:20260310T110500\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    events = parser.parse_events(ics)
    assert events[0].dtstart_date == "2026-03-10"
    assert events[0].dtend_date == "2026-03-10"
    assert events[0].is_multi_day is False


def test_missing_dtend_means_same_day():
    """A VEVENT without DTEND falls back to dtstart_date."""
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:t3\nSUMMARY:X\n"
        b"DTSTART;VALUE=DATE:20260512\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    events = parser.parse_events(ics)
    assert events[0].dtstart_date == "2026-05-12"
    assert events[0].dtend_date == "2026-05-12"
    assert events[0].is_multi_day is False

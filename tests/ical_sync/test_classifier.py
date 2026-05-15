"""Phase 15: classifier detects '-klausur-' marker in UID."""
from __future__ import annotations

from school_test_engine.ical_sync.classifier import is_klausur_event
from school_test_engine.ical_sync.parser import RawVEvent


def _ev(uid: str) -> RawVEvent:
    return RawVEvent(uid=uid, summary="", description="", dtstart_date="2026-01-01", categories=())


def test_klausur_uid_returns_true():
    e = _ev("20010101T000001-klausur-9084-14627-2026-03-10@6115.start.schulportal.hessen.de")
    assert is_klausur_event(e) is True


def test_ferien_uid_returns_false():
    e = _ev("20240409T113106-3788@6115.start.schulportal.hessen.de")
    assert is_klausur_event(e) is False


def test_empty_uid_returns_false():
    e = _ev("")
    assert is_klausur_event(e) is False

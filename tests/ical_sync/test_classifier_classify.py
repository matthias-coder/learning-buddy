"""Classify VEVENTs into klausur / ferien / frei / event / None (skip)."""
from __future__ import annotations

import pytest

from school_test_engine.ical_sync.classifier import classify, is_klausur_event
from school_test_engine.ical_sync.parser import RawVEvent


def _event(uid="x", summary="", desc="", start="2026-05-15",
            end=None, categories=()):
    return RawVEvent(
        uid=uid, summary=summary, description=desc,
        dtstart_date=start, dtend_date=end if end else start,
        categories=tuple(categories),
    )


def test_klausur_uid_marker_returns_klausur():
    e = _event(uid="20010101T000001-klausur-9084-14627-2026-03-10@x.org",
               categories=("Arbeiten",))
    assert classify(e) == "klausur"


def test_multi_day_ferien_category_returns_ferien():
    e = _event(start="2026-07-07", end="2026-08-15", categories=("Ferien",))
    assert classify(e) == "ferien"


def test_single_day_ferien_category_returns_frei():
    e = _event(start="2026-05-12", end="2026-05-12", categories=("Ferien",))
    assert classify(e) == "frei"


def test_feiertag_category_multi_day_returns_ferien():
    e = _event(start="2026-12-24", end="2026-12-26", categories=("Feiertag",))
    assert classify(e) == "ferien"


def test_feiertag_category_single_day_returns_frei():
    e = _event(start="2026-10-03", categories=("Feiertag",))
    assert classify(e) == "frei"


def test_arbeiten_without_klausur_uid_returns_event():
    """Wettbewerb etc. — CATEGORIES:Arbeiten ohne -klausur- im UID."""
    e = _event(uid="20250920T153052-5927@x.org",
               summary="Mathematikwettbewerb",
               categories=("Arbeiten",))
    assert classify(e) == "event"


def test_unknown_categories_returns_none():
    e = _event(categories=("Unterricht",))
    assert classify(e) is None


def test_no_categories_returns_none():
    e = _event(categories=())
    assert classify(e) is None


def test_is_klausur_event_backward_compat():
    """is_klausur_event must remain functional (Phase 15 callers + tests)."""
    e_kl = _event(uid="x-klausur-y", categories=("Arbeiten",))
    e_no = _event(uid="x-y", categories=("Ferien",), start="2026-07-07", end="2026-08-15")
    assert is_klausur_event(e_kl) is True
    assert is_klausur_event(e_no) is False

"""Phase 15: service.sync_feed orchestrates fetch + parse + diff + apply."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from school_test_engine.ical_sync import service
from school_test_engine.ical_sync.fetcher import FeedFetchError
from school_test_engine.storage import assessments_repo, events_repo, run_migrations, users_repo


FIXTURE = Path(__file__).parent.parent / "fixtures" / "schulkalender_mini.ics"


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def user_with_feed(conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x.example/feed")
    return uid


def _make_fetcher(ics_bytes: bytes):
    return lambda url, timeout=10.0: ics_bytes


def test_sync_inserts_klausuren_only(conn, user_with_feed, monkeypatch):
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    result = service.sync_feed(conn, user_with_feed)
    assert result.error is None
    # Fixture has 3 klausur-UIDs (Mathe + Religion + Geographie from line-folding test)
    assert result.added == 3
    assert result.updated == 0
    assert result.deleted == 0
    rows = events_repo.list_with_external_uid(conn, user_with_feed)
    subjects = sorted(r["subject"] for r in rows)
    assert subjects == ["Geographie", "Mathe", "Religion"]


def test_sync_is_idempotent(conn, user_with_feed, monkeypatch):
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    service.sync_feed(conn, user_with_feed)
    result = service.sync_feed(conn, user_with_feed)
    assert result.added == 0
    assert result.updated == 0
    assert result.deleted == 0


def test_sync_updates_changed_date_keeps_topics(conn, user_with_feed, monkeypatch):
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    service.sync_feed(conn, user_with_feed)
    # User adds topics manually to the Mathe-KA
    mathe = next(r for r in events_repo.list_with_external_uid(conn, user_with_feed) if r["subject"] == "Mathe")
    events_repo.update(conn, mathe["id"], topics=["Lineare Gleichungen", "Brüche"])
    # Second sync with date shifted in fixture content
    shifted = FIXTURE.read_bytes().replace(b"20260310", b"20260317")
    monkeypatch.setattr(service, "_fetch", _make_fetcher(shifted))
    result = service.sync_feed(conn, user_with_feed)
    assert result.updated == 1
    mathe_after = next(r for r in events_repo.list_with_external_uid(conn, user_with_feed) if r["subject"] == "Mathe")
    assert mathe_after["event_date"] == "2026-03-17"
    assert json.loads(mathe_after["topics"]) == ["Lineare Gleichungen", "Brüche"]


def _remove_religion_event(ics_bytes: bytes) -> bytes:
    """Delete the Religion VEVENT block from the fixture bytes."""
    start = ics_bytes.find(b"BEGIN:VEVENT\nDTSTAMP:20260515T080000\nDTSTART;TZID=Europe/Berlin:20260417")
    end = ics_bytes.find(b"END:VEVENT", start) + len(b"END:VEVENT\n")
    return ics_bytes[:start] + ics_bytes[end:]


def test_sync_deletes_removed_event_without_note(conn, user_with_feed, monkeypatch):
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    service.sync_feed(conn, user_with_feed)
    # Remove the Religion-KA from feed
    monkeypatch.setattr(service, "_fetch", _make_fetcher(_remove_religion_event(FIXTURE.read_bytes())))
    result = service.sync_feed(conn, user_with_feed)
    assert result.deleted == 1
    rows = events_repo.list_with_external_uid(conn, user_with_feed)
    assert len(rows) == 2
    assert "Religion" not in [r["subject"] for r in rows]


def test_sync_keeps_removed_event_with_linked_assessment(conn, user_with_feed, monkeypatch):
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    service.sync_feed(conn, user_with_feed)
    # Attach an assessment to the Religion-KA
    religion = next(r for r in events_repo.list_with_external_uid(conn, user_with_feed) if r["subject"] == "Religion")
    assessments_repo.create(
        conn, user_with_feed, "Religion", "schriftlich", "2026-04-17",
        grade=2.0, scheduled_event_id=religion["id"],
    )
    # Now remove Religion from feed
    monkeypatch.setattr(service, "_fetch", _make_fetcher(_remove_religion_event(FIXTURE.read_bytes())))
    result = service.sync_feed(conn, user_with_feed)
    assert result.deleted == 0
    rows = events_repo.list_with_external_uid(conn, user_with_feed)
    assert len(rows) == 3  # all still present


def test_sync_returns_error_on_network_failure(conn, user_with_feed, monkeypatch):
    def _raise(url, timeout=10.0):
        raise FeedFetchError("Netzwerk-Fehler: no route")
    monkeypatch.setattr(service, "_fetch", _raise)
    result = service.sync_feed(conn, user_with_feed)
    assert result.error is not None
    assert "Netzwerk-Fehler" in result.error
    # Persisted summary holds the error
    row = users_repo.get_user(conn, user_with_feed)
    assert row["ical_last_sync_summary"] is not None
    assert "Netzwerk-Fehler" in row["ical_last_sync_summary"]


def test_sync_no_url_returns_error(conn):
    uid = users_repo.create_user(conn, name="NoFeed")
    result = service.sync_feed(conn, uid)
    assert "Keine Feed-URL" in (result.error or "")


def test_sync_persists_last_sync_at_on_success(conn, user_with_feed, monkeypatch):
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    service.sync_feed(conn, user_with_feed)
    row = users_repo.get_user(conn, user_with_feed)
    assert row["ical_last_sync_at"] is not None
    assert row["ical_last_sync_at"].startswith("20")


def test_sync_persists_multi_day_ferien_to_calendar_events(monkeypatch, conn, user_with_feed):
    from school_test_engine.storage import calendar_events_repo
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:abc\nSUMMARY:Sommerferien\n"
        b"DTSTART;VALUE=DATE:20260707\nDTEND;VALUE=DATE:20260817\n"
        b"CATEGORIES:Ferien\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url, timeout=10.0: ics)
    result = service.sync_feed(conn, user_with_feed)
    assert result.error is None
    assert result.cal_added == 1
    rows = calendar_events_repo.list_for_user(conn, user_with_feed,
                                              today="2026-01-01",
                                              timeframe="all", kinds={"ferien"})
    assert len(rows) == 1
    assert rows[0]["title"] == "Sommerferien"
    assert rows[0]["start_date"] == "2026-07-07"
    assert rows[0]["end_date"] == "2026-08-16"


def test_sync_persists_single_day_frei(monkeypatch, conn, user_with_feed):
    from school_test_engine.storage import calendar_events_repo
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:p1\nSUMMARY:Paedagogischer Tag\n"
        b"DTSTART;VALUE=DATE:20260512\nDTEND;VALUE=DATE:20260513\n"
        b"CATEGORIES:Ferien\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url, timeout=10.0: ics)
    service.sync_feed(conn, user_with_feed)
    rows = calendar_events_repo.list_for_user(conn, user_with_feed,
                                              today="2026-01-01", timeframe="all",
                                              kinds={"frei"})
    assert len(rows) == 1
    assert rows[0]["kind"] == "frei"


def test_sync_persists_event_kind_for_wettbewerb(monkeypatch, conn, user_with_feed):
    from school_test_engine.storage import calendar_events_repo
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:w1\nSUMMARY:Mathewettbewerb\n"
        b"DTSTART;TZID=Europe/Berlin:20260428T112500\n"
        b"DTEND;TZID=Europe/Berlin:20260428T125500\n"
        b"CATEGORIES:Arbeiten\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url, timeout=10.0: ics)
    service.sync_feed(conn, user_with_feed)
    rows = calendar_events_repo.list_for_user(conn, user_with_feed,
                                              today="2026-01-01", timeframe="all",
                                              kinds={"event"})
    assert len(rows) == 1
    assert rows[0]["title"] == "Mathewettbewerb"


def test_sync_updates_calendar_event_when_date_changes(monkeypatch, conn, user_with_feed):
    ics_v1 = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\nUID:f1\nSUMMARY:Herbst\n"
        b"DTSTART;VALUE=DATE:20261019\nDTEND;VALUE=DATE:20261101\n"
        b"CATEGORIES:Ferien\nEND:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url, timeout=10.0: ics_v1)
    service.sync_feed(conn, user_with_feed)

    ics_v2 = ics_v1.replace(b"20261019", b"20261020").replace(b"20261101", b"20261102")
    monkeypatch.setattr(service, "_fetch", lambda url, timeout=10.0: ics_v2)
    result = service.sync_feed(conn, user_with_feed)
    assert result.cal_updated == 1


def test_sync_deletes_calendar_event_when_gone_from_feed(monkeypatch, conn, user_with_feed):
    from school_test_engine.storage import calendar_events_repo
    ics_v1 = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\nUID:f1\nSUMMARY:Herbst\n"
        b"DTSTART;VALUE=DATE:20261019\nDTEND;VALUE=DATE:20261101\n"
        b"CATEGORIES:Ferien\nEND:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url, timeout=10.0: ics_v1)
    service.sync_feed(conn, user_with_feed)

    ics_v2 = b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\nEND:VCALENDAR\n"
    monkeypatch.setattr(service, "_fetch", lambda url, timeout=10.0: ics_v2)
    result = service.sync_feed(conn, user_with_feed)
    assert result.cal_deleted == 1
    assert calendar_events_repo.list_external_uids(conn, user_with_feed) == set()


def test_sync_mixed_feed_writes_to_both_tables(monkeypatch, conn, user_with_feed):
    from school_test_engine.storage import calendar_events_repo, events_repo
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\nUID:f1\nSUMMARY:Sommer\n"
        b"DTSTART;VALUE=DATE:20260707\nDTEND;VALUE=DATE:20260817\n"
        b"CATEGORIES:Ferien\nEND:VEVENT\n"
        b"BEGIN:VEVENT\n"
        b"UID:20010101T000001-klausur-9084-14627-2026-03-10@x.org\n"
        b"SUMMARY:Mathe R8b Arbeit\nDESCRIPTION:Arbeit in Mathematik R8b (082M07-R)\n"
        b"DTSTART;TZID=Europe/Berlin:20260310T093500\n"
        b"DTEND;TZID=Europe/Berlin:20260310T110500\n"
        b"CATEGORIES:Arbeiten\nEND:VEVENT\n"
        b"END:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url, timeout=10.0: ics)
    result = service.sync_feed(conn, user_with_feed)
    assert result.added == 1
    assert result.cal_added == 1
    assert len(events_repo.list_all(conn, user_with_feed)) == 1
    cal_rows = calendar_events_repo.list_for_user(
        conn, user_with_feed, today="2026-01-01", timeframe="all",
        kinds={"ferien", "frei", "event"},
    )
    assert len(cal_rows) == 1

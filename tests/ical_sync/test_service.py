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


def test_sync_keeps_removed_event_with_note(conn, user_with_feed, monkeypatch):
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

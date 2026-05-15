"""Orchestrate fetch → parse → classify → extract → diff → apply.

`_fetch` is a module-level indirection so tests can monkeypatch it cleanly
without touching urllib.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from ..storage import assessments_repo, events_repo, users_repo
from . import classifier, extractor, fetcher, parser
from .extractor import EventRecord
from .fetcher import FeedFetchError


@dataclass(frozen=True)
class SyncResult:
    added: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0
    error: str | None = None
    synced_at: str = ""


# Indirection for tests
_fetch = fetcher.fetch_feed


def sync_feed(conn: sqlite3.Connection, user_id: int) -> SyncResult:
    user = users_repo.get_user(conn, user_id)
    if user is None or not user["ical_feed_url"]:
        return SyncResult(error="Keine Feed-URL hinterlegt")
    url = user["ical_feed_url"]
    try:
        raw_bytes = _fetch(url)
        events = parser.parse_events(raw_bytes)
    except (FeedFetchError, ValueError) as e:
        return _persist_error(conn, user_id, str(e))

    klausuren = [e for e in events if classifier.is_klausur_event(e)]
    records: list[EventRecord] = []
    skipped = 0
    for v in klausuren:
        rec = extractor.to_event_record(v)
        if rec is None:
            skipped += 1
        else:
            records.append(rec)

    adds, updates, deletes = _diff(conn, user_id, records)
    _apply(conn, user_id, adds, updates, deletes)
    return _persist_summary(conn, user_id, len(adds), len(updates), len(deletes), skipped)


def _diff(conn, user_id, feed_records: list[EventRecord]):
    feed_by_uid = {r.external_uid: r for r in feed_records}
    db_rows = events_repo.list_with_external_uid(conn, user_id)
    db_by_uid = {r["external_uid"]: r for r in db_rows}

    adds = [r for uid, r in feed_by_uid.items() if uid not in db_by_uid]
    updates = [
        (r, db_by_uid[r.external_uid])
        for uid, r in feed_by_uid.items()
        if uid in db_by_uid and _has_changes(r, db_by_uid[uid])
    ]
    delete_candidates = [row for uid, row in db_by_uid.items() if uid not in feed_by_uid]
    deletes = [
        row for row in delete_candidates
        if assessments_repo.find_by_event(conn, row["id"]) is None
    ]
    return adds, updates, deletes


def _has_changes(rec: EventRecord, db_row) -> bool:
    return (
        rec.event_date != db_row["event_date"]
        or rec.subject != db_row["subject"]
        or rec.kind != db_row["kind"]
    )


def _apply(conn, user_id, adds, updates, deletes):
    for rec in adds:
        events_repo.create(
            conn, user_id,
            rec.subject, rec.kind, rec.event_date,
            external_uid=rec.external_uid,
            external_source="schulportal_hessen",
        )
    for rec, _ in updates:
        events_repo.update_by_external_uid(
            conn, user_id, rec.external_uid,
            subject=rec.subject, kind=rec.kind, event_date=rec.event_date,
        )
    for row in deletes:
        events_repo.delete(conn, row["id"])


def _persist_summary(conn, user_id, added, updated, deleted, skipped) -> SyncResult:
    now = datetime.now().isoformat(timespec="seconds")
    summary_json = json.dumps({
        "added": added, "updated": updated, "deleted": deleted, "skipped": skipped, "error": None,
    })
    users_repo.update_user(
        conn, user_id,
        ical_last_sync_at=now,
        ical_last_sync_summary=summary_json,
    )
    return SyncResult(added=added, updated=updated, deleted=deleted, skipped=skipped, synced_at=now)


def _persist_error(conn, user_id, error_msg: str) -> SyncResult:
    now = datetime.now().isoformat(timespec="seconds")
    summary_json = json.dumps({"added": 0, "updated": 0, "deleted": 0, "skipped": 0, "error": error_msg})
    users_repo.update_user(
        conn, user_id,
        ical_last_sync_at=now,
        ical_last_sync_summary=summary_json,
    )
    return SyncResult(error=error_msg, synced_at=now)

# src/school_test_engine/ical_sync/service.py
"""Orchestrate fetch → parse → classify → split → diff → apply.

KAs land in scheduled_events (Phase 7-Pfad); Ferien/Frei/Event in calendar_events
(Phase 17). Both paths run during the same sync_feed call.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from ..storage import (
    assessments_repo, calendar_events_repo, events_repo, users_repo,
)
from . import classifier, extractor, fetcher, parser
from .extractor import EventRecord
from .fetcher import FeedFetchError


@dataclass(frozen=True)
class SyncResult:
    added: int = 0
    updated: int = 0
    deleted: int = 0
    cal_added: int = 0
    cal_updated: int = 0
    cal_deleted: int = 0
    skipped: int = 0
    error: str | None = None
    synced_at: str = ""


_fetch = fetcher.fetch_feed


@dataclass(frozen=True)
class _CalRecord:
    external_uid: str
    kind: str
    title: str
    start_date: str
    end_date: str


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

    klausuren: list[EventRecord] = []
    cal_records: list[_CalRecord] = []
    skipped = 0

    for v in events:
        kind = classifier.classify(v)
        if kind is None:
            skipped += 1
            continue
        if kind == "klausur":
            rec = extractor.to_event_record(v)
            if rec is None:
                skipped += 1
            else:
                klausuren.append(rec)
        else:
            cal_records.append(_CalRecord(
                external_uid=v.uid,
                kind=kind,
                title=v.summary,
                start_date=v.dtstart_date,
                end_date=v.dtend_date,
            ))

    adds, updates, deletes = _diff_klausuren(conn, user_id, klausuren)
    _apply_klausuren(conn, user_id, adds, updates, deletes)

    cal_adds, cal_updates, cal_deletes = _diff_calendar(conn, user_id, cal_records)
    _apply_calendar(conn, user_id, cal_adds, cal_updates, cal_deletes)

    return _persist_summary(
        conn, user_id,
        added=len(adds), updated=len(updates), deleted=len(deletes),
        cal_added=len(cal_adds), cal_updated=len(cal_updates),
        cal_deleted=len(cal_deletes),
        skipped=skipped,
    )


def _diff_klausuren(conn, user_id, feed_records: list[EventRecord]):
    feed_by_uid = {r.external_uid: r for r in feed_records}
    db_rows = events_repo.list_with_external_uid(conn, user_id)
    db_by_uid = {r["external_uid"]: r for r in db_rows}

    adds = [r for uid, r in feed_by_uid.items() if uid not in db_by_uid]
    updates = [
        (r, db_by_uid[r.external_uid])
        for uid, r in feed_by_uid.items()
        if uid in db_by_uid and _has_klausur_changes(r, db_by_uid[uid])
    ]
    delete_candidates = [row for uid, row in db_by_uid.items() if uid not in feed_by_uid]
    deletes = [
        row for row in delete_candidates
        if assessments_repo.find_by_event(conn, row["id"]) is None
    ]
    return adds, updates, deletes


def _has_klausur_changes(rec: EventRecord, db_row) -> bool:
    return (
        rec.event_date != db_row["event_date"]
        or rec.subject != db_row["subject"]
        or rec.kind != db_row["kind"]
    )


def _apply_klausuren(conn, user_id, adds, updates, deletes):
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


def _diff_calendar(conn, user_id, feed_records: list[_CalRecord]):
    feed_by_uid = {r.external_uid: r for r in feed_records}
    db_rows = calendar_events_repo.list_with_external_uid(conn, user_id)
    db_by_uid = {r["external_uid"]: r for r in db_rows}

    adds = [r for uid, r in feed_by_uid.items() if uid not in db_by_uid]
    updates = [
        r for uid, r in feed_by_uid.items()
        if uid in db_by_uid and _has_calendar_changes(r, db_by_uid[uid])
    ]
    deletes = [row for uid, row in db_by_uid.items() if uid not in feed_by_uid]
    return adds, updates, deletes


def _has_calendar_changes(rec: _CalRecord, db_row) -> bool:
    return (
        rec.kind != db_row["kind"]
        or rec.title != db_row["title"]
        or rec.start_date != db_row["start_date"]
        or rec.end_date != db_row["end_date"]
    )


def _apply_calendar(conn, user_id, adds, updates, deletes):
    for rec in adds:
        calendar_events_repo.create(
            conn,
            user_id=user_id,
            kind=rec.kind,
            title=rec.title,
            start_date=rec.start_date,
            end_date=rec.end_date,
            external_uid=rec.external_uid,
            external_source="schulportal_hessen",
        )
    for rec in updates:
        calendar_events_repo.update_by_external_uid(
            conn,
            user_id=user_id,
            external_uid=rec.external_uid,
            kind=rec.kind, title=rec.title,
            start_date=rec.start_date, end_date=rec.end_date,
        )
    for row in deletes:
        calendar_events_repo.delete_by_external_uid(conn, user_id, row["external_uid"])


def _persist_summary(
    conn, user_id, *,
    added, updated, deleted,
    cal_added, cal_updated, cal_deleted,
    skipped,
) -> SyncResult:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary_json = json.dumps({
        "added": added, "updated": updated, "deleted": deleted,
        "cal_added": cal_added, "cal_updated": cal_updated, "cal_deleted": cal_deleted,
        "skipped": skipped, "error": None,
    })
    users_repo.update_user(
        conn, user_id,
        ical_last_sync_at=now,
        ical_last_sync_summary=summary_json,
    )
    return SyncResult(
        added=added, updated=updated, deleted=deleted,
        cal_added=cal_added, cal_updated=cal_updated, cal_deleted=cal_deleted,
        skipped=skipped, synced_at=now,
    )


def _persist_error(conn, user_id, error_msg: str) -> SyncResult:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary_json = json.dumps({
        "added": 0, "updated": 0, "deleted": 0,
        "cal_added": 0, "cal_updated": 0, "cal_deleted": 0,
        "skipped": 0, "error": error_msg,
    })
    users_repo.update_user(
        conn, user_id,
        ical_last_sync_at=now,
        ical_last_sync_summary=summary_json,
    )
    return SyncResult(error=error_msg, synced_at=now)

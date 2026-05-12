from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class EventCardData:
    event_id: int
    subject: str
    kind: str
    event_date: str            # ISO YYYY-MM-DD
    days_until: int            # negative if event_date in past
    topics: list[str]
    note: str | None
    linked_assessment_id: int | None


def upcoming_events_for_menu(
    conn: sqlite3.Connection, user_id: int, today: date, limit: int = 3
) -> list[EventCardData]:
    today_iso = today.isoformat()
    cur = conn.execute(
        """
        SELECT e.*, a.id AS assessment_id
        FROM scheduled_events e
        LEFT JOIN assessments a ON a.scheduled_event_id = e.id
        WHERE e.user_id = ? AND e.event_date >= ?
        ORDER BY e.event_date ASC, e.created_at ASC
        LIMIT ?
        """,
        (user_id, today_iso, limit),
    )
    out: list[EventCardData] = []
    for row in cur.fetchall():
        event_d = datetime.fromisoformat(row["event_date"]).date()
        days = (event_d - today).days
        out.append(EventCardData(
            event_id=row["id"],
            subject=row["subject"],
            kind=row["kind"],
            event_date=row["event_date"],
            days_until=days,
            topics=json.loads(row["topics"] or "[]"),
            note=row["note"],
            linked_assessment_id=row["assessment_id"],
        ))
    return out

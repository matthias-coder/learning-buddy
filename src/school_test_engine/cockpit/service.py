from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date


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
        SELECT e.*,
               (SELECT a.id
                FROM assessments a
                WHERE a.scheduled_event_id = e.id
                ORDER BY a.created_at ASC, a.id ASC
                LIMIT 1) AS assessment_id
        FROM scheduled_events e
        WHERE e.user_id = ? AND e.event_date >= ?
        ORDER BY e.event_date ASC, e.created_at ASC
        LIMIT ?
        """,
        (user_id, today_iso, limit),
    )
    out: list[EventCardData] = []
    for row in cur.fetchall():
        event_d = date.fromisoformat(row["event_date"])
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


@dataclass(frozen=True)
class ComparisonData:
    assessment_id: int
    subject: str
    attempts_count: int
    attempts_grade_avg: float
    real_grade: float
    delta: float          # real - app_avg (positive = app was easier, KA worse)
    delta_label: str


_LABEL_BETTER = "Du warst in der KA besser als in App-Übungen ↑"
_LABEL_WORSE = "Du warst in der KA schlechter als in App-Übungen ↓"
_LABEL_SIMILAR = "App-Übungen und echte KA waren sehr ähnlich"


def _delta_label(delta: float) -> str:
    if delta < -0.2:
        return _LABEL_BETTER
    if delta > 0.2:
        return _LABEL_WORSE
    return _LABEL_SIMILAR


def comparison_for_assessment(
    conn: sqlite3.Connection, assessment_id: int
) -> ComparisonData | None:
    """Compute app-practice vs real grade comparison for one assessment.

    Window: attempts in the same subject finished between the previous
    scheduled_event (same subject) and this assessment's event_date.
    If no previous event: all attempts up to event_date.
    Returns None if the assessment has no scheduled_event_id or no
    matching attempts in the window.
    """
    a = conn.execute(
        "SELECT * FROM assessments WHERE id = ?", (assessment_id,)
    ).fetchone()
    if a is None or a["scheduled_event_id"] is None:
        return None
    event = conn.execute(
        "SELECT * FROM scheduled_events WHERE id = ?", (a["scheduled_event_id"],)
    ).fetchone()
    if event is None:
        return None

    # Find previous event of same subject for the same user
    prev = conn.execute(
        """
        SELECT MAX(event_date) AS prev_date
        FROM scheduled_events
        WHERE user_id = ? AND subject = ? AND event_date < ?
        """,
        (a["user_id"], a["subject"], event["event_date"]),
    ).fetchone()
    prev_date = prev["prev_date"] if prev else None

    # Find attempts in window
    if prev_date is None:
        cur = conn.execute(
            """
            SELECT AVG(att.note) AS avg_note, COUNT(*) AS n
            FROM attempts att
            JOIN tests t ON t.id = att.test_id
            WHERE att.user_id = ?
              AND att.completed = 1
              AND t.subject = ?
              AND date(att.finished_at) <= ?
            """,
            (a["user_id"], a["subject"], event["event_date"]),
        )
    else:
        cur = conn.execute(
            """
            SELECT AVG(att.note) AS avg_note, COUNT(*) AS n
            FROM attempts att
            JOIN tests t ON t.id = att.test_id
            WHERE att.user_id = ?
              AND att.completed = 1
              AND t.subject = ?
              AND date(att.finished_at) > ?
              AND date(att.finished_at) <= ?
            """,
            (a["user_id"], a["subject"], prev_date, event["event_date"]),
        )
    row = cur.fetchone()
    n = int(row["n"] or 0)
    if n == 0:
        return None
    app_avg = float(row["avg_note"])
    real = float(a["grade"])
    delta = round(real - app_avg, 2)
    return ComparisonData(
        assessment_id=assessment_id,
        subject=a["subject"],
        attempts_count=n,
        attempts_grade_avg=round(app_avg, 2),
        real_grade=real,
        delta=delta,
        delta_label=_delta_label(delta),
    )

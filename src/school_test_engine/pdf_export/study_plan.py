"""Phase 14 Track D: Render a study plan PDF for an upcoming KA."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from html import escape

from ..storage import events_repo
from ._common import html_header, html_footer


KIND_LABELS = {
    "klassenarbeit": "Klassenarbeit",
    "klausur": "Klausur",
    "test": "Test",
    "sonstiges": "Sonstiges",
}


def _topic_mastery(conn: sqlite3.Connection, user_id: int, subject: str, topic: str) -> tuple[int, int]:
    """Returns (correct, total) for this user/subject/topic across all attempts."""
    row = conn.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct,
          COUNT(*) AS total
        FROM answers a
        JOIN questions q ON q.id = a.question_id
        JOIN tests t     ON t.id = q.test_id
        WHERE t.user_id = ? AND t.subject = ? AND q.topic = ?
        """,
        (user_id, subject, topic),
    ).fetchone()
    return int(row["correct"] or 0), int(row["total"] or 0)


def _mastery_bar(correct: int, total: int) -> str:
    if total == 0:
        return "○○○○○"
    filled = round(5 * correct / total)
    filled = max(0, min(5, filled))
    return "●" * filled + "○" * (5 - filled)


def export_study_plan(conn: sqlite3.Connection, event_id: int) -> str:
    ev = events_repo.get(conn, event_id)
    if ev is None:
        raise ValueError(f"Event {event_id} not found")

    event_date = date.fromisoformat(ev["event_date"])
    today = date.today()
    days_until = (event_date - today).days
    if days_until == 0:
        countdown = "heute"
    elif days_until > 0:
        countdown = f"in {days_until} Tagen"
    else:
        countdown = f"vor {abs(days_until)} Tagen"
    subject = ev["subject"]
    kind = KIND_LABELS.get(ev["kind"], "Termin")
    topics = json.loads(ev["topics"] or "[]")
    user_id = ev["user_id"]

    parts = [
        html_header(f"{escape(subject)} {escape(kind)}"),
        "<div class='eyebrow'>LERNPLAN</div>",
        f"<p>{escape(event_date.strftime('%d.%m.%Y'))} · {escape(countdown)}</p>",
        "<h2>Themen der KA</h2>",
    ]

    if not topics:
        parts.append("<p>Keine Themen eingetragen.</p>")
    else:
        parts.append("<table>")
        parts.append("<tr><th>Thema</th><th>Stand</th><th>Versuche</th></tr>")
        rated: list[tuple[str, int, int]] = []
        for topic in topics:
            correct, total = _topic_mastery(conn, user_id, subject, topic)
            rated.append((topic, correct, total))
            bar = _mastery_bar(correct, total)
            last = f"{correct}/{total}" if total > 0 else "noch nicht geübt"
            parts.append(
                f"<tr><td>{escape(topic)}</td><td>{bar}</td><td>{escape(last)}</td></tr>"
            )
        parts.append("</table>")

        def _ratio(t):
            _, correct, total = t
            if total == 0:
                return -1.0
            return correct / total

        sorted_topics = sorted(rated, key=_ratio)
        parts.append("<h2>Empfehlung</h2>")
        parts.append("<ol>")
        for topic, correct, total in sorted_topics:
            if total == 0:
                hint = "noch nicht geübt"
            elif correct / total < 0.6:
                hint = "schwach"
            else:
                hint = "zur Sicherheit"
            parts.append(f"<li>{escape(topic)} — {hint}</li>")
        parts.append("</ol>")

    parts.append(html_footer())
    return "".join(parts)

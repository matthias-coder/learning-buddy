from __future__ import annotations

import json
import sqlite3
from typing import Iterable


def create(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str,
    kind: str,
    event_date: str,
    *,
    topics: Iterable[str] | None = None,
    note: str | None = None,
    external_uid: str | None = None,
    external_source: str | None = None,
) -> int:
    topics_json = json.dumps(list(topics) if topics else [])
    cur = conn.execute(
        """
        INSERT INTO scheduled_events
            (user_id, subject, kind, event_date, topics, note, external_uid, external_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, subject, kind, event_date, topics_json, note, external_uid, external_source),
    )
    conn.commit()
    eid = cur.lastrowid
    assert eid is not None
    return eid


def get(conn: sqlite3.Connection, event_id: int) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM scheduled_events WHERE id = ?", (event_id,))
    return cur.fetchone()


def list_upcoming(
    conn: sqlite3.Connection, user_id: int, today: str, limit: int = 3
) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM scheduled_events
        WHERE user_id = ? AND event_date >= ?
        ORDER BY event_date ASC, created_at ASC
        LIMIT ?
        """,
        (user_id, today, limit),
    )
    return cur.fetchall()


def list_all(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM scheduled_events
        WHERE user_id = ?
        ORDER BY event_date DESC, created_at DESC
        """,
        (user_id,),
    )
    return cur.fetchall()


_SENTINEL = object()


def update(
    conn: sqlite3.Connection,
    event_id: int,
    *,
    subject: str | None = None,
    kind: str | None = None,
    event_date: str | None = None,
    topics: Iterable[str] | None = _SENTINEL,  # type: ignore[assignment]
    note=_SENTINEL,
) -> None:
    fields: list[str] = []
    values: list = []
    if subject is not None:
        fields.append("subject = ?"); values.append(subject)
    if kind is not None:
        fields.append("kind = ?"); values.append(kind)
    if event_date is not None:
        fields.append("event_date = ?"); values.append(event_date)
    if topics is not _SENTINEL:
        fields.append("topics = ?"); values.append(json.dumps(list(topics or [])))
    if note is not _SENTINEL:
        fields.append("note = ?"); values.append(note)
    if not fields:
        return
    values.append(event_id)
    conn.execute(f"UPDATE scheduled_events SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()


def delete(conn: sqlite3.Connection, event_id: int) -> None:
    conn.execute("DELETE FROM scheduled_events WHERE id = ?", (event_id,))
    conn.commit()


def list_with_external_uid(
    conn: sqlite3.Connection, user_id: int
) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM scheduled_events
        WHERE user_id = ? AND external_uid IS NOT NULL
        """,
        (user_id,),
    )
    return cur.fetchall()


def update_by_external_uid(
    conn: sqlite3.Connection,
    user_id: int,
    external_uid: str,
    *,
    subject: str,
    kind: str,
    event_date: str,
) -> None:
    conn.execute(
        """
        UPDATE scheduled_events
        SET subject = ?, kind = ?, event_date = ?
        WHERE user_id = ? AND external_uid = ?
        """,
        (subject, kind, event_date, user_id, external_uid),
    )
    conn.commit()

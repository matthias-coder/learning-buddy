from __future__ import annotations

import sqlite3


def create(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str,
    category: str,
    assessment_date: str,
    *,
    grade: float,
    points: float | None = None,
    max_points: float | None = None,
    note: str | None = None,
    scheduled_event_id: int | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO assessments
            (user_id, subject, category, assessment_date,
             grade, points, max_points, note, scheduled_event_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, subject, category, assessment_date,
         grade, points, max_points, note, scheduled_event_id),
    )
    conn.commit()
    aid = cur.lastrowid
    assert aid is not None
    return aid


def get(conn: sqlite3.Connection, assessment_id: int) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM assessments WHERE id = ?", (assessment_id,))
    return cur.fetchone()


def list_by_subject(
    conn: sqlite3.Connection, user_id: int, subject: str
) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM assessments
        WHERE user_id = ? AND subject = ?
        ORDER BY assessment_date DESC, created_at DESC
        """,
        (user_id, subject),
    )
    return cur.fetchall()


def list_all(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM assessments
        WHERE user_id = ?
        ORDER BY assessment_date DESC, created_at DESC
        """,
        (user_id,),
    )
    return cur.fetchall()


def find_by_event(conn: sqlite3.Connection, event_id: int) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT * FROM assessments WHERE scheduled_event_id = ? "
        "ORDER BY created_at ASC LIMIT 1",
        (event_id,),
    )
    return cur.fetchone()


_SENTINEL = object()


def update(
    conn: sqlite3.Connection,
    assessment_id: int,
    *,
    subject: str | None = None,
    category: str | None = None,
    assessment_date: str | None = None,
    grade: float | None = None,
    points=_SENTINEL,
    max_points=_SENTINEL,
    note=_SENTINEL,
    scheduled_event_id=_SENTINEL,
) -> None:
    fields: list[str] = []
    values: list = []
    if subject is not None:
        fields.append("subject = ?"); values.append(subject)
    if category is not None:
        fields.append("category = ?"); values.append(category)
    if assessment_date is not None:
        fields.append("assessment_date = ?"); values.append(assessment_date)
    if grade is not None:
        fields.append("grade = ?"); values.append(grade)
    if points is not _SENTINEL:
        fields.append("points = ?"); values.append(points)
    if max_points is not _SENTINEL:
        fields.append("max_points = ?"); values.append(max_points)
    if note is not _SENTINEL:
        fields.append("note = ?"); values.append(note)
    if scheduled_event_id is not _SENTINEL:
        fields.append("scheduled_event_id = ?"); values.append(scheduled_event_id)
    if not fields:
        return
    values.append(assessment_id)
    conn.execute(f"UPDATE assessments SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()


def delete(conn: sqlite3.Connection, assessment_id: int) -> None:
    conn.execute("DELETE FROM assessments WHERE id = ?", (assessment_id,))
    conn.commit()

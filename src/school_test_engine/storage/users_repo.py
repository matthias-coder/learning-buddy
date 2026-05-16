from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM users ORDER BY sort_order ASC, created_at ASC"
    )
    return cur.fetchall()


def get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cur.fetchone()


def count_users(conn: sqlite3.Connection) -> int:
    cur = conn.execute("SELECT COUNT(*) AS n FROM users")
    return int(cur.fetchone()["n"])


_SENTINEL = object()  # Sentinel um "Spalte nicht ändern" von "auf NULL setzen" zu trennen


def create_user(
    conn: sqlite3.Connection,
    name: str,
    avatar: str = "👤",
    *,
    avatar_image: bytes | None = None,
    birthday: str | None = None,
) -> int:
    next_sort = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM users"
    ).fetchone()["n"]
    cur = conn.execute(
        """
        INSERT INTO users (name, avatar, avatar_image, birthday, sort_order, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, avatar, avatar_image, birthday, next_sort, _now_iso()),
    )
    conn.commit()
    new_id = cur.lastrowid
    assert new_id is not None
    return new_id


def update_user(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    name: str | None = None,
    avatar: str | None = None,
    avatar_image=_SENTINEL,
    birthday=_SENTINEL,
    ai_style_briefing=_SENTINEL,
    grade=_SENTINEL,
    school_type=_SENTINEL,
    bundesland=_SENTINEL,
    school_name=_SENTINEL,
    school_year=_SENTINEL,
    sort_order: int | None = None,
    show_keyboard_hints: int | None = None,
    ical_feed_url=_SENTINEL,
    ical_last_sync_at=_SENTINEL,
    ical_last_sync_summary=_SENTINEL,
    calendar_show_klausuren: int | None = None,
    calendar_show_ferien: int | None = None,
    calendar_show_frei: int | None = None,
    calendar_show_events: int | None = None,
    calendar_timeframe: str | None = None,
) -> None:
    fields: list[str] = []
    values: list = []
    if name is not None:
        fields.append("name = ?"); values.append(name)
    if avatar is not None:
        fields.append("avatar = ?"); values.append(avatar)
    if avatar_image is not _SENTINEL:
        fields.append("avatar_image = ?"); values.append(avatar_image)
    if birthday is not _SENTINEL:
        fields.append("birthday = ?"); values.append(birthday)
    if ai_style_briefing is not _SENTINEL:
        fields.append("ai_style_briefing = ?"); values.append(ai_style_briefing)
    if grade is not _SENTINEL:
        fields.append("grade = ?"); values.append(grade)
    if school_type is not _SENTINEL:
        fields.append("school_type = ?"); values.append(school_type)
    if bundesland is not _SENTINEL:
        fields.append("bundesland = ?"); values.append(bundesland)
    if school_name is not _SENTINEL:
        fields.append("school_name = ?"); values.append(school_name)
    if school_year is not _SENTINEL:
        fields.append("school_year = ?"); values.append(school_year)
    if sort_order is not None:
        fields.append("sort_order = ?"); values.append(sort_order)
    if show_keyboard_hints is not None:
        fields.append("show_keyboard_hints = ?"); values.append(int(show_keyboard_hints))
    if ical_feed_url is not _SENTINEL:
        fields.append("ical_feed_url = ?"); values.append(ical_feed_url)
    if ical_last_sync_at is not _SENTINEL:
        fields.append("ical_last_sync_at = ?"); values.append(ical_last_sync_at)
    if ical_last_sync_summary is not _SENTINEL:
        fields.append("ical_last_sync_summary = ?"); values.append(ical_last_sync_summary)
    if calendar_show_klausuren is not None:
        fields.append("calendar_show_klausuren = ?"); values.append(int(calendar_show_klausuren))
    if calendar_show_ferien is not None:
        fields.append("calendar_show_ferien = ?"); values.append(int(calendar_show_ferien))
    if calendar_show_frei is not None:
        fields.append("calendar_show_frei = ?"); values.append(int(calendar_show_frei))
    if calendar_show_events is not None:
        fields.append("calendar_show_events = ?"); values.append(int(calendar_show_events))
    if calendar_timeframe is not None:
        fields.append("calendar_timeframe = ?"); values.append(calendar_timeframe)
    if not fields:
        return
    values.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()


def delete_user(conn: sqlite3.Connection, user_id: int) -> None:
    """Löscht User samt zugeordneter Tests/Versuche/Antworten.

    Manuelles Cascade: SQLite kann beim ALTER-TABLE-ADD-COLUMN keine FK-Spalte
    mit non-NULL Default anlegen, daher kein ON DELETE CASCADE im Schema.
    """
    # Versuche und ihre Antworten: über tests gehen, dann attempts direkt
    conn.execute(
        "DELETE FROM answers WHERE attempt_id IN "
        "(SELECT id FROM attempts WHERE user_id = ?)",
        (user_id,),
    )
    conn.execute("DELETE FROM attempts WHERE user_id = ?", (user_id,))
    # Tests + ihre Fragen (via ON DELETE CASCADE auf tests.id, das gibt es)
    conn.execute("DELETE FROM tests WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()

"""CRUD + filtered listing for calendar_events (Phase 17)."""
from __future__ import annotations

import sqlite3


def create(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    kind: str,
    title: str,
    start_date: str,
    end_date: str,
    external_uid: str | None = None,
    external_source: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO calendar_events
            (user_id, kind, title, start_date, end_date, external_uid, external_source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, kind, title, start_date, end_date, external_uid, external_source),
    )
    conn.commit()
    eid = cur.lastrowid
    assert eid is not None
    return eid


def list_for_user(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    today: str | None = None,
    timeframe: str = "future",
    kinds: set[str] | None = None,
) -> list[sqlite3.Row]:
    where = ["user_id = ?"]
    params: list = [user_id]

    if kinds:
        placeholders = ",".join("?" for _ in kinds)
        where.append(f"kind IN ({placeholders})")
        params.extend(kinds)

    if timeframe == "future" and today:
        where.append("end_date >= ?"); params.append(today)
    elif timeframe == "past" and today:
        where.append("end_date < ?"); params.append(today)
    # "all" → no date filter

    sql = (
        f"SELECT * FROM calendar_events WHERE {' AND '.join(where)} "
        f"ORDER BY start_date ASC, id ASC"
    )
    cur = conn.execute(sql, params)
    return cur.fetchall()


def list_external_uids(conn: sqlite3.Connection, user_id: int) -> set[str]:
    cur = conn.execute(
        "SELECT external_uid FROM calendar_events "
        "WHERE user_id = ? AND external_uid IS NOT NULL",
        (user_id,),
    )
    return {r["external_uid"] for r in cur.fetchall()}


def list_with_external_uid(
    conn: sqlite3.Connection, user_id: int
) -> list[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM calendar_events "
        "WHERE user_id = ? AND external_uid IS NOT NULL",
        (user_id,),
    )
    return cur.fetchall()


def update_by_external_uid(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    external_uid: str,
    kind: str,
    title: str,
    start_date: str,
    end_date: str,
) -> bool:
    cur = conn.execute(
        """
        UPDATE calendar_events
        SET kind = ?, title = ?, start_date = ?, end_date = ?
        WHERE user_id = ? AND external_uid = ?
        """,
        (kind, title, start_date, end_date, user_id, external_uid),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_by_external_uid(
    conn: sqlite3.Connection, user_id: int, external_uid: str
) -> bool:
    cur = conn.execute(
        "DELETE FROM calendar_events WHERE user_id = ? AND external_uid = ?",
        (user_id, external_uid),
    )
    conn.commit()
    return cur.rowcount > 0

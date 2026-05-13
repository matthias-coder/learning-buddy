from __future__ import annotations

import sqlite3


def upsert(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str,
    *,
    last_topic: str | None,
    last_count: int,
    last_dist: str,
) -> None:
    conn.execute(
        """
        INSERT INTO prompt_drafts
            (user_id, subject, last_topic, last_count, last_dist, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, subject) DO UPDATE SET
            last_topic = excluded.last_topic,
            last_count = excluded.last_count,
            last_dist  = excluded.last_dist,
            updated_at = excluded.updated_at
        """,
        (user_id, subject, last_topic, last_count, last_dist),
    )
    conn.commit()


def get(
    conn: sqlite3.Connection, user_id: int, subject: str
) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT * FROM prompt_drafts WHERE user_id = ? AND subject = ?",
        (user_id, subject),
    )
    return cur.fetchone()


def list_for_user(
    conn: sqlite3.Connection, user_id: int
) -> list[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM prompt_drafts WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    )
    return cur.fetchall()

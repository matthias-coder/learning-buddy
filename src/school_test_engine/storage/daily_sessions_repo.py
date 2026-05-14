from __future__ import annotations

import sqlite3


def start_session(
    conn: sqlite3.Connection,
    user_id: int,
    session_date: str,
    *,
    test_id: int | None,
    attempt_id: int | None,
    started_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO daily_sessions
            (user_id, session_date, test_id, attempt_id, started_at, completed_at)
        VALUES (?, ?, ?, ?, ?, NULL)
        """,
        (user_id, session_date, test_id, attempt_id, started_at),
    )
    conn.commit()


def complete_session(
    conn: sqlite3.Connection,
    user_id: int,
    session_date: str,
    *,
    completed_at: str,
) -> None:
    conn.execute(
        "UPDATE daily_sessions SET completed_at = ? "
        "WHERE user_id = ? AND session_date = ?",
        (completed_at, user_id, session_date),
    )
    conn.commit()


def get_for_today(
    conn: sqlite3.Connection, user_id: int, today: str
) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT * FROM daily_sessions WHERE user_id = ? AND session_date = ?",
        (user_id, today),
    )
    return cur.fetchone()


def find_by_attempt(
    conn: sqlite3.Connection, attempt_id: int
) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT * FROM daily_sessions WHERE attempt_id = ?",
        (attempt_id,),
    )
    return cur.fetchone()


def list_recent_completed_dates(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    since: str,
    until: str,
) -> list[str]:
    cur = conn.execute(
        """
        SELECT session_date FROM daily_sessions
        WHERE user_id = ?
          AND session_date >= ?
          AND session_date <= ?
          AND completed_at IS NOT NULL
        ORDER BY session_date DESC
        """,
        (user_id, since, until),
    )
    return [row["session_date"] for row in cur.fetchall()]

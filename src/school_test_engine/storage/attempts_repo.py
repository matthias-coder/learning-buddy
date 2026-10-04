from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


def start_attempt(
    conn: sqlite3.Connection,
    test_id: int,
    points_possible: int,
    user_id: int,
    shuffle_seed: int | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO attempts
            (test_id, started_at, points_possible, shuffle_seed, completed, current_index, user_id)
        VALUES (?, ?, ?, ?, 0, 0, ?)
        """,
        (
            test_id,
            datetime.now(timezone.utc).isoformat(),
            points_possible,
            shuffle_seed,
            user_id,
        ),
    )
    conn.commit()
    attempt_id = cur.lastrowid
    assert attempt_id is not None
    return attempt_id


def upsert_answer(
    conn: sqlite3.Connection,
    attempt_id: int,
    question_id: int,
    response: list[str] | str,
    points_earned: float,
    is_correct: bool,
    marked: bool = False,
) -> None:
    conn.execute(
        """
        INSERT INTO answers
            (attempt_id, question_id, response, points_earned, is_correct, marked)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(attempt_id, question_id) DO UPDATE SET
            response = excluded.response,
            points_earned = excluded.points_earned,
            is_correct = excluded.is_correct,
            marked = excluded.marked
        """,
        (
            attempt_id,
            question_id,
            json.dumps(response),
            points_earned,
            1 if is_correct else 0,
            1 if marked else 0,
        ),
    )
    conn.commit()


def set_marked(
    conn: sqlite3.Connection, attempt_id: int, question_id: int, marked: bool
) -> None:
    cur = conn.execute(
        "UPDATE answers SET marked = ? WHERE attempt_id = ? AND question_id = ?",
        (1 if marked else 0, attempt_id, question_id),
    )
    if cur.rowcount == 0:
        # Kein Answer-Row vorhanden — leeren Stub anlegen, damit Markierung persistiert
        conn.execute(
            """
            INSERT INTO answers
                (attempt_id, question_id, response, points_earned, is_correct, marked)
            VALUES (?, ?, ?, 0, 0, ?)
            """,
            (attempt_id, question_id, json.dumps([]), 1 if marked else 0),
        )
    conn.commit()


def update_current_index(
    conn: sqlite3.Connection, attempt_id: int, index: int
) -> None:
    conn.execute(
        "UPDATE attempts SET current_index = ? WHERE id = ?",
        (index, attempt_id),
    )
    conn.commit()


def finish_attempt(
    conn: sqlite3.Connection,
    attempt_id: int,
    points_earned: float,
    percent: float,
    note: int,
) -> None:
    conn.execute(
        """
        UPDATE attempts
        SET finished_at = ?, points_earned = ?, percent = ?, note = ?, completed = 1
        WHERE id = ?
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            points_earned,
            percent,
            note,
            attempt_id,
        ),
    )
    conn.commit()


def get_attempt(conn: sqlite3.Connection, attempt_id: int) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,))
    return cur.fetchone()


def find_incomplete_attempt(
    conn: sqlite3.Connection, user_id: int, test_id: int | None = None
) -> sqlite3.Row | None:
    if test_id is None:
        cur = conn.execute(
            """
            SELECT * FROM attempts
            WHERE completed = 0 AND user_id = ?
            ORDER BY started_at DESC LIMIT 1
            """,
            (user_id,),
        )
    else:
        cur = conn.execute(
            """
            SELECT * FROM attempts
            WHERE completed = 0 AND user_id = ? AND test_id = ?
            ORDER BY started_at DESC LIMIT 1
            """,
            (user_id, test_id),
        )
    return cur.fetchone()


def list_incomplete_attempts(
    conn: sqlite3.Connection, user_id: int
) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT a.*, t.title AS test_title, t.subject
        FROM attempts a JOIN tests t ON t.id = a.test_id
        WHERE a.completed = 0 AND a.user_id = ?
        ORDER BY a.started_at DESC, a.id DESC
        """,
        (user_id,),
    )
    return cur.fetchall()


def discard_attempt(conn: sqlite3.Connection, attempt_id: int) -> None:
    conn.execute("DELETE FROM attempts WHERE id = ?", (attempt_id,))
    conn.commit()


def get_answer_map(
    conn: sqlite3.Connection, attempt_id: int
) -> dict[int, sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM answers WHERE attempt_id = ?", (attempt_id,)
    )
    return {int(row["question_id"]): row for row in cur.fetchall()}


def list_attempts_for_test(conn: sqlite3.Connection, test_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM attempts
        WHERE test_id = ? AND completed = 1
        ORDER BY finished_at DESC
        """,
        (test_id,),
    )
    return cur.fetchall()


def list_all_attempts(
    conn: sqlite3.Connection, user_id: int
) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT a.*, t.title AS test_title, t.subject AS subject
        FROM attempts a JOIN tests t ON t.id = a.test_id
        WHERE a.completed = 1 AND a.user_id = ?
        ORDER BY a.finished_at DESC
        """,
        (user_id,),
    )
    return cur.fetchall()


def get_answers(conn: sqlite3.Connection, attempt_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT a.*, q.ext_id, q.prompt, q.prompt_math, q.topic,
               q.points AS question_points, q.explanation
        FROM answers a JOIN questions q ON q.id = a.question_id
        WHERE a.attempt_id = ?
        ORDER BY q.position
        """,
        (attempt_id,),
    )
    return cur.fetchall()


def topic_history(
    conn: sqlite3.Connection, user_id: int, subject: str | None = None
) -> list[sqlite3.Row]:
    """Pro (topic, attempt) ein Row: für Trend-Berechnung über mehrere Versuche."""
    if subject:
        cur = conn.execute(
            """
            SELECT q.topic,
                   t.id        AS attempt_id,
                   t.finished_at,
                   SUM(a.points_earned) AS earned,
                   SUM(q.points)        AS possible
            FROM answers a
            JOIN questions q ON q.id = a.question_id
            JOIN attempts  t ON t.id = a.attempt_id
            JOIN tests    ts ON ts.id = q.test_id
            WHERE t.completed = 1 AND t.user_id = ? AND ts.subject = ?
            GROUP BY q.topic, t.id
            ORDER BY q.topic, t.finished_at
            """,
            (user_id, subject),
        )
    else:
        cur = conn.execute(
            """
            SELECT q.topic,
                   t.id        AS attempt_id,
                   t.finished_at,
                   SUM(a.points_earned) AS earned,
                   SUM(q.points)        AS possible
            FROM answers a
            JOIN questions q ON q.id = a.question_id
            JOIN attempts  t ON t.id = a.attempt_id
            WHERE t.completed = 1 AND t.user_id = ?
            GROUP BY q.topic, t.id
            ORDER BY q.topic, t.finished_at
            """,
            (user_id,),
        )
    return cur.fetchall()


def topic_stats(
    conn: sqlite3.Connection, user_id: int, subject: str | None = None
) -> list[sqlite3.Row]:
    if subject:
        cur = conn.execute(
            """
            SELECT q.topic,
                   ts.subject          AS subject,
                   SUM(a.points_earned) AS earned,
                   SUM(q.points)        AS possible,
                   COUNT(*)             AS n_answers
            FROM answers a
            JOIN questions q ON q.id = a.question_id
            JOIN attempts  t ON t.id = a.attempt_id
            JOIN tests     ts ON ts.id = q.test_id
            WHERE t.completed = 1 AND t.user_id = ? AND ts.subject = ?
            GROUP BY q.topic, ts.subject
            ORDER BY (SUM(a.points_earned) * 1.0 / SUM(q.points)) ASC
            """,
            (user_id, subject),
        )
    else:
        cur = conn.execute(
            """
            SELECT q.topic,
                   ts.subject          AS subject,
                   SUM(a.points_earned) AS earned,
                   SUM(q.points)        AS possible,
                   COUNT(*)             AS n_answers
            FROM answers a
            JOIN questions q ON q.id = a.question_id
            JOIN attempts  t ON t.id = a.attempt_id
            JOIN tests     ts ON ts.id = q.test_id
            WHERE t.completed = 1 AND t.user_id = ?
            GROUP BY q.topic, ts.subject
            ORDER BY (SUM(a.points_earned) * 1.0 / SUM(q.points)) ASC
            """,
            (user_id,),
        )
    return cur.fetchall()

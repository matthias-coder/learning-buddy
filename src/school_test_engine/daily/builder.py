from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from random import Random

from ..models.test import REALSCHULE_DEFAULT_NOTENSCHLUESSEL


DAILY_SUBJECT = "Daily-5"
DAILY_TITLE_PREFIX = "Daily-5"


def has_enough_questions(conn: sqlite3.Connection, user_id: int, min_pool: int = 5) -> bool:
    """True if user has at least min_pool questions across non-synthetic tests."""
    n = conn.execute(
        """
        SELECT COUNT(DISTINCT q.id) AS n
        FROM questions q
        JOIN tests t ON t.id = q.test_id
        WHERE t.user_id = ? AND t.is_study = 0
        """,
        (user_id,),
    ).fetchone()["n"]
    return n >= min_pool


def build_daily_test(
    conn: sqlite3.Connection,
    user_id: int,
    today: date,
    seed: int | None = None,
) -> int | None:
    """Build a synthetic Daily-5 test with 5 questions from the user's weakest
    topics (2-2-1 split). Returns the new test_id, or None if pool insufficient.
    """
    if not has_enough_questions(conn, user_id):
        return None

    rng = Random(seed if seed is not None else today.toordinal())

    chosen_ids = _pick_question_ids(conn, user_id, rng)
    if len(chosen_ids) < 5:
        return None

    # Load full question rows in chosen order
    placeholders = ",".join(["?"] * len(chosen_ids))
    questions = conn.execute(
        f"SELECT * FROM questions WHERE id IN ({placeholders})",
        chosen_ids,
    ).fetchall()
    by_id = {q["id"]: q for q in questions}
    ordered = [by_id[qid] for qid in chosen_ids]

    title = f"{DAILY_TITLE_PREFIX} — {today.strftime('%d.%m.%Y')}"
    description = "Tägliche 5-Fragen-Session aus deinen schwächsten Themen."
    points_total = sum(int(q["points"]) for q in ordered)

    cur = conn.execute(
        """
        INSERT INTO tests
            (title, subject, grade, school_type, description, time_limit_min,
             notenschluessel, source_json, imported_at, is_study, user_id)
        VALUES (?, ?, ?, 'Realschule', ?, NULL, ?, '{}', ?, 1, ?)
        """,
        (
            title,
            DAILY_SUBJECT,
            8,
            description,
            json.dumps({str(k): v for k, v in REALSCHULE_DEFAULT_NOTENSCHLUESSEL.items()}),
            datetime.now(timezone.utc).isoformat(),
            user_id,
        ),
    )
    test_id = cur.lastrowid
    assert test_id is not None

    conn.executemany(
        """
        INSERT INTO questions
            (test_id, ext_id, position, type, topic, difficulty, points,
             prompt, prompt_math, payload, explanation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                test_id,
                f"dq{pos+1}",
                pos,
                q["type"],
                q["topic"],
                q["difficulty"],
                q["points"],
                q["prompt"],
                q["prompt_math"],
                q["payload"],
                q["explanation"],
            )
            for pos, q in enumerate(ordered)
        ],
    )
    conn.commit()
    return test_id


def _pick_question_ids(conn: sqlite3.Connection, user_id: int, rng: Random) -> list[int]:
    """Pick 5 question ids using 2-2-1 from the three weakest topics with fallback."""
    weak_topics = _weakest_topics(conn, user_id, threshold=0.80, limit=3)
    chosen: list[int] = []
    quotas = [2, 2, 1]
    for idx, topic_row in enumerate(weak_topics):
        qids = _random_question_ids_for_topic(
            conn, user_id, topic_row["topic"], topic_row["subject"],
            quotas[idx], rng, exclude=chosen,
        )
        chosen.extend(qids)

    # Fallback: fill up to 5 from any non-study question
    if len(chosen) < 5:
        fillers = _random_question_ids_global(conn, user_id, 5 - len(chosen), rng, exclude=chosen)
        chosen.extend(fillers)

    return chosen[:5]


def _weakest_topics(
    conn: sqlite3.Connection, user_id: int, threshold: float, limit: int,
) -> list[sqlite3.Row]:
    """Return topics with mastery < threshold, sorted ASC by mastery, top `limit`.
    Returns rows with at least 'topic' and 'subject' keys."""
    rows = conn.execute(
        """
        SELECT q.topic AS topic,
               ts.subject AS subject,
               SUM(a.points_earned) * 1.0 / SUM(q.points) AS mastery
        FROM answers a
        JOIN questions q ON q.id = a.question_id
        JOIN attempts t ON t.id = a.attempt_id
        JOIN tests   ts ON ts.id = q.test_id
        WHERE t.completed = 1 AND t.user_id = ? AND ts.is_study = 0
        GROUP BY q.topic, ts.subject
        HAVING mastery < ?
        ORDER BY mastery ASC
        LIMIT ?
        """,
        (user_id, threshold, limit),
    ).fetchall()
    return rows


def _random_question_ids_for_topic(
    conn: sqlite3.Connection,
    user_id: int,
    topic: str,
    subject: str,
    n: int,
    rng: Random,
    exclude: list[int],
) -> list[int]:
    if exclude:
        placeholders = ",".join(["?"] * len(exclude))
        exclude_clause = f"AND q.id NOT IN ({placeholders})"
        params = (user_id, topic, subject, *exclude)
    else:
        exclude_clause = ""
        params = (user_id, topic, subject)
    rows = conn.execute(
        f"""
        SELECT q.id FROM questions q
        JOIN tests t ON t.id = q.test_id
        WHERE t.user_id = ? AND t.is_study = 0
          AND q.topic = ? AND t.subject = ?
          {exclude_clause}
        """,
        params,
    ).fetchall()
    ids = [r["id"] for r in rows]
    rng.shuffle(ids)
    return ids[:n]


def _random_question_ids_global(
    conn: sqlite3.Connection,
    user_id: int,
    n: int,
    rng: Random,
    exclude: list[int],
) -> list[int]:
    if exclude:
        placeholders = ",".join(["?"] * len(exclude))
        exclude_clause = f"AND q.id NOT IN ({placeholders})"
        params = (user_id, *exclude)
    else:
        exclude_clause = ""
        params = (user_id,)
    rows = conn.execute(
        f"""
        SELECT q.id FROM questions q
        JOIN tests t ON t.id = q.test_id
        WHERE t.user_id = ? AND t.is_study = 0
          {exclude_clause}
        """,
        params,
    ).fetchall()
    ids = [r["id"] for r in rows]
    rng.shuffle(ids)
    return ids[:n]

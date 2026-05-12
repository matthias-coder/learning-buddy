from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..models.test import (
    MultiChoiceQuestion,
    Question,
    ShortAnswerQuestion,
    SingleChoiceQuestion,
    Test,
)


def insert_test(
    conn: sqlite3.Connection, test: Test, source_json: str, user_id: int
) -> int:
    cur = conn.execute(
        """
        INSERT INTO tests
            (title, subject, grade, school_type, description, time_limit_min,
             notenschluessel, source_json, imported_at, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            test.title,
            test.subject,
            test.grade,
            test.school_type,
            test.description,
            test.time_limit_minutes,
            json.dumps(test.effective_notenschluessel()),
            source_json,
            datetime.now(timezone.utc).isoformat(),
            user_id,
        ),
    )
    test_id = cur.lastrowid
    assert test_id is not None

    for position, q in enumerate(test.questions):
        payload = _question_payload(q)
        conn.execute(
            """
            INSERT INTO questions
                (test_id, ext_id, position, type, topic, difficulty, points,
                 prompt, prompt_math, payload, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                test_id,
                q.id,
                position,
                q.type,
                q.topic,
                q.difficulty,
                q.points,
                q.prompt,
                q.prompt_math,
                json.dumps(payload),
                q.explanation,
            ),
        )
    conn.commit()
    return test_id


def _question_payload(q: Question) -> dict:
    if isinstance(q, SingleChoiceQuestion):
        return {
            "choices": [c.model_dump() for c in q.choices],
            "correct": q.correct,
        }
    if isinstance(q, MultiChoiceQuestion):
        return {
            "choices": [c.model_dump() for c in q.choices],
            "correct": q.correct,
            "scoring": q.scoring,
        }
    if isinstance(q, ShortAnswerQuestion):
        return {
            "accepted_answers": q.accepted_answers,
            "case_sensitive": q.case_sensitive,
            "trim_whitespace": q.trim_whitespace,
        }
    raise TypeError(f"unbekannter Fragetyp: {type(q).__name__}")


def list_tests(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str | None = None,
    include_study: bool = False,
) -> list[sqlite3.Row]:
    where = ["t.user_id = ?"]
    params: list = [user_id]
    if not include_study:
        where.append("t.is_study = 0")
    if subject:
        where.append("t.subject = ?")
        params.append(subject)
    where_clause = "WHERE " + " AND ".join(where)
    cur = conn.execute(
        f"""
        SELECT t.*, COUNT(q.id) AS n_questions, SUM(q.points) AS total_points
        FROM tests t LEFT JOIN questions q ON q.test_id = t.id
        {where_clause}
        GROUP BY t.id
        ORDER BY t.imported_at DESC
        """,
        params,
    )
    return cur.fetchall()


def get_test(conn: sqlite3.Connection, test_id: int) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM tests WHERE id = ?", (test_id,))
    return cur.fetchone()


def get_questions(conn: sqlite3.Connection, test_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM questions WHERE test_id = ? ORDER BY position",
        (test_id,),
    )
    return cur.fetchall()


def delete_test(conn: sqlite3.Connection, test_id: int) -> None:
    conn.execute("DELETE FROM tests WHERE id = ?", (test_id,))
    conn.commit()

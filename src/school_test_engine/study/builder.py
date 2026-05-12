from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..models.test import REALSCHULE_DEFAULT_NOTENSCHLUESSEL


STUDY_TITLE_PREFIX = "Übung"


class StudyBuildError(Exception):
    """Raised when a study session cannot be built (no matching questions)."""


def build_study_test(
    conn: sqlite3.Connection,
    topic: str,
    subject: str,
    user_id: int,
    max_questions: int = 10,
) -> int:
    """Erzeuge einen synthetischen Test aus existierenden Fragen für ein Thema.

    Es werden alle Fragen mit exakt diesem Topic in Tests dieses Fachs und Users
    gesucht (ohne andere Übungstests). Bis zu `max_questions` werden in den neuen
    Test kopiert.

    Returns: test_id des neuen Übungs-Tests.
    Raises: StudyBuildError wenn keine passenden Fragen vorhanden.
    """
    rows = conn.execute(
        """
        SELECT q.* FROM questions q
        JOIN tests t ON t.id = q.test_id
        WHERE t.subject = ? AND t.user_id = ? AND q.topic = ? AND t.is_study = 0
        ORDER BY q.points DESC, q.id
        LIMIT ?
        """,
        (subject, user_id, topic, max_questions),
    ).fetchall()

    if not rows:
        raise StudyBuildError(
            f"Keine Fragen für Thema '{topic}' im Fach {subject} gefunden."
        )

    title = f"{STUDY_TITLE_PREFIX}: {topic}"
    cur = conn.execute(
        """
        INSERT INTO tests
            (title, subject, grade, school_type, description, time_limit_min,
             notenschluessel, source_json, imported_at, is_study, user_id)
        VALUES (?, ?, ?, 'Realschule', ?, NULL, ?, '{}', ?, 1, ?)
        """,
        (
            title,
            subject,
            8,
            f"Übungs-Session aus {len(rows)} Fragen zu '{topic}'.",
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
                f"sq{pos+1}",
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
            for pos, q in enumerate(rows)
        ],
    )

    conn.commit()
    return test_id

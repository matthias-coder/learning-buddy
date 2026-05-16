from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timezone

from ..models.test import REALSCHULE_DEFAULT_NOTENSCHLUESSEL
from . import queries

_ERR_EXT_RE = re.compile(r"^err:(\d+)$")

_FEHLER_TITLE_PREFIX = "Fehler-Übung"
_FEHLER_DESCRIPTION = "Wiederholung von Fragen, die noch nicht sitzen."


def has_open_errors(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str | None = None,
) -> bool:
    """True wenn mindestens 1 offene Fehlerheft-Position für den User existiert
    (optional gefiltert nach Fach)."""
    counts = queries.count_open(conn, user_id)
    if subject is None:
        return any(v > 0 for v in counts.values())
    return counts.get(subject, 0) > 0


def _root_question_id(q_row) -> int:
    """Wenn ext_id 'err:N' matched, returnt N; sonst die eigene id.
    Hält die Kette flach: max 1 Hop Indirektion, egal wie oft kopiert."""
    ext = q_row["ext_id"] if isinstance(q_row, sqlite3.Row) else q_row.get("ext_id")
    if ext:
        m = _ERR_EXT_RE.match(ext)
        if m:
            return int(m.group(1))
    return int(q_row["id"])


def _find_open_practice_test(
    conn: sqlite3.Connection, user_id: int, subject: str
) -> int | None:
    """Returnt test_id eines noch nicht abgeschlossenen Fehler-Übungs-Attempts im Fach,
    oder None."""
    row = conn.execute(
        """
        SELECT t.id AS test_id
        FROM tests t
        JOIN attempts att ON att.test_id = t.id
        WHERE t.user_id = ?
          AND t.subject = ?
          AND t.is_study = 1
          AND t.title LIKE ?
          AND att.completed = 0
        ORDER BY att.started_at DESC
        LIMIT 1
        """,
        (user_id, subject, f"{_FEHLER_TITLE_PREFIX}%"),
    ).fetchone()
    return None if row is None else int(row["test_id"])


def _load_questions(conn: sqlite3.Connection, qids: list[int]) -> list[sqlite3.Row]:
    """Returnt Question-Rows in der Reihenfolge der übergebenen qids."""
    if not qids:
        return []
    placeholders = ",".join(["?"] * len(qids))
    rows = conn.execute(
        f"SELECT * FROM questions WHERE id IN ({placeholders})", qids
    ).fetchall()
    by_id = {r["id"]: r for r in rows}
    return [by_id[qid] for qid in qids if qid in by_id]


def build_practice_test(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str,
    limit: int = 10,
) -> int | None:
    """Baut einen Fehler-Übungs-Test (subject, is_study=1) mit ≤limit kopierten Fragen.
    Returnt test_id, oder None wenn keine offenen Fehler im Fach."""
    existing = _find_open_practice_test(conn, user_id, subject)
    if existing is not None:
        return existing

    entries = queries.list_open_entries(conn, user_id, subject=subject)
    if not entries:
        return None
    entries = entries[:limit]

    qids = [e.question_id for e in entries]
    question_rows = _load_questions(conn, qids)
    if not question_rows:
        return None

    today = date.today()
    title = f"{_FEHLER_TITLE_PREFIX} – {subject} – {today.strftime('%d.%m.%Y')}"
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
            _FEHLER_DESCRIPTION,
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
                f"err:{_root_question_id(q)}",
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
            for pos, q in enumerate(question_rows)
        ],
    )
    conn.commit()
    return test_id

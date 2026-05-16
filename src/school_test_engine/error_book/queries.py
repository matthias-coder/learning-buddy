from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from typing import Iterable

from .models import ErrorBookEntry


def _is_resolved(answers_desc: Iterable) -> bool:
    """True wenn die letzten 2 Antworten (DESC-sortiert) beide korrekt waren."""
    rows = list(answers_desc)
    if len(rows) < 2:
        return False
    return rows[0].is_correct == 1 and rows[1].is_correct == 1


def _consecutive_correct(answers_desc: Iterable) -> int:
    """Zählt korrekte Antworten vom neuesten Eintrag rückwärts bis zum ersten Fehler."""
    n = 0
    for a in answers_desc:
        if a.is_correct == 1:
            n += 1
        else:
            break
    return n


_CANDIDATE_SQL = """
    SELECT DISTINCT a.question_id AS qid
    FROM answers a
    JOIN attempts att ON att.id = a.attempt_id
    JOIN tests t ON t.id = att.test_id
    WHERE a.is_correct = 0
      AND att.completed = 1
      AND t.is_study = 0
      AND t.user_id = ?
"""

_QUESTION_META_SQL = """
    SELECT q.id   AS id,
           t.subject AS subject,
           q.topic AS topic,
           q.prompt AS prompt
    FROM questions q
    JOIN tests t ON t.id = q.test_id
    WHERE q.id = ?
"""

_ANSWERS_DESC_SQL = """
    SELECT a.is_correct AS is_correct, att.finished_at AS finished_at
    FROM answers a
    JOIN attempts att ON att.id = a.attempt_id
    WHERE a.question_id = ? AND att.completed = 1
    UNION ALL
    SELECT a.is_correct AS is_correct, att.finished_at AS finished_at
    FROM answers a
    JOIN attempts att ON att.id = a.attempt_id
    JOIN questions q ON q.id = a.question_id
    WHERE q.ext_id = ? AND att.completed = 1
    ORDER BY finished_at DESC
"""


def _excerpt(prompt: str, limit: int = 80) -> str:
    if prompt is None:
        return ""
    s = " ".join(prompt.split())
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def list_open_entries(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str | None = None,
) -> list[ErrorBookEntry]:
    """Offene Fehlerheft-Positionen, sortiert nach wrong_count DESC, last_wrong_at DESC."""
    qids = [r["qid"] for r in conn.execute(_CANDIDATE_SQL, (user_id,)).fetchall()]

    entries: list[ErrorBookEntry] = []
    for qid in qids:
        meta = conn.execute(_QUESTION_META_SQL, (qid,)).fetchone()
        if meta is None:
            continue
        if subject is not None and meta["subject"] != subject:
            continue

        rows = conn.execute(_ANSWERS_DESC_SQL, (qid, f"err:{qid}")).fetchall()
        # Adapter: T2-helpers expect attribute access (.is_correct), sqlite3.Row is subscript-only.
        answers = [
            SimpleNamespace(is_correct=r["is_correct"], finished_at=r["finished_at"])
            for r in rows
        ]
        if _is_resolved(answers):
            continue

        wrong_count = sum(1 for a in answers if a.is_correct == 0)
        last_wrong_at = next(
            (a.finished_at for a in answers if a.is_correct == 0), ""
        )
        entries.append(ErrorBookEntry(
            question_id=qid,
            subject=meta["subject"],
            topic=meta["topic"] or "",
            prompt_excerpt=_excerpt(meta["prompt"]),
            wrong_count=wrong_count,
            last_wrong_at=last_wrong_at or "",
            consecutive_correct=_consecutive_correct(answers),
        ))

    entries.sort(key=lambda e: (-e.wrong_count, e.last_wrong_at), reverse=False)
    # Tie-break: jüngeres last_wrong_at zuerst → DESC. Aber wir sortieren bereits
    # ASC nach last_wrong_at oben, also umkehren: zweistufiger Sort:
    entries.sort(key=lambda e: e.last_wrong_at, reverse=True)
    entries.sort(key=lambda e: e.wrong_count, reverse=True)
    return entries


def count_open(conn: sqlite3.Connection, user_id: int) -> dict[str, int]:
    """Anzahl offener Einträge pro Fach (Dict mit Fach → int)."""
    out: dict[str, int] = {}
    for entry in list_open_entries(conn, user_id):
        out[entry.subject] = out.get(entry.subject, 0) + 1
    return out

from __future__ import annotations

import re
import sqlite3

from . import queries

_ERR_EXT_RE = re.compile(r"^err:(\d+)$")


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
    ext = q_row["ext_id"] if "ext_id" in q_row.keys() else None  # type: ignore[attr-defined]
    # sqlite3.Row vs dict
    if hasattr(q_row, "keys") and not isinstance(q_row, dict):
        ext = q_row["ext_id"]
    elif isinstance(q_row, dict):
        ext = q_row.get("ext_id")
    if ext:
        m = _ERR_EXT_RE.match(ext)
        if m:
            return int(m.group(1))
    return int(q_row["id"])

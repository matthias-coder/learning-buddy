from __future__ import annotations

import sqlite3

from . import queries


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

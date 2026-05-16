from __future__ import annotations

import sqlite3
from typing import Iterable


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

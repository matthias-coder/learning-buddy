from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorBookEntry:
    """Eine offene Fehlerheft-Position.

    `question_id` ist immer die ROOT-Frage (nie eine err:-Kopie).
    `consecutive_correct` ist 0 oder 1 — bei ≥2 wird der Eintrag in
    `queries.list_open_entries` rausgefiltert und erscheint nicht.
    """

    question_id: int
    subject: str
    topic: str
    prompt_excerpt: str
    wrong_count: int
    last_wrong_at: str
    consecutive_correct: int

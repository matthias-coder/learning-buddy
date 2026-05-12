from __future__ import annotations

# Standard-Notenschlüssel für Realschule (8. Klasse).
# Cutoffs: erforderliche Mindest-Prozent für die jeweilige Note.
#
# TODO MATTHIAS: Stimmen diese Cutoffs mit Clemens' Schule überein?
#   Frag bei Bedarf den Klassenlehrer nach dem offiziellen Schlüssel —
#   manche Schulen nutzen z.B. 96/85/70/55/30/0 oder einen IHK-Schlüssel.
#   Pro Test kann das im JSON ("notenschluessel": {...}) überschrieben werden.
DEFAULT_REALSCHULE: dict[int, int] = {
    1: 92,
    2: 81,
    3: 67,
    4: 50,
    5: 25,
    6: 0,
}


def percent_to_note(percent: float, schluessel: dict[int, int] | None = None) -> int:
    table = schluessel or DEFAULT_REALSCHULE
    for note in (1, 2, 3, 4, 5):
        if percent >= table[note]:
            return note
    return 6

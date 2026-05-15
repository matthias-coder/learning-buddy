"""Fach-bezogene UI-Helpers (Pill-Variante pro Fach).

Die Subject-Liste selbst lebt in `models.test.Subject` (als Literal).
"""
from __future__ import annotations


SUBJECTS_ALL = [
    "Mathe", "Englisch", "Deutsch",
    "Bio", "Physik", "Chemie",
    "Geschichte", "Geographie", "Politik und Wirtschaft",
    "Religion", "Musik",
]

_SUBJECT_VARIANT = {
    "Mathe": "clay",
    "Englisch": "tea",
    "Deutsch": "rose",
    "Bio": "tea",
    "Physik": "sky",
    "Chemie": "honey",
    "Geschichte": "paper",
    "Geographie": "tea",
    "Politik und Wirtschaft": "clay",
    "Religion": "paper",
    "Musik": "honey",
}


def subject_variant(subject: str) -> str:
    return _SUBJECT_VARIANT.get(subject, "paper")


_NOTE_COLOR = {
    1: "#3e552d",  # tea-700
    2: "#658a47",  # tea-500
    3: "#c79d44",  # honey-500
    4: "#c26a3d",  # clay-500
    5: "#a8524f",  # rose-500
    6: "#7e3b39",
}


def note_color(note: int) -> str:
    return _NOTE_COLOR.get(note, "#1e1b15")


def trend_variant(trend: str) -> str:
    return {"up": "tea", "down": "rose", "flat": "paper"}.get(trend, "paper")

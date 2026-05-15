"""Map raw subject strings from the iCal feed to the app's canonical names.

Unknown subjects pass through unchanged — the UI Subject-Combo is editable,
so unmapped names land in the DB as-is and the user can rename later.
"""
from __future__ import annotations

DEFAULT_SUBJECT_MAP: dict[str, str] = {
    "Mathematik": "Mathe",
    "Religion - evangelisch": "Religion",
    "Religion - katholisch": "Religion",
    "Religion - ethisch": "Religion",
    "Ethik": "Religion",
    "Erdkunde": "Geographie",
    "PoWi": "Politik und Wirtschaft",
    "Sozialkunde": "Politik und Wirtschaft",
}


def map_subject(raw: str) -> str:
    cleaned = raw.strip()
    return DEFAULT_SUBJECT_MAP.get(cleaned, cleaned)

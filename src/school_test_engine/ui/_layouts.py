"""Layout- und sqlite3.Row-Helpers."""
from __future__ import annotations

import sqlite3
from typing import Any

from PySide6.QtWidgets import QLayout


def clear_layout(layout: QLayout) -> None:
    """Alle Kinder-Widgets entfernen und für Garbage-Collection markieren."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()


def row_get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    """Wie row[key], aber gibt `default` zurück wenn die Spalte nicht existiert.

    Notwendig weil Migrations nachträglich Spalten hinzufügen — älterer
    Migration-Stand kennt z.B. avatar_image/birthday/prompt_math noch nicht.
    """
    try:
        return row[key]
    except (IndexError, KeyError):
        return default

from __future__ import annotations

from PySide6.QtWidgets import QLabel


def Eyebrow(text: str, parent=None) -> QLabel:
    """Kleine, getrackte Uppercase-Beschriftung über einer Sektion.
    Stil via QSS-objectName 'eyebrow' (siehe style.qss)."""
    lbl = QLabel(text.upper(), parent)
    lbl.setObjectName("eyebrow")
    return lbl

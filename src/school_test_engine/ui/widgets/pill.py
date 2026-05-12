from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

PillVariant = Literal["tea", "clay", "paper", "rose", "honey", "sky"]


_VARIANTS = {
    "tea":   ("#dde8d0", "#3e552d", None),
    "clay":  ("#f6ddc9", "#7e4025", None),
    "paper": ("#f4efe6", "#4a4538", "#d8cdb8"),
    "rose":  ("#f6dcdb", "#7e3b39", None),
    "honey": ("#f6e3bb", "#7e5b16", None),
    "sky":   ("#dbe7ed", "#395869", None),
}


def Pill(text: str, variant: PillVariant = "paper", parent=None) -> QLabel:
    """Kleines abgerundetes Tag-Label im Kessler-Stil."""
    bg, fg, border = _VARIANTS.get(variant, _VARIANTS["paper"])
    lbl = QLabel(text, parent)
    style = (
        f"background: {bg}; color: {fg}; "
        f"font-size: 10pt; font-weight: 500; "
        f"padding: 3px 10px; border-radius: 12px; "
    )
    if border:
        style += f"border: 1px solid {border};"
    lbl.setStyleSheet(style)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl

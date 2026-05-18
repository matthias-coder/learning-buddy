from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..design import Color, FontFamily


class OpenGradesBanner(QFrame):
    """Klickbare Card unter dem FerienBanner — Zähler offener Noten."""

    def __init__(
        self,
        count: int,
        parent=None,
        get_window: Callable | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("openGradesBanner")
        self._count = count
        self._get_window = get_window or (lambda: self.window())
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(12)

        strip = QFrame()
        strip.setObjectName("openGradesBannerStrip")
        strip.setFixedWidth(4)
        h.addWidget(strip)

        emoji = QLabel("📝")
        emoji.setStyleSheet("font-size: 18pt;")
        h.addWidget(emoji)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._label = QLabel(self._compose_label(count))
        self._label.setFont(QFont(FontFamily.BODY, 11, QFont.Weight.Medium))
        text_col.addWidget(self._label)
        sub = QLabel("Tippe für Schulkalender")
        sub.setStyleSheet(f"color: {Color.PAPER_500}; font-size: 9pt;")
        text_col.addWidget(sub)
        h.addLayout(text_col)
        h.addStretch(1)

    @staticmethod
    def _compose_label(n: int) -> str:
        if n == 1:
            return "1 offene Note"
        return f"{n} offene Noten"

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            win = self._get_window()
            if win is not None and hasattr(win, "show_school_calendar"):
                win.show_school_calendar(initial_tab="past")
        super().mousePressEvent(event)

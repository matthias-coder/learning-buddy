from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ...school_calendar.service import FerienBannerState
from ..design import Color, FontFamily


class FerienBanner(QFrame):
    """Klickbare Card unter der Menü-Begrüßung — Countdown / In-Vacation."""

    def __init__(
        self,
        state: FerienBannerState,
        parent=None,
        get_window: Callable | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("ferienBanner")
        self._state = state
        self._get_window = get_window or (lambda: self.window())
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(12)

        # 4px tea-strip on the left
        strip = QFrame()
        strip.setObjectName("ferienBannerStrip")
        strip.setFixedWidth(4)
        h.addWidget(strip)

        emoji = QLabel("🌴" if state.mode == "countdown" else "🌞")
        emoji.setStyleSheet("font-size: 18pt;")
        h.addWidget(emoji)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._label = QLabel(state.label)
        self._label.setFont(QFont(FontFamily.BODY, 11, QFont.Weight.Medium))
        text_col.addWidget(self._label)

        if state.mode == "countdown" and state.target_date:
            sub = QLabel(f"Beginn: {state.target_date.strftime('%d.%m.%Y')}")
            sub.setStyleSheet(f"color: {Color.PAPER_500}; font-size: 9pt;")
            text_col.addWidget(sub)

        h.addLayout(text_col)
        h.addStretch(1)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            win = self._get_window()
            if win is not None and hasattr(win, "show_school_calendar"):
                win.show_school_calendar()
        super().mousePressEvent(event)

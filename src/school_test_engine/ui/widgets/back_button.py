from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from ..design import Color, FontFamily, FontSize


class BackButton(QFrame):
    """Globaler Zurück-Button im GlobalHeader. Emits `clicked` on left-press.

    Visibility is controlled by MainWindow (bound to history-stack depth)."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("backButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 4, 12, 4)
        h.setSpacing(6)

        arrow = QLabel("←")
        arrow.setStyleSheet(
            f"color: {Color.PAPER_700}; font-size: 16pt; font-weight: 400;"
        )
        h.addWidget(arrow)

        text = QLabel("Zurück")
        text.setFont(QFont(FontFamily.BODY, FontSize.SM, QFont.Weight.Medium))
        text.setStyleSheet(f"color: {Color.PAPER_700};")
        h.addWidget(text)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

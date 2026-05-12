from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame

from .shadow import apply_warm_shadow


class ClickableCard(QFrame):
    """Card als QFrame mit Klick-Signal — verlässlicher als QPushButton mit Layout."""

    clicked = Signal()

    def __init__(self, *, object_name: str = "card", with_shadow: bool = True, parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if with_shadow:
            apply_warm_shadow(self, blur=12, dy=2, alpha=0.06)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self.setProperty("hover", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setProperty("hover", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)

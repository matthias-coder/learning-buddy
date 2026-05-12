from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel


class AvatarTile(QFrame):
    """Klickbare Avatar-Auswahl-Kachel mit Highlight bei Selektion."""

    clicked = Signal(str)

    def __init__(self, emoji: str, parent=None):
        super().__init__(parent)
        self._emoji = emoji
        self.setObjectName("avatarTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(56, 56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(emoji)
        f = QFont(); f.setPointSize(22); label.setFont(f)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    def emoji(self) -> str:
        return self._emoji

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._emoji)
        super().mousePressEvent(event)

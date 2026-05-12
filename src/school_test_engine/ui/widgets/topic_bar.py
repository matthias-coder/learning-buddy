from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class TopicBar(QWidget):
    """Horizontaler Fortschrittsbalken: Farbe rot/gelb/grün je nach Prozent."""

    def __init__(self, percent: float, parent=None):
        super().__init__(parent)
        self._percent = max(0.0, min(100.0, percent))
        self.setMinimumHeight(18)

    def sizeHint(self) -> QSize:
        return QSize(200, 18)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect: QRect = self.rect().adjusted(0, 2, -1, -2)
        # Hintergrund
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ebe3d5"))
        p.drawRoundedRect(rect, 4, 4)
        # Füllung
        if self._percent > 0:
            fill_width = int(rect.width() * (self._percent / 100.0))
            fill_rect = QRect(rect.x(), rect.y(), fill_width, rect.height())
            p.setBrush(_color_for_percent(self._percent))
            p.drawRoundedRect(fill_rect, 4, 4)


def _color_for_percent(p: float) -> QColor:
    # Kessler: rose (rot) → honey (gelb) → tea (grün)
    if p < 50:
        return QColor("#a8524f")
    if p < 80:
        return QColor("#c79d44")
    return QColor("#658a47")

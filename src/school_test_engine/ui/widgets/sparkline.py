from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class Sparkline(QWidget):
    """Mini-Liniendiagramm — z.B. Notenverlauf über mehrere Versuche."""

    def __init__(
        self,
        values: list[float],
        *,
        y_min: float | None = None,
        y_max: float | None = None,
        invert_y: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._values = list(values)
        self._y_min = y_min if y_min is not None else (min(values) if values else 0.0)
        self._y_max = y_max if y_max is not None else (max(values) if values else 1.0)
        self._invert = invert_y
        self.setMinimumHeight(40)

    def sizeHint(self) -> QSize:
        return QSize(200, 40)

    def paintEvent(self, _event) -> None:
        if not self._values:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)
        y_min, y_max = self._y_min, self._y_max
        span = y_max - y_min or 1.0
        n = len(self._values)
        if n == 1:
            xs = [rect.center().x()]
        else:
            xs = [rect.left() + i * rect.width() / (n - 1) for i in range(n)]

        def y_for(v):
            t = (v - y_min) / span
            if self._invert:
                t = 1.0 - t
            return rect.bottom() - t * rect.height()

        # Baseline (paper-200)
        p.setPen(QPen(QColor("#ebe3d5"), 1))
        p.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        # Linie (clay-500)
        path = QPainterPath()
        path.moveTo(xs[0], y_for(self._values[0]))
        for x, v in zip(xs[1:], self._values[1:]):
            path.lineTo(x, y_for(v))
        p.setPen(QPen(QColor("#c26a3d"), 2))
        p.drawPath(path)

        # Punkte (clay-600)
        p.setBrush(QColor("#a25431"))
        p.setPen(Qt.PenStyle.NoPen)
        for x, v in zip(xs, self._values):
            p.drawEllipse(int(x) - 3, int(y_for(v)) - 3, 6, 6)

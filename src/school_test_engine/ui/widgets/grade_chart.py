"""Phase 14 Track C: Notenverlauf-Liniendiagramm pro Fach."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


CLAY = "#c26a3d"
TEA = "#658a47"
PAPER_300 = "#d8cdb8"
PAPER_500 = "#8a8068"
PAPER_600 = "#6f6757"


class GradeChart(QWidget):
    """Line-chart for grade history. X = date, Y = grade (1 top, 6 bottom).

    Two series: schriftlich (clay) and muendlich (tea). Dotted line when
    fewer than 2 points in a series. Placeholder when both empty/too few.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self._schriftlich: list[tuple[date, float]] = []
        self._muendlich: list[tuple[date, float]] = []

    def sizeHint(self) -> QSize:
        return QSize(500, 220)

    def set_data(
        self,
        schriftlich: list[tuple[date, float]],
        muendlich: list[tuple[date, float]],
    ) -> None:
        self._schriftlich = sorted(schriftlich, key=lambda t: t[0])
        self._muendlich = sorted(muendlich, key=lambda t: t[0])
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        all_pts = self._schriftlich + self._muendlich
        if len(all_pts) < 2:
            self._paint_placeholder(p)
            return

        margin_left = 36
        margin_right = 16
        margin_top = 24
        margin_bottom = 32
        rect = self.rect().adjusted(margin_left, margin_top, -margin_right, -margin_bottom)

        min_date = min(d for d, _ in all_pts)
        max_date = max(d for d, _ in all_pts)
        if (max_date - min_date).days < 30:
            max_date = min_date + timedelta(days=30)
        date_span = max(1, (max_date - min_date).days)

        def x_for(d: date) -> float:
            t = (d - min_date).days / date_span
            return rect.left() + t * rect.width()

        def y_for(grade: float) -> float:
            t = (grade - 1.0) / 5.0
            return rect.top() + t * rect.height()

        # Y-axis grid + labels
        p.setFont(QFont("Inter", 8))
        for g in range(1, 7):
            y = y_for(float(g))
            p.setPen(QPen(QColor(PAPER_300), 1))
            p.drawLine(rect.left(), int(y), rect.right(), int(y))
            p.setPen(QPen(QColor(PAPER_600), 1))
            p.drawText(rect.left() - 26, int(y) + 4, f"{g}")

        # X-axis end labels
        p.setPen(QPen(QColor(PAPER_600), 1))
        p.drawText(rect.left(), rect.bottom() + 16, min_date.strftime("%b %Y"))
        p.drawText(rect.right() - 60, rect.bottom() + 16, max_date.strftime("%b %Y"))

        # Plot series
        self._plot_series(p, self._schriftlich, QColor(CLAY), x_for, y_for)
        self._plot_series(p, self._muendlich, QColor(TEA), x_for, y_for)

        # Legend
        p.setFont(QFont("Inter", 9))
        legend_y = margin_top - 4
        p.setBrush(QColor(CLAY))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(rect.right() - 140, legend_y, 8, 8)
        p.setPen(QPen(QColor(PAPER_600), 1))
        p.drawText(rect.right() - 128, legend_y + 8, "schriftlich")
        p.setBrush(QColor(TEA))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(rect.right() - 70, legend_y, 8, 8)
        p.setPen(QPen(QColor(PAPER_600), 1))
        p.drawText(rect.right() - 58, legend_y + 8, "mündlich")

    def _plot_series(self, p, series, color, x_for, y_for) -> None:
        if not series:
            return
        pen = QPen(color, 2)
        pen.setStyle(Qt.PenStyle.DotLine if len(series) < 2 else Qt.PenStyle.SolidLine)
        p.setPen(pen)
        if len(series) >= 2:
            path = QPainterPath()
            path.moveTo(x_for(series[0][0]), y_for(series[0][1]))
            for d, g in series[1:]:
                path.lineTo(x_for(d), y_for(g))
            p.drawPath(path)
        # Points
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        for d, g in series:
            p.drawEllipse(int(x_for(d)) - 4, int(y_for(g)) - 4, 8, 8)

    def _paint_placeholder(self, p: QPainter) -> None:
        p.setPen(QPen(QColor(PAPER_500), 1))
        p.setFont(QFont("Inter", 11))
        p.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "Mehr Noten = aussagekräftiger Verlauf",
        )

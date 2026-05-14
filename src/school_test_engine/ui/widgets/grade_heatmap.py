"""Phase 14 Track C: Fach × Wochen Heatmap."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


PAPER_100 = "#f4efe6"
PAPER_300 = "#d8cdb8"
PAPER_500 = "#8a8068"
PAPER_600 = "#6f6757"
FG = "#1e1b15"


def _cell_color(grade: float) -> QColor:
    """Returns a pastel color for a grade."""
    if grade <= 2.0:
        return QColor("#bcd2a4")
    if grade <= 3.0:
        return QColor("#dde8d0")
    if grade <= 4.0:
        return QColor("#f6e3bb")
    return QColor("#f6c8c2")


class GradeHeatmap(QWidget):
    """N weeks × subjects heatmap."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self._weeks: list[date] = []
        self._rows: list[tuple[str, dict[date, float]]] = []

    def sizeHint(self) -> QSize:
        return QSize(560, 280)

    def set_data(
        self,
        weeks: list[date],
        rows: list[tuple[str, dict[date, float]]],
    ) -> None:
        self._weeks = list(weeks)
        self._rows = list(rows)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self._rows or not self._weeks:
            p.setPen(QPen(QColor(PAPER_500), 1))
            p.setFont(QFont("Inter", 11))
            p.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "Noch keine Noten in den letzten 8 Wochen",
            )
            return

        label_width = 90
        legend_height = 28
        header_height = 22
        body_top = header_height
        body_bottom = self.height() - legend_height
        cells_left = label_width
        cells_width = self.width() - cells_left - 8
        cell_w = max(20, cells_width // max(1, len(self._weeks)))
        row_h = max(28, (body_bottom - body_top - 4) // max(1, len(self._rows)))

        # Header row (week labels)
        p.setFont(QFont("Inter", 9))
        p.setPen(QPen(QColor(PAPER_600), 1))
        for i, monday in enumerate(self._weeks):
            week_num = monday.isocalendar().week
            x = cells_left + i * cell_w
            p.drawText(
                QRect(x, 0, cell_w, header_height),
                Qt.AlignmentFlag.AlignCenter,
                f"KW {week_num:02d}",
            )

        # Subject rows + cells
        p.setFont(QFont("Inter", 10))
        for row_i, (subject, week_grades) in enumerate(self._rows):
            y = body_top + row_i * row_h
            # Label
            p.setPen(QPen(QColor(FG), 1))
            p.drawText(
                QRect(0, y, label_width - 8, row_h),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                subject,
            )
            # Cells
            for i, monday in enumerate(self._weeks):
                x = cells_left + i * cell_w
                inner = QRect(x + 2, y + 2, cell_w - 4, row_h - 4)
                if monday in week_grades:
                    color = _cell_color(week_grades[monday])
                    p.setBrush(color)
                else:
                    p.setBrush(QColor(PAPER_100))
                p.setPen(QPen(QColor(PAPER_300), 1))
                p.drawRoundedRect(inner, 4, 4)

        # Legend
        legend_y = self.height() - legend_height + 4
        p.setFont(QFont("Inter", 9))
        items = [
            ("≤2,0", _cell_color(2.0)),
            ("≤3,0", _cell_color(3.0)),
            ("≤4,0", _cell_color(4.0)),
            (">4,0", _cell_color(5.0)),
            ("keine", QColor(PAPER_100)),
        ]
        legend_x = cells_left
        for label, color in items:
            p.setBrush(color)
            p.setPen(QPen(QColor(PAPER_300), 1))
            p.drawRoundedRect(legend_x, legend_y, 14, 14, 3, 3)
            p.setPen(QPen(QColor(PAPER_600), 1))
            p.drawText(legend_x + 18, legend_y + 12, label)
            legend_x += 60

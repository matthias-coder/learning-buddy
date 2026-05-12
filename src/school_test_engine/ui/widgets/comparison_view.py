from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..design import Color, FontFamily, Semantic
from .grade_pill import GradePill


class ComparisonView(QFrame):
    """Shows app-practice average vs. real grade for one assessment."""

    def __init__(self, comparison_data, parent=None):
        super().__init__(parent)
        self.setObjectName("comparisonCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 16)
        outer.setSpacing(10)

        eyebrow = QLabel("VERGLEICH")
        eyebrow.setObjectName("eyebrow")
        outer.addWidget(eyebrow)

        row = QHBoxLayout()
        row.setSpacing(20)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        app_col = QVBoxLayout()
        app_col.setSpacing(4)
        app_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_col.addWidget(GradePill(comparison_data.attempts_grade_avg, size=56), alignment=Qt.AlignmentFlag.AlignCenter)
        app_label = QLabel(f"App-Übungen\n({comparison_data.attempts_count})")
        app_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_label.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 9pt;")
        app_col.addWidget(app_label)
        row.addLayout(app_col)

        arrow = QLabel("→")
        arrow.setStyleSheet(f"color: {Semantic.ACCENT}; font-size: 22pt;")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(arrow)

        real_col = QVBoxLayout()
        real_col.setSpacing(4)
        real_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        real_col.addWidget(GradePill(comparison_data.real_grade, size=72), alignment=Qt.AlignmentFlag.AlignCenter)
        real_label = QLabel("echte Note")
        real_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        real_label.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 9pt;")
        real_col.addWidget(real_label)
        row.addLayout(real_col)
        row.addStretch(1)

        outer.addLayout(row)

        delta_lbl = QLabel(comparison_data.delta_label)
        delta_lbl.setFont(QFont(FontFamily.DISPLAY, 12, QFont.Weight.Normal))
        delta_lbl.setStyleSheet(f"color: {Semantic.FG};")
        delta_lbl.setWordWrap(True)
        outer.addWidget(delta_lbl)

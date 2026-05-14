from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..design import Color, FontFamily, Semantic
from .clickable_card import ClickableCard


DailyState = Literal["no_library", "due", "done"]


def _streak_text(streak: int) -> str:
    if streak <= 0:
        return ""
    if streak == 1:
        return "🔥 1. Tag"
    return f"🔥 {streak} Tage in Folge"


class DailyCard(ClickableCard):
    """Daily-5 status card on the Hauptmenü. Four visual states (no_library,
    due-no-streak, due-with-streak, done)."""

    practice_clicked = Signal()

    def __init__(
        self,
        state: DailyState,
        streak: int,
        last_grade: int | None = None,
        parent=None,
    ):
        super().__init__(object_name="dailyCard", parent=parent)
        self.setMinimumHeight(96)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 14, 20, 14)
        outer.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(4)

        eyebrow_text = "DAILY-5 · heute"
        if state == "no_library":
            eyebrow_text = "DAILY-5"
        elif state == "done":
            eyebrow_text = "✓ DAILY-5 · heute geschafft"
        eyebrow = QLabel(eyebrow_text)
        eyebrow.setObjectName("eyebrow")
        left.addWidget(eyebrow)

        if state == "no_library":
            title = QLabel("Importiere zuerst Tests in deine Library —\nDaily-5 startet danach.")
            title.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 11pt;")
            title.setWordWrap(True)
            left.addWidget(title)
        elif state == "due":
            title = QLabel("5 Fragen, ~5 Min")
            title.setFont(QFont(FontFamily.DISPLAY, 16, QFont.Weight.Medium))
            title.setStyleSheet(f"color: {Semantic.FG};")
            left.addWidget(title)
            streak_str = _streak_text(streak)
            if streak_str:
                sub = QLabel(streak_str)
                sub.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
                left.addWidget(sub)
        elif state == "done":
            sub_parts: list[str] = []
            streak_str = _streak_text(streak)
            if streak_str:
                sub_parts.append(streak_str)
            if last_grade is not None:
                sub_parts.append(f"Note: {last_grade}")
            sub_parts.append("komm morgen wieder")
            sub = QLabel(" · ".join(sub_parts))
            sub.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
            sub.setWordWrap(True)
            left.addWidget(sub)

        outer.addLayout(left, 1)

        if state == "due":
            btn = QPushButton("Starten →")
            btn.setObjectName("primary")
            btn.clicked.connect(lambda: self.practice_clicked.emit())
            outer.addWidget(btn)
        elif state == "done":
            # Greyed-out check pill
            pill = QLabel("✓")
            pill.setStyleSheet(
                "background: #dde8d0; color: #3e552d; "
                "font-size: 16pt; padding: 4px 14px; border-radius: 14px;"
            )
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer.addWidget(pill)
        # state == "no_library": no action button

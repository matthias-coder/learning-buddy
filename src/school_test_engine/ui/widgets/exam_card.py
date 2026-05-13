from __future__ import annotations

from typing import Callable

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
from .pill import Pill
from .._subjects import subject_variant


def _countdown_text(days_until: int) -> str:
    if days_until < 0:
        return f"vor {abs(days_until)} Tagen"
    if days_until == 0:
        return "heute"
    if days_until == 1:
        return "morgen"
    return f"in {days_until} Tagen"


def _countdown_variant(days_until: int) -> str:
    # rose for "urgent" (<= 3 days), honey for soon (<= 7), paper otherwise; past = paper dimmed
    if days_until < 0:
        return "paper"
    if days_until <= 3:
        return "rose"
    if days_until <= 7:
        return "honey"
    return "tea"


class ExamCard(ClickableCard):
    """Hero KA card. Click opens detail dialog (handled by parent via clicked signal)."""

    practice_clicked = Signal(int)   # emits event_id (Phase 8 will hook up)
    enter_grade_clicked = Signal(int)
    edit_clicked = Signal(int)

    def __init__(self, event_data, parent=None):
        super().__init__(object_name="examCard", parent=parent)
        self.event_id = event_data.event_id
        self.setMinimumSize(260, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)

        # Top row: subject pill + countdown pill
        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(Pill(event_data.subject.upper(), subject_variant(event_data.subject)))
        top.addWidget(Pill(_countdown_text(event_data.days_until), _countdown_variant(event_data.days_until)))
        top.addStretch(1)
        layout.addLayout(top)

        # Title: kind label
        kind_label = {
            "klassenarbeit": "Klassenarbeit",
            "klausur": "Klausur",
            "test": "Test",
            "sonstiges": "Termin",
        }.get(event_data.kind, "Termin")
        title = QLabel(kind_label)
        title.setObjectName("h2")
        title.setFont(QFont(FontFamily.DISPLAY, 16, QFont.Weight.Medium))
        title.setStyleSheet(f"color: {Semantic.FG};")
        layout.addWidget(title)

        # Topics (up to 3 lines)
        topics_text = "\n".join(f"· {t}" for t in event_data.topics[:3]) if event_data.topics else "Keine Themen erfasst"
        topics = QLabel(topics_text)
        topics.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
        topics.setWordWrap(True)
        layout.addWidget(topics)

        layout.addStretch(1)

        # Bottom row: actions
        actions = QHBoxLayout()
        actions.setSpacing(8)
        if event_data.linked_assessment_id is None:
            practice_btn = QPushButton("✨ Test bauen")
            practice_btn.setObjectName("primary")
            practice_btn.clicked.connect(lambda: self.practice_clicked.emit(self.event_id))
            actions.addWidget(practice_btn)

            grade_btn = QPushButton("Note eintragen")
            grade_btn.setObjectName("text")
            grade_btn.clicked.connect(lambda: self.enter_grade_clicked.emit(self.event_id))
            actions.addWidget(grade_btn)
        else:
            done = Pill("Note erfasst ✓", "tea")
            actions.addWidget(done)
        actions.addStretch(1)
        edit = QPushButton("…")
        edit.setObjectName("text")
        edit.setFixedWidth(36)
        edit.clicked.connect(lambda: self.edit_clicked.emit(self.event_id))
        actions.addWidget(edit)
        layout.addLayout(actions)

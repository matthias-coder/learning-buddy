from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from ..design import Color
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
    study_plan_clicked = Signal(int)   # Phase 14: triggers PDF Lernplan-Export

    def __init__(self, event_data, parent=None):
        super().__init__(object_name="examCard", parent=parent)
        self.event_id = event_data.event_id
        self.setMinimumWidth(240)
        # Explizite Mindesthöhe: topics-QLabel hat setWordWrap(True), wodurch
        # die sizeHint höhenabhängig von der Breite wird. Ohne expliziten
        # Floor squeezt Qt die Card unter Engpässen (anders als z.B. tiles
        # mit setMinimumSize(180, 88) oder Banner mit fester Layout-Höhe).
        self.setMinimumHeight(130)
        # Vertikal Fixed: bei Window-Resize sollen die Karten ihre sizeHint
        # behalten — der addStretch in MenuPage absorbiert die Höhenänderung.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 14, 14)
        layout.setSpacing(8)

        # Top row: subject pill + countdown pill + overflow menu (always slim)
        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(Pill(event_data.subject.upper(), subject_variant(event_data.subject)))
        top.addWidget(Pill(_countdown_text(event_data.days_until), _countdown_variant(event_data.days_until)))
        top.addStretch(1)
        top.addWidget(self._build_overflow_menu(event_data))
        layout.addLayout(top)

        # Title: kind label
        kind_label = {
            "klassenarbeit": "Klassenarbeit",
            "klausur": "Klausur",
            "test": "Test",
            "sonstiges": "Termin",
        }.get(event_data.kind, "Termin")
        title = QLabel(kind_label)
        title.setObjectName("examCardTitle")
        layout.addWidget(title)

        # Topics (up to 3 lines)
        topics_text = "\n".join(f"· {t}" for t in event_data.topics[:3]) if event_data.topics else "Keine Themen erfasst"
        topics = QLabel(topics_text)
        topics.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
        topics.setWordWrap(True)
        layout.addWidget(topics)

        # Linked badge — small status line below topics, only when graded.
        if event_data.linked_assessment_id is not None:
            badge_row = QHBoxLayout()
            badge_row.addWidget(Pill("Note erfasst ✓", "tea"))
            badge_row.addStretch(1)
            layout.addLayout(badge_row)

    def _build_overflow_menu(self, event_data) -> QPushButton:
        btn = QPushButton("…")
        btn.setObjectName("cardOverflow")
        btn.setFixedSize(32, 32)
        btn.setToolTip("Aktionen")
        menu = QMenu(btn)
        if event_data.linked_assessment_id is None:
            menu.addAction("Test erstellen").triggered.connect(
                lambda: self.practice_clicked.emit(self.event_id)
            )
            menu.addAction("Note eintragen").triggered.connect(
                lambda: self.enter_grade_clicked.emit(self.event_id)
            )
        menu.addAction("Lernplan erstellen").triggered.connect(
            lambda: self.study_plan_clicked.emit(self.event_id)
        )
        menu.addSeparator()
        menu.addAction("Termin bearbeiten").triggered.connect(
            lambda: self.edit_clicked.emit(self.event_id)
        )
        btn.setMenu(menu)
        return btn

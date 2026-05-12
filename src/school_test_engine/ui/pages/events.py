from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...storage import events_repo, assessments_repo
from ..design import Color, FontFamily, Semantic
from ..dialogs.event_dialog import EventDialog
from ..dialogs.assessment_dialog import AssessmentDialog
from ..widgets.clickable_card import ClickableCard
from ..widgets.pill import Pill
from .._subjects import subject_variant


def _kind_label(kind: str) -> str:
    return {
        "klassenarbeit": "Klassenarbeit",
        "klausur": "Klausur",
        "test": "Test",
        "sonstiges": "Sonstiges",
    }.get(kind, "Termin")


def _format_date(iso: str) -> str:
    d = datetime.fromisoformat(iso).date()
    return d.strftime("%a, %d.%m.%Y")


class EventsPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(16)

        # Header row: back + eyebrow/title + add
        head = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(self.window.show_menu)
        head.addWidget(back)
        head.addStretch(1)
        add = QPushButton("+ Termin")
        add.setObjectName("primary")
        add.clicked.connect(self._add_event)
        head.addWidget(add)
        outer.addLayout(head)

        eyebrow = QLabel("TERMINE")
        eyebrow.setObjectName("eyebrow")
        outer.addWidget(eyebrow)

        title = QLabel("Was kommt")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        # Scrollable list
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(10)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._list_container)
        outer.addWidget(self._scroll, 1)

    def reload(self) -> None:
        uid = self.window.active_user_id
        if uid is None:
            return
        # Clear list
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        events = events_repo.list_all(self.conn, uid)
        if not events:
            empty = QLabel("Noch keine Termine eingetragen.\nKlick auf „+ Termin“ um den ersten anzulegen.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 11pt; padding: 40px;")
            empty.setWordWrap(True)
            self._list_layout.addWidget(empty)
            return

        today_iso = date.today().isoformat()
        for ev in events:
            card = self._make_event_row(ev, is_past=ev["event_date"] < today_iso)
            self._list_layout.addWidget(card)

    def _make_event_row(self, ev, is_past: bool) -> ClickableCard:
        card = ClickableCard(object_name="eventListCard")
        card.clicked.connect(lambda eid=ev["id"]: self._edit_event(eid))
        if is_past:
            card.setProperty("dimmed", True)
        card.setMinimumHeight(80)

        h = QHBoxLayout(card)
        h.setContentsMargins(18, 12, 18, 12)
        h.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(2)
        date_lbl = QLabel(_format_date(ev["event_date"]))
        date_lbl.setStyleSheet(
            f"color: {Color.PAPER_600 if is_past else Semantic.FG}; font-size: 10pt;"
        )
        left.addWidget(date_lbl)

        kind_lbl = QLabel(_kind_label(ev["kind"]))
        kind_lbl.setFont(QFont(FontFamily.DISPLAY, 16, QFont.Weight.Medium))
        kind_lbl.setStyleSheet(
            f"color: {Color.PAPER_500 if is_past else Semantic.FG};"
        )
        left.addWidget(kind_lbl)

        topics = json.loads(ev["topics"] or "[]")
        if topics:
            topics_lbl = QLabel(" · ".join(topics))
            topics_lbl.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
            topics_lbl.setWordWrap(True)
            left.addWidget(topics_lbl)

        h.addLayout(left, 1)

        # Subject pill
        h.addWidget(Pill(ev["subject"].upper(), subject_variant(ev["subject"])))

        # Assessment status
        assess = assessments_repo.find_by_event(self.conn, ev["id"])
        if assess is not None:
            h.addWidget(Pill(f"Note {str(assess['grade']).replace('.', ',')}", "tea"))
        elif is_past:
            h.addWidget(Pill("Note fehlt", "honey"))

        return card

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_event(self):
        dlg = EventDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.data()
            events_repo.create(
                self.conn, self.window.active_user_id,
                data["subject"], data["kind"], data["event_date"],
                topics=data["topics"], note=data["note"],
            )
            self.reload()

    def _edit_event(self, event_id: int):
        ev = events_repo.get(self.conn, event_id)
        if ev is None:
            return
        dlg = EventDialog(self, initial=ev)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.is_delete():
            events_repo.delete(self.conn, event_id)
        else:
            data = dlg.data()
            events_repo.update(
                self.conn, event_id,
                subject=data["subject"], kind=data["kind"], event_date=data["event_date"],
                topics=data["topics"], note=data["note"],
            )
        self.reload()

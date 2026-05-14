from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...storage import events_repo
from .._subjects import SUBJECTS_ALL
from ..design import FontFamily


KIND_LABELS = [
    ("klassenarbeit", "Klassenarbeit"),
    ("klausur", "Klausur"),
    ("test", "Test"),
    ("sonstiges", "Sonstiges"),
]


class EventEditPage(QWidget):
    """Inline page for adding or editing a scheduled_event. Replaces the
    old EventDialog from Phases 7+."""

    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._event_id: int | None = None
        self._return_to: str = "events"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(48, 36, 48, 36)
        layout.setSpacing(14)

        # Header
        head = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(self._cancel)
        head.addWidget(back)
        head.addStretch(1)
        self.save_btn = QPushButton("Speichern")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        head.addWidget(self.save_btn)
        layout.addLayout(head)

        eyebrow = QLabel("TERMIN")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)

        self.title_label = QLabel("Klassenarbeit")
        self.title_label.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        layout.addWidget(self.title_label)

        form = QFormLayout()
        form.setSpacing(10)

        self.subject = QComboBox()
        self.subject.addItems(SUBJECTS_ALL)
        self.subject.setEditable(True)
        form.addRow("Fach:", self.subject)

        kind_row = QHBoxLayout()
        self.kind_group = QButtonGroup(self)
        self._kind_buttons: dict[str, QRadioButton] = {}
        for value, label in KIND_LABELS:
            rb = QRadioButton(label)
            self._kind_buttons[value] = rb
            self.kind_group.addButton(rb)
            kind_row.addWidget(rb)
        self._kind_buttons["klassenarbeit"].setChecked(True)
        form.addRow("Typ:", kind_row)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        form.addRow("Datum:", self.date_edit)

        self.topics_edit = QPlainTextEdit()
        self.topics_edit.setPlaceholderText("Eine Zeile = ein Thema")
        self.topics_edit.setMaximumHeight(140)
        form.addRow("Themen:", self.topics_edit)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText('optional, z. B. „Formelsammlung erlaubt“')
        form.addRow("Notiz:", self.note_edit)

        layout.addLayout(form)

        # Footer: delete (only in edit mode)
        footer = QHBoxLayout()
        self.delete_btn = QPushButton("Löschen")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete)
        self.delete_btn.setVisible(False)
        footer.addWidget(self.delete_btn)
        footer.addStretch(1)
        layout.addLayout(footer)

        layout.addStretch(1)

    def show_for(self, event_id: int | None = None, return_to: str = "events") -> None:
        self._event_id = event_id
        self._return_to = return_to
        self._reset_fields()
        if event_id is None:
            self.title_label.setText("Klassenarbeit")
            self.delete_btn.setVisible(False)
        else:
            self.title_label.setText("Termin bearbeiten")
            self.delete_btn.setVisible(True)
            self._load_event(event_id)

    def _reset_fields(self) -> None:
        self.subject.setCurrentIndex(0)
        self._kind_buttons["klassenarbeit"].setChecked(True)
        default_date = date.today() + timedelta(days=7)
        self.date_edit.setDate(QDate(default_date.year, default_date.month, default_date.day))
        self.topics_edit.setPlainText("")
        self.note_edit.setText("")

    def _load_event(self, event_id: int) -> None:
        row = events_repo.get(self.conn, event_id)
        if row is None:
            return
        idx = self.subject.findText(row["subject"])
        if idx >= 0:
            self.subject.setCurrentIndex(idx)
        else:
            self.subject.setEditText(row["subject"])
        if row["kind"] in self._kind_buttons:
            self._kind_buttons[row["kind"]].setChecked(True)
        d = row["event_date"]
        self.date_edit.setDate(QDate(int(d[:4]), int(d[5:7]), int(d[8:10])))
        topics = json.loads(row["topics"] or "[]")
        self.topics_edit.setPlainText("\n".join(topics))
        if row["note"]:
            self.note_edit.setText(row["note"])

    def _collect_data(self) -> dict:
        kind = next(v for v, rb in self._kind_buttons.items() if rb.isChecked())
        topics_text = self.topics_edit.toPlainText()
        topics = [t.strip() for t in topics_text.splitlines() if t.strip()]
        return {
            "subject": self.subject.currentText().strip(),
            "kind": kind,
            "event_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "topics": topics,
            "note": self.note_edit.text().strip() or None,
        }

    def _save(self) -> None:
        data = self._collect_data()
        if not data["subject"]:
            QMessageBox.information(self, "Fach fehlt", "Bitte ein Fach wählen.")
            return
        if self._event_id is None:
            events_repo.create(
                self.conn, self.window.active_user_id,
                data["subject"], data["kind"], data["event_date"],
                topics=data["topics"], note=data["note"],
            )
        else:
            events_repo.update(
                self.conn, self._event_id,
                subject=data["subject"], kind=data["kind"], event_date=data["event_date"],
                topics=data["topics"], note=data["note"],
            )
        self._navigate_back()

    def _delete(self) -> None:
        if self._event_id is None:
            return
        reply = QMessageBox.question(
            self, "Termin löschen?",
            "Termin endgültig löschen?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        events_repo.delete(self.conn, self._event_id)
        self._navigate_back()

    def _cancel(self) -> None:
        self._navigate_back()

    def _navigate_back(self) -> None:
        if self._return_to == "menu":
            self.window.show_menu()
        else:
            self.window.show_events()

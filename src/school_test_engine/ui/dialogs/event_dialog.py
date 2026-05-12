from __future__ import annotations

import json
from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from .._subjects import SUBJECTS_ALL


KIND_LABELS = [
    ("klassenarbeit", "Klassenarbeit"),
    ("klausur", "Klausur"),
    ("test", "Test"),
    ("sonstiges", "Sonstiges"),
]


class EventDialog(QDialog):
    """Add or edit a scheduled_event. Returns dict via .data() when accepted.

    Usage:
        dlg = EventDialog(parent, initial=row_or_None)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.data()
            # payload = {"subject":..., "kind":..., "event_date":..., "topics":[...], "note":...}
    """

    def __init__(self, parent=None, initial=None):
        super().__init__(parent)
        self.setWindowTitle("Klassenarbeit" if initial is None else "Termin bearbeiten")
        self.setMinimumWidth(420)
        self._deleted = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        # Subject
        self.subject = QComboBox()
        self.subject.addItems(SUBJECTS_ALL)
        self.subject.setEditable(True)  # "Anderes…"-Effekt: user can type custom value
        form.addRow("Fach:", self.subject)

        # Kind (radio buttons)
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

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        default_date = date.today() + timedelta(days=7)
        self.date_edit.setDate(QDate(default_date.year, default_date.month, default_date.day))
        form.addRow("Datum:", self.date_edit)

        # Topics
        self.topics_edit = QPlainTextEdit()
        self.topics_edit.setPlaceholderText("Eine Zeile = ein Thema")
        self.topics_edit.setMaximumHeight(110)
        form.addRow("Themen:", self.topics_edit)

        # Note
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("optional, z. B. „Formelsammlung erlaubt“")
        form.addRow("Notiz:", self.note_edit)

        layout.addLayout(form)

        # Bottom row: optional Delete + Save/Cancel
        bottom = QHBoxLayout()
        if initial is not None:
            del_btn = QPushButton("Löschen")
            del_btn.setObjectName("danger")
            del_btn.clicked.connect(self._on_delete)
            bottom.addWidget(del_btn)
        bottom.addStretch(1)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        bottom.addWidget(btns)
        layout.addLayout(bottom)

        if initial is not None:
            self._populate(initial)

    def _populate(self, row):
        idx = self.subject.findText(row["subject"])
        if idx >= 0:
            self.subject.setCurrentIndex(idx)
        else:
            self.subject.setEditText(row["subject"])
        if row["kind"] in self._kind_buttons:
            self._kind_buttons[row["kind"]].setChecked(True)
        d = row["event_date"]
        # ISO string YYYY-MM-DD
        y, m, da = int(d[:4]), int(d[5:7]), int(d[8:10])
        self.date_edit.setDate(QDate(y, m, da))
        topics = json.loads(row["topics"] or "[]")
        self.topics_edit.setPlainText("\n".join(topics))
        if row["note"]:
            self.note_edit.setText(row["note"])

    def _on_delete(self):
        self._deleted = True
        self.accept()

    def is_delete(self) -> bool:
        return self._deleted

    def data(self) -> dict:
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

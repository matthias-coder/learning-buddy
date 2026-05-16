from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...storage import assessments_repo, events_repo
from .._subjects import SUBJECTS_ALL, note_color
from ..design import FontFamily, Spacing


CATEGORY_LABELS = [
    ("schriftlich", "schriftlich"),
    ("muendlich", "muendlich"),
    ("sonstige", "sonstige"),
]


class _GradeSelector(QFrame):
    """Big-button grid 1..6 with a half-step toggle. Replaces the former
    AssessmentDialog._GradeSelector."""

    changed = Signal(float)

    def __init__(self, initial: float = 2.0, parent=None):
        super().__init__(parent)
        self._value = float(initial)
        h = QGridLayout(self)
        h.setSpacing(8)
        h.setContentsMargins(0, 0, 0, 0)

        self._buttons: dict[int, QPushButton] = {}
        for idx, n in enumerate(range(1, 7)):
            b = QPushButton(str(n))
            b.setCheckable(True)
            b.setFixedSize(56, 56)
            color = note_color(n)
            b.setStyleSheet(
                f"QPushButton {{ background: #f4efe6; color: {color}; "
                f"font-family: 'Fraunces'; font-size: 22pt; border: 2px solid transparent; border-radius: 10px; }}"
                f"QPushButton:checked {{ background: {color}; color: #f6f1e6; }}"
            )
            b.clicked.connect(lambda _, val=n: self._set_int(val))
            self._buttons[n] = b
            row, col = divmod(idx, 3)
            h.addWidget(b, row, col)

        self._half = QPushButton(",5")
        self._half.setCheckable(True)
        self._half.setFixedHeight(36)
        self._half.setStyleSheet(
            "QPushButton { background: #f4efe6; color: #4a4538; "
            "font-family: 'Fraunces'; font-size: 14pt; border: 2px solid transparent; border-radius: 10px; }"
            "QPushButton:checked { background: #c79d44; color: #f6f1e6; }"
        )
        self._half.clicked.connect(self._toggle_half)
        # Span all three columns so the half-step toggle is visually centred
        # under the six grade buttons instead of floating alone on the right.
        h.addWidget(self._half, 2, 0, 1, 3)

        h.setColumnStretch(0, 1)
        h.setColumnStretch(1, 1)
        h.setColumnStretch(2, 1)

        self._apply(self._value)

    def _set_int(self, val: int):
        self._value = float(val)
        self._apply(self._value)
        self.changed.emit(self._value)

    def _toggle_half(self):
        base = int(self._value)
        if abs(self._value - base) < 0.01:
            self._value = base + 0.5
        else:
            self._value = float(base)
        self._apply(self._value)
        self.changed.emit(self._value)

    def _apply(self, val: float):
        base = int(val)
        for n, b in self._buttons.items():
            b.setChecked(n == base)
        self._half.setChecked(abs(val - base) >= 0.4)

    def value(self) -> float:
        return self._value

    def set_value(self, val: float):
        self._value = val
        self._apply(val)


class AssessmentEditPage(QWidget):
    """Inline page for adding or editing an assessment. Replaces the old
    AssessmentDialog from Phase 7+."""

    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._assessment_id: int | None = None
        self._return_to: str = "grades"
        self._prefill_event_id: int | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll, 1)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(48, 36, 48, 36)
        layout.setSpacing(14)

        # Cancel/Save live in the sticky footer; the global header provides
        # the universal "leave" route.
        eyebrow = QLabel("NOTE")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)

        self.title_label = QLabel("Note eintragen")
        self.title_label.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        layout.addWidget(self.title_label)

        # Grade selector
        grade_lbl = QLabel("Note")
        grade_lbl.setObjectName("eyebrow")
        layout.addWidget(grade_lbl)
        self.grade = _GradeSelector(initial=2.0)
        layout.addWidget(self.grade)

        # Compact form
        form = QFormLayout()
        form.setSpacing(8)

        self.subject = QComboBox()
        self.subject.addItems(SUBJECTS_ALL)
        self.subject.setEditable(True)
        form.addRow("Fach:", self.subject)

        cat_row = QHBoxLayout()
        self.cat_group = QButtonGroup(self)
        self._cat_buttons: dict[str, QRadioButton] = {}
        for value, label in CATEGORY_LABELS:
            rb = QRadioButton(label)
            self._cat_buttons[value] = rb
            self.cat_group.addButton(rb)
            cat_row.addWidget(rb)
        self._cat_buttons["schriftlich"].setChecked(True)
        form.addRow("Art:", cat_row)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        form.addRow("Datum:", self.date_edit)

        self.points = QDoubleSpinBox()
        self.points.setMaximum(1000)
        self.points.setDecimals(1)
        self.max_points = QDoubleSpinBox()
        self.max_points.setMaximum(1000)
        self.max_points.setDecimals(1)
        pts_row = QHBoxLayout()
        pts_row.addWidget(self.points)
        pts_row.addWidget(QLabel("von"))
        pts_row.addWidget(self.max_points)
        form.addRow("Punkte:", pts_row)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("optional")
        form.addRow("Notiz:", self.note_edit)

        layout.addLayout(form)
        layout.addStretch(1)

        # Sticky action bar — stays visible while the form scrolls.
        outer.addWidget(self._build_action_bar())

    def _build_action_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("stickyFooter")
        h = QHBoxLayout(bar)
        h.setContentsMargins(Spacing.S6, Spacing.S3, Spacing.S6, Spacing.S3)
        h.setSpacing(Spacing.S3)

        self.delete_btn = QPushButton("Löschen")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete)
        self.delete_btn.setVisible(False)
        h.addWidget(self.delete_btn)

        h.addStretch(1)

        cancel = QPushButton("Abbrechen")
        cancel.setObjectName("text")
        cancel.clicked.connect(self._cancel)
        h.addWidget(cancel)

        self.save_btn = QPushButton("Speichern")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        h.addWidget(self.save_btn)

        return bar

    def show_for(
        self,
        assessment_id: int | None = None,
        return_to: str = "grades",
        prefill_subject: str | None = None,
        prefill_event_id: int | None = None,
    ) -> None:
        self._assessment_id = assessment_id
        self._return_to = return_to
        self._prefill_event_id = prefill_event_id
        self._reset_fields()
        if assessment_id is None:
            self.title_label.setText("Note eintragen")
            self.delete_btn.setVisible(False)
            if prefill_subject:
                idx = self.subject.findText(prefill_subject)
                if idx >= 0:
                    self.subject.setCurrentIndex(idx)
                else:
                    self.subject.setEditText(prefill_subject)
            if prefill_event_id is not None:
                ev = events_repo.get(self.conn, prefill_event_id)
                if ev is not None:
                    d = ev["event_date"]
                    self.date_edit.setDate(QDate(int(d[:4]), int(d[5:7]), int(d[8:10])))
        else:
            self.title_label.setText("Note bearbeiten")
            self.delete_btn.setVisible(True)
            self._load_assessment(assessment_id)

    def _reset_fields(self) -> None:
        self.grade.set_value(2.0)
        self.subject.setCurrentIndex(0)
        self._cat_buttons["schriftlich"].setChecked(True)
        today = date.today()
        self.date_edit.setDate(QDate(today.year, today.month, today.day))
        self.points.setValue(0.0)
        self.max_points.setValue(0.0)
        self.note_edit.setText("")

    def _load_assessment(self, assessment_id: int) -> None:
        row = assessments_repo.get(self.conn, assessment_id)
        if row is None:
            return
        self.grade.set_value(float(row["grade"]))
        idx = self.subject.findText(row["subject"])
        if idx >= 0:
            self.subject.setCurrentIndex(idx)
        else:
            self.subject.setEditText(row["subject"])
        if row["category"] in self._cat_buttons:
            self._cat_buttons[row["category"]].setChecked(True)
        d = row["assessment_date"]
        self.date_edit.setDate(QDate(int(d[:4]), int(d[5:7]), int(d[8:10])))
        if row["points"] is not None:
            self.points.setValue(float(row["points"]))
        if row["max_points"] is not None:
            self.max_points.setValue(float(row["max_points"]))
        if row["note"]:
            self.note_edit.setText(row["note"])
        self._prefill_event_id = row["scheduled_event_id"]

    def _collect_data(self) -> dict:
        category = next(v for v, rb in self._cat_buttons.items() if rb.isChecked())
        points = self.points.value() if self.points.value() > 0 else None
        max_points = self.max_points.value() if self.max_points.value() > 0 else None
        return {
            "subject": self.subject.currentText().strip(),
            "category": category,
            "assessment_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "grade": self.grade.value(),
            "points": points,
            "max_points": max_points,
            "note": self.note_edit.text().strip() or None,
            "scheduled_event_id": self._prefill_event_id,
        }

    def _save(self) -> None:
        data = self._collect_data()
        if not data["subject"]:
            QMessageBox.information(self, "Fach fehlt", "Bitte ein Fach waehlen.")
            return
        if self._assessment_id is None:
            assessments_repo.create(
                self.conn, self.window.active_user_id,
                data["subject"], data["category"], data["assessment_date"],
                grade=data["grade"], points=data["points"], max_points=data["max_points"],
                note=data["note"], scheduled_event_id=data["scheduled_event_id"],
            )
        else:
            assessments_repo.update(
                self.conn, self._assessment_id,
                subject=data["subject"], category=data["category"],
                assessment_date=data["assessment_date"],
                grade=data["grade"], points=data["points"], max_points=data["max_points"],
                note=data["note"], scheduled_event_id=data["scheduled_event_id"],
            )
        self._navigate_back()

    def _delete(self) -> None:
        if self._assessment_id is None:
            return
        reply = QMessageBox.question(
            self, "Note loeschen?",
            "Note endgueltig loeschen?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        assessments_repo.delete(self.conn, self._assessment_id)
        self._navigate_back()

    def _cancel(self) -> None:
        self._navigate_back()

    def _navigate_back(self) -> None:
        if self._return_to == "menu":
            self.window.show_menu()
        elif self._return_to == "events":
            self.window.show_events()
        else:
            self.window.show_grades()

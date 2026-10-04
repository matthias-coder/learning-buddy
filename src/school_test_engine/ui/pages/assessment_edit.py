from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
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

from ...grading.grade_labels import GRADE_OPTIONS, clamp_grade, grade_label
from ...storage import assessments_repo, events_repo
from .._subjects import SUBJECTS_ALL, note_color
from ..design import FontFamily, Spacing
from ..widgets.date_picker import DatePicker


CATEGORY_LABELS = [
    ("schriftlich", "schriftlich"),
    ("muendlich", "mündlich"),
    ("sonstige", "sonstige"),
]


class _GradeSelector(QFrame):
    """Dropdown with grade tendencies (1, 1−, 2+, 2, ...). Legacy half-step
    values (x.5) are shown as an extra entry like "2–3" while set."""

    changed = Signal(float)

    def __init__(self, initial: float = 2.0, parent=None):
        super().__init__(parent)
        self._value = 2.0
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.combo = QComboBox()
        self.combo.setMinimumWidth(120)
        for label, val in GRADE_OPTIONS:
            self.combo.addItem(label, val)
        self._base_count = self.combo.count()
        h.addWidget(self.combo)
        h.addStretch(1)
        self.combo.currentIndexChanged.connect(self._on_index)
        self.set_value(initial)

    def _on_index(self, idx: int) -> None:
        if idx < 0:
            return
        self._value = float(self.combo.itemData(idx))
        self._drop_legacy_entry()
        self._style()
        self.changed.emit(self._value)

    def _drop_legacy_entry(self) -> None:
        # Remove the legacy "x–y" entry once the user picked something else.
        if self.combo.count() > self._base_count and self.combo.currentIndex() < self._base_count:
            self.combo.blockSignals(True)
            cur = self.combo.currentIndex()
            self.combo.removeItem(self._base_count)
            self.combo.setCurrentIndex(cur)
            self.combo.blockSignals(False)

    def _style(self) -> None:
        color = note_color(max(1, min(6, int(round(self._value)))))
        self.combo.setStyleSheet(f"QComboBox {{ color: {color}; font-weight: 600; }}")

    def value(self) -> float:
        return self._value

    def set_value(self, val: float) -> None:
        v = clamp_grade(val)
        self.combo.blockSignals(True)
        # drop any previous legacy entry
        while self.combo.count() > self._base_count:
            self.combo.removeItem(self._base_count)
        idx = next(
            (i for i in range(self._base_count)
             if abs(float(self.combo.itemData(i)) - v) < 0.01),
            -1,
        )
        if idx < 0:
            self.combo.addItem(grade_label(v), v)
            idx = self.combo.count() - 1
        self.combo.setCurrentIndex(idx)
        self.combo.blockSignals(False)
        self._value = float(self.combo.itemData(idx))
        self._style()


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

        self.date_edit = DatePicker()
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
                    # Defensive: prefill subject from event if caller didn't pass one
                    if not prefill_subject:
                        idx = self.subject.findText(ev["subject"])
                        if idx >= 0:
                            self.subject.setCurrentIndex(idx)
                        else:
                            self.subject.setEditText(ev["subject"])
                    d = ev["event_date"]
                    self.date_edit.setDate(
                        QDate(int(d[:4]), int(d[5:7]), int(d[8:10]))
                    )
                # Lock subject + date — they reflect the KA, not a free choice.
                self.subject.setEnabled(False)
                self.date_edit.setEnabled(False)
            else:
                # No event link → both fields freely editable
                self.subject.setEnabled(True)
                self.date_edit.setEnabled(True)
        else:
            self.title_label.setText("Note bearbeiten")
            self.delete_btn.setVisible(True)
            # Edit mode: both stay enabled regardless of event link
            self.subject.setEnabled(True)
            self.date_edit.setEnabled(True)
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
        pts, mx = self.points.value(), self.max_points.value()
        # 0 is a valid score; both at 0 means "not entered".
        if pts == 0 and mx == 0:
            points = max_points = None
        else:
            points = pts
            max_points = mx if mx > 0 else None
        return {
            "subject": self.subject.currentText().strip(),
            "category": category,
            "assessment_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "grade": min(self.grade.value(), 6.0),
            "points": points,
            "max_points": max_points,
            "note": self.note_edit.text().strip() or None,
            "scheduled_event_id": self._prefill_event_id,
        }

    def _save(self) -> None:
        data = self._collect_data()
        if not data["subject"]:
            QMessageBox.information(self, "Fach fehlt", "Bitte ein Fach wählen.")
            return
        if (
            data["points"] is not None and data["max_points"] is not None
            and data["points"] > data["max_points"]
        ):
            QMessageBox.information(
                self, "Punkte ungültig",
                "Die erreichten Punkte dürfen die maximalen Punkte nicht übersteigen.",
            )
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
            self, "Note löschen?",
            "Note endgültig löschen?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        assessments_repo.delete(self.conn, self._assessment_id)
        self._navigate_back()

    def _cancel(self) -> None:
        self._navigate_back()

    def _navigate_back(self) -> None:
        self.window._navigate_back()

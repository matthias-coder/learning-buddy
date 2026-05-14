from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from .._subjects import SUBJECTS_ALL, note_color
from ..design import FontFamily


CATEGORY_LABELS = [
    ("schriftlich", "schriftlich"),
    ("muendlich", "mündlich"),
    ("sonstige", "sonstige"),
]


class _GradeSelector(QFrame):
    """Big-button row 1..6 with +/- 0.5 step buttons."""
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
            b.setFixedSize(56, 56)  # was 48x48 — 56 ≥ MIN_TOUCH_SIZE (44)
            color = note_color(n)
            b.setStyleSheet(
                f"QPushButton {{ background: #f4efe6; color: {color}; "
                f"font-family: 'Fraunces'; font-size: 22pt; border: 2px solid transparent; border-radius: 10px; }}"
                f"QPushButton:checked {{ background: {color}; color: #f6f1e6; }}"
            )
            b.clicked.connect(lambda _, val=n: self._set_int(val))
            self._buttons[n] = b
            row, col = divmod(idx, 3)  # 3 columns
            h.addWidget(b, row, col)

        # Half-step toggle in a 3rd row, right-aligned (column 2)
        self._half = QPushButton(",5")
        self._half.setCheckable(True)
        self._half.setFixedSize(56, 40)  # was 40x48 — 56 wide for grid alignment
        self._half.setStyleSheet(
            "QPushButton { background: #f4efe6; color: #4a4538; "
            "font-family: 'Fraunces'; font-size: 14pt; border: 2px solid transparent; border-radius: 10px; }"
            "QPushButton:checked { background: #c79d44; color: #f6f1e6; }"
        )
        self._half.clicked.connect(self._toggle_half)
        h.addWidget(self._half, 2, 2)  # row 2 (third row), col 2 (right)

        # Make remaining cells stretchable so buttons don't get squished
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


class AssessmentDialog(QDialog):
    """Add or edit an assessment. Designed for fast entry (<= 5 seconds for default case).

    Usage:
        dlg = AssessmentDialog(parent, initial=row_or_None,
                               prefill_subject=..., prefill_event_id=...)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.data()
    """

    def __init__(self, parent=None, initial=None,
                 prefill_subject: str | None = None,
                 prefill_event_id: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("Note" if initial is None else "Note bearbeiten")
        self.setMinimumWidth(380)
        self.setMaximumWidth(540)
        self._deleted = False
        self._prefill_event_id = prefill_event_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        # Grade selector — biggest visual element
        grade_label = QLabel("Note")
        grade_label.setObjectName("eyebrow")
        layout.addWidget(grade_label)
        self.grade = _GradeSelector(initial=2.0)
        layout.addWidget(self.grade)

        # Compact form for the rest
        form = QFormLayout()
        form.setSpacing(8)

        self.subject = QComboBox()
        self.subject.addItems(SUBJECTS_ALL)
        self.subject.setEditable(True)
        if prefill_subject:
            idx = self.subject.findText(prefill_subject)
            if idx >= 0:
                self.subject.setCurrentIndex(idx)
            else:
                self.subject.setEditText(prefill_subject)
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
        today = date.today()
        self.date_edit.setDate(QDate(today.year, today.month, today.day))
        form.addRow("Datum:", self.date_edit)

        # Points (collapsible "Details")
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

    def _on_delete(self):
        self._deleted = True
        self.accept()

    def is_delete(self) -> bool:
        return self._deleted

    def data(self) -> dict:
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

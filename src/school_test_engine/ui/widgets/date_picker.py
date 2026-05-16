"""Compact three-part date picker (Day/Month/Year) — replaces wide QDateEdit
with calendar popup. Used by event, assessment and profile edit forms."""
from __future__ import annotations

import calendar
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QSizePolicy,
    QSpinBox,
    QWidget,
)


_MONTHS_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


class DatePicker(QWidget):
    """Day + Month + Year selector. Total width ~240 px instead of QDateEdit's
    full-row stretch. The day spinbox clamps to the actual number of days in
    the selected month/year automatically."""

    changed = Signal(QDate)

    def __init__(
        self,
        *,
        year_range: tuple[int, int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        today = date.today()
        self._year_range = year_range or (today.year - 5, today.year + 10)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._day = QSpinBox()
        self._day.setRange(1, 31)
        self._day.setFixedWidth(56)
        self._day.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._day.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)

        self._month = QComboBox()
        for label in _MONTHS_DE:
            self._month.addItem(label)
        self._month.setFixedWidth(140)

        self._year = QSpinBox()
        self._year.setRange(self._year_range[0], self._year_range[1])
        self._year.setFixedWidth(84)
        self._year.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._year.setGroupSeparatorShown(False)
        self._year.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)

        layout.addWidget(self._day)
        layout.addWidget(self._month)
        layout.addWidget(self._year)
        layout.addStretch(1)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._day.valueChanged.connect(self._emit_changed)
        self._month.currentIndexChanged.connect(self._on_month_or_year_changed)
        self._year.valueChanged.connect(self._on_month_or_year_changed)

        self.set_date(QDate(today.year, today.month, today.day))

    # ------------------------------------------------------------------
    # Public API — mirrors QDateEdit's date() / setDate(QDate)
    # ------------------------------------------------------------------

    def date(self) -> QDate:
        return QDate(self._year.value(), self._month.currentIndex() + 1, self._day.value())

    def set_date(self, qd: QDate) -> None:
        self._year.blockSignals(True)
        self._month.blockSignals(True)
        self._day.blockSignals(True)
        # Clamp year into the configured range so set_date never silently fails.
        y = max(self._year_range[0], min(self._year_range[1], qd.year()))
        self._year.setValue(y)
        self._month.setCurrentIndex(qd.month() - 1)
        max_day = calendar.monthrange(y, qd.month())[1]
        self._day.setRange(1, max_day)
        self._day.setValue(min(qd.day(), max_day))
        self._year.blockSignals(False)
        self._month.blockSignals(False)
        self._day.blockSignals(False)

    def setDate(self, qd: QDate) -> None:  # Qt-style alias
        self.set_date(qd)

    # ------------------------------------------------------------------

    def _on_month_or_year_changed(self, *_: object) -> None:
        # Re-clamp day spinbox: e.g. switching from January 31 → February.
        y = self._year.value()
        m = self._month.currentIndex() + 1
        max_day = calendar.monthrange(y, m)[1]
        if self._day.value() > max_day:
            self._day.blockSignals(True)
            self._day.setValue(max_day)
            self._day.blockSignals(False)
        self._day.setRange(1, max_day)
        self._emit_changed()

    def _emit_changed(self) -> None:
        self.changed.emit(self.date())

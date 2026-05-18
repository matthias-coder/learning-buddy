from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ...school_calendar.models import CalendarEntry, GradeStatus
from ..design import FontFamily
from .grade_pill import GradePill
from .pill import Pill


_PILL_VARIANT_FOR_KIND = {
    "klausur": "clay",
    "ferien": "tea",
    "frei": "honey",
    "event": "sky",
}

_PILL_LABEL_FOR_KIND = {
    "klausur": "KA",
    "ferien": "Ferien",
    "frei": "Frei",
    "event": "Event",
}


class CalendarEntryCard(QFrame):
    """Schlanke Card: [DateBadge] [Title] [KindPill] [optional NotePill].
    Klausur-Cards sind klickbar."""

    clicked = Signal(int)

    def __init__(
        self,
        entry: CalendarEntry,
        parent=None,
        *,
        grade_status: GradeStatus | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("calendarEntryCard")
        self._entry = entry

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(12)

        self._date_label = QLabel(self._format_date_range(entry))
        self._date_label.setObjectName("dateBadge")
        self._date_label.setFont(QFont(FontFamily.MONO, 10))
        self._date_label.setMinimumWidth(110)
        h.addWidget(self._date_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel(entry.title)
        title.setFont(QFont(FontFamily.BODY, 11, QFont.Weight.Medium))
        title_col.addWidget(title)
        h.addLayout(title_col)

        h.addStretch(1)

        kind_pill = Pill(_PILL_LABEL_FOR_KIND[entry.kind],
                         variant=_PILL_VARIANT_FOR_KIND[entry.kind])
        h.addWidget(kind_pill)

        if grade_status is not None:
            if grade_status.assessment_id is None:
                # Note nicht eingetragen
                note_pill = Pill("Note offen", variant="honey")
                h.addWidget(note_pill)
            elif grade_status.grade is not None:
                # Note vorhanden — GradePill mit kompakter Größe
                pill = GradePill(grade_status.grade, size=36)
                h.addWidget(pill)

        if entry.kind == "klausur":
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _format_date_range(self, e: CalendarEntry) -> str:
        if e.is_multi_day:
            same_year = e.start_date.year == e.end_date.year
            if same_year:
                return f"{e.start_date.strftime('%d.%m.')}–{e.end_date.strftime('%d.%m.')}"
            return (
                f"{e.start_date.strftime('%d.%m.%Y')}–"
                f"{e.end_date.strftime('%d.%m.%Y')}"
            )
        return e.start_date.strftime("%d.%m.")

    def _maybe_emit_click(self) -> None:
        if self._entry.kind == "klausur":
            self.clicked.emit(self._entry.entry_id)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._maybe_emit_click()
        super().mousePressEvent(event)

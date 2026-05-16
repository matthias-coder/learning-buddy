from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ...school_calendar.filters import CalendarFilters
from ...school_calendar.service import group_by_month, list_entries
from ...storage import users_repo
from ..design import Color, FontFamily
from ..widgets.calendar_entry_card import CalendarEntryCard
from ..widgets.eyebrow import Eyebrow


_CHIP_KINDS = [
    ("klausur", "KAs"),
    ("ferien", "Ferien"),
    ("frei", "Frei"),
    ("event", "Events"),
]
_TIMEFRAMES = [("future", "Ab heute"), ("all", "Alle"), ("past", "Vergangen")]


def _kind_field(kind: str) -> str:
    return {"klausur": "show_klausuren",
            "ferien": "show_ferien",
            "frei": "show_frei",
            "event": "show_events"}[kind]


def _kind_db_column(kind: str) -> str:
    return {"klausur": "calendar_show_klausuren",
            "ferien": "calendar_show_ferien",
            "frei": "calendar_show_frei",
            "event": "calendar_show_events"}[kind]


class SchoolCalendarPage(QWidget):
    """Agenda-Liste über KAs + calendar_events mit persistierten Filtern."""

    def __init__(self, window, conn: sqlite3.Connection, today: date | None = None):
        super().__init__()
        self.window = window
        self.conn = conn
        self._today_override = today
        self._user_id: int | None = window.active_user_id
        self._filters = CalendarFilters.defaults()
        self._loading = False
        self._cards: list[CalendarEntryCard] = []
        self._chip_buttons: dict[str, QPushButton] = {}
        self._tab_buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(14)

        outer.addWidget(Eyebrow("Schulkalender"))
        title = QLabel("Alle Termine")
        title.setObjectName("title")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        intro = QLabel("Klassenarbeiten, Ferien, freie Tage und Schul-Events.")
        intro.setStyleSheet(f"color: {Color.PAPER_500}; font-size: 10pt;")
        outer.addWidget(intro)

        # Filter row: chips
        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        for kind, label in _CHIP_KINDS:
            b = QPushButton(label)
            b.setObjectName("filterChip")
            b.setCheckable(True)
            b.setChecked(True)
            b.toggled.connect(lambda checked, k=kind: self._on_chip_toggled(k, checked))
            self._chip_buttons[kind] = b
            chip_row.addWidget(b)
        chip_row.addStretch(1)
        outer.addLayout(chip_row)

        # Timeframe tabs
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        for tf, label in _TIMEFRAMES:
            b = QPushButton(label)
            b.setObjectName("subjectTab")
            b.setCheckable(True)
            b.clicked.connect(lambda _, t=tf: self._on_timeframe_changed(t))
            self._tab_group.addButton(b)
            self._tab_buttons[tf] = b
            tab_row.addWidget(b)
        tab_row.addStretch(1)
        outer.addLayout(tab_row)

        # Empty-state label
        self._empty_label = QLabel("")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {Color.PAPER_600}; font-family: 'Fraunces'; "
            f"font-style: italic; font-size: 13pt; padding: 40px;"
        )
        self._empty_label.setVisible(False)
        outer.addWidget(self._empty_label)

        # Scrollable list
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list_host)
        outer.addWidget(self._scroll, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        self._user_id = self.window.active_user_id
        if self._user_id is None:
            return
        user_row = users_repo.get_user(self.conn, self._user_id)
        self._filters = CalendarFilters.from_user_row(user_row)
        self._loading = True
        try:
            self._apply_filters_to_ui()
        finally:
            self._loading = False
        self._reload_list_only()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _today(self) -> date:
        return self._today_override or date.today()

    def _apply_filters_to_ui(self) -> None:
        for kind, btn in self._chip_buttons.items():
            checked = getattr(self._filters, _kind_field(kind))
            btn.setChecked(bool(checked))
        for tf, btn in self._tab_buttons.items():
            btn.setChecked(tf == self._filters.timeframe)

    def _reload_list_only(self) -> None:
        self._clear_cards()
        if not self._filters.active_kinds():
            self._show_empty(
                "Alle Filter sind ausgeschaltet — klick oben eine Kategorie an."
            )
            return
        entries = list_entries(self.conn, self._user_id, self._today(), self._filters)
        if not entries:
            self._show_empty("Keine Termine im gewählten Zeitraum.")
            return
        self._empty_label.setVisible(False)
        for month_label, month_entries in group_by_month(entries):
            self._add_month_header(month_label)
            for entry in month_entries:
                card = CalendarEntryCard(entry, parent=self._list_host)
                if entry.kind == "klausur":
                    card.clicked.connect(self._open_klausur)
                self._cards.append(card)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def _clear_cards(self) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._cards = []

    def _add_month_header(self, label: str) -> None:
        eb = Eyebrow(label.upper())
        eb.setParent(self._list_host)
        self._list_layout.insertWidget(self._list_layout.count() - 1, eb)

    def _show_empty(self, text: str) -> None:
        self._empty_label.setText(text)
        self._empty_label.setVisible(True)

    def _on_chip_toggled(self, kind: str, checked: bool) -> None:
        if self._loading or self._user_id is None:
            return
        self._filters = self._filters.with_kind_set(kind, checked)
        users_repo.update_user(
            self.conn, self._user_id,
            **{_kind_db_column(kind): int(checked)},
        )
        self._reload_list_only()

    def _on_timeframe_changed(self, tf: str) -> None:
        if self._loading or self._user_id is None:
            return
        self._filters = self._filters.with_timeframe(tf)
        users_repo.update_user(self.conn, self._user_id, calendar_timeframe=tf)
        self._reload_list_only()

    def _open_klausur(self, event_id: int) -> None:
        if hasattr(self.window, "show_event_edit"):
            self.window.show_event_edit(event_id, return_to="school_calendar")

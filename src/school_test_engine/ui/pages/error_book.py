from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...error_book import queries as error_book_queries
from ...error_book.models import ErrorBookEntry
from ..design import Color, FontFamily, Semantic
from ..widgets.eyebrow import Eyebrow
from ..widgets.flow_layout import FlowLayout
from ..widgets.pill import Pill
from .._format import fmt_dt
from .._subjects import SUBJECTS_ALL, subject_variant


class ErrorBookPage(QWidget):
    """Pro-Fach-Liste offener Fehler + One-Click-Übungs-Button im Header."""

    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._current_subject: str | None = None
        self._subject_buttons: dict[str, QPushButton] = {}
        self._last_counts: dict[str, int] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(16)

        outer.addWidget(Eyebrow("Fehlerheft"))
        title = QLabel("Was nochmal hakt")
        title.setObjectName("title")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        # Subject-Pill-Row mit FlowLayout (analog grades.py)
        self._subject_host = QWidget()
        self._subject_row = FlowLayout(self._subject_host, h_spacing=6, v_spacing=6)
        for s in SUBJECTS_ALL:
            b = QPushButton(s)
            b.setCheckable(True)
            b.setObjectName("subjectTab")
            b.clicked.connect(lambda _, sub=s: self._select_subject(sub))
            self._subject_buttons[s] = b
            self._subject_row.addWidget(b)
        outer.addWidget(self._subject_host)

        # Globale Empty-State Card
        self.empty_label = QLabel("Noch keine offenen Fehler — sauber.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(
            f"color: {Color.PAPER_600}; font-family: 'Fraunces'; "
            f"font-style: italic; font-size: 13pt; padding: 40px;"
        )
        outer.addWidget(self.empty_label)

        # Per-Subject Empty-Hinweis
        self.subject_empty_label = QLabel("In diesem Fach gerade alles im Lot.")
        self.subject_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subject_empty_label.setStyleSheet(
            f"color: {Color.PAPER_600}; font-size: 11pt; padding: 30px;"
        )
        outer.addWidget(self.subject_empty_label)

        # Scrollable list of error cards
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(10)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._list_container)
        outer.addWidget(self._scroll, stretch=1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        uid = self.window.active_user_id
        if uid is None:
            return
        counts = error_book_queries.count_open(self.conn, uid)
        self._last_counts = counts
        total = sum(counts.values())

        # Refresh subject pill labels + enabled state
        for sub, btn in self._subject_buttons.items():
            n = counts.get(sub, 0)
            btn.setText(f"{sub} · {n}" if n > 0 else sub)
            btn.setEnabled(n > 0)

        if total == 0:
            self.empty_label.show()
            self.subject_empty_label.hide()
            self._subject_host.setVisible(False)
            self._scroll.hide()
            self._current_subject = None
            self._refresh_action_button()
            return

        # Wähle Default-Fach: erstes mit count>0, sonst erstes SUBJECTS_ALL
        if self._current_subject is None or counts.get(self._current_subject, 0) == 0:
            self._current_subject = next(
                (s for s in SUBJECTS_ALL if counts.get(s, 0) > 0),
                SUBJECTS_ALL[0],
            )

        self.empty_label.hide()
        self._subject_host.setVisible(True)
        for sub, btn in self._subject_buttons.items():
            btn.setChecked(sub == self._current_subject)

        # Render Card-Liste oder per-Subject-Empty
        entries = error_book_queries.list_open_entries(
            self.conn, uid, subject=self._current_subject
        )
        self._clear_cards()
        if not entries:
            self.subject_empty_label.show()
            self._scroll.hide()
        else:
            self.subject_empty_label.hide()
            self._scroll.show()
            for e in entries:
                self._list_layout.addWidget(_make_entry_card(e))
            self._list_layout.addStretch(1)
        self._refresh_action_button()

    def practice_button_count(self) -> int:
        """Anzahl Fragen für den Üben-Button im aktiven Fach (gekappt bei 10).
        Liest aus dem Cache, der von reload() befüllt wird — vermeidet einen zweiten
        DB-Scan beim Refreshen des Action-Buttons im Global-Header."""
        if self._current_subject is None:
            return 0
        return min(self._last_counts.get(self._current_subject, 0), 10)

    def trigger_practice(self) -> None:
        if self._current_subject is None:
            return
        self.window.start_error_book_practice(self._current_subject)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _select_subject(self, subject: str) -> None:
        self._current_subject = subject
        self.reload()

    def _clear_cards(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _refresh_action_button(self) -> None:
        """Sagt MainWindow Bescheid, dass der Üben-Button im Header
        aktualisiert werden muss (z.B. nach Subject-Wechsel)."""
        refresh = getattr(self.window, "_refresh_error_book_action", None)
        if refresh is not None:
            refresh()


def _make_entry_card(e: ErrorBookEntry) -> QFrame:
    card = QFrame()
    card.setObjectName("assessmentCard")  # Reuse-Stil
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    v = QVBoxLayout(card)
    v.setContentsMargins(18, 14, 18, 14)
    v.setSpacing(8)

    top = QHBoxLayout()
    top.setSpacing(10)
    if e.topic:
        top.addWidget(Pill(e.topic.upper(), subject_variant(e.subject)))
    prompt = QLabel(e.prompt_excerpt)
    prompt.setWordWrap(True)
    prompt.setStyleSheet(f"color: {Semantic.FG}; font-size: 11pt;")
    top.addWidget(prompt, stretch=1)
    v.addLayout(top)

    bottom = QHBoxLayout()
    bottom.setSpacing(8)
    left_text = f"{e.wrong_count}× falsch · zuletzt {fmt_dt(e.last_wrong_at)}"
    left = QLabel(left_text)
    left.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
    bottom.addWidget(left)
    bottom.addStretch(1)
    streak = QLabel(_streak_text(e.consecutive_correct))
    streak.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
    bottom.addWidget(streak)
    v.addLayout(bottom)

    return card


def _streak_text(consecutive_correct: int) -> str:
    if consecutive_correct >= 1:
        return "●○ noch 1× richtig"
    return "○○ noch 2× richtig"

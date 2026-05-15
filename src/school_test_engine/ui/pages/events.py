from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...config import db_path
from ...ical_sync import SyncResult
from ...storage import events_repo, assessments_repo, users_repo
from ..design import Color, FontFamily, Semantic
from ..sync_worker import SyncWorker
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
    def __init__(self, window, conn: sqlite3.Connection, *, sync_runner=None):
        super().__init__()
        self.window = window
        self.conn = conn
        self._sync_runner = sync_runner
        self._sync_thread: QThread | None = None
        self._sync_worker: SyncWorker | None = None

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

        # Sync row (Phase 15)
        sync_row = QHBoxLayout()
        self.sync_button = QPushButton("↻ Synchronisieren")
        self.sync_button.setObjectName("text")
        self.sync_button.clicked.connect(self._start_sync)
        sync_row.addWidget(self.sync_button)
        sync_row.addStretch(1)
        outer.addLayout(sync_row)

        self.sync_status_label = QLabel("")
        self.sync_status_label.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 9pt;")
        self.sync_status_label.setWordWrap(True)
        outer.addWidget(self.sync_status_label)

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

        # React to background sync (MainWindow.events_synced) — keep list fresh
        if hasattr(window, "events_synced"):
            window.events_synced.connect(self.reload)

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
            self._update_sync_state()
            return

        today_iso = date.today().isoformat()
        for ev in events:
            card = self._make_event_row(ev, is_past=ev["event_date"] < today_iso)
            self._list_layout.addWidget(card)
        self._update_sync_state()

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
    # Sync (Phase 15)
    # ------------------------------------------------------------------

    def _has_feed_url(self) -> bool:
        uid = self.window.active_user_id
        if uid is None:
            return False
        row = users_repo.get_user(self.conn, uid)
        return bool(row and row["ical_feed_url"])

    def _update_sync_state(self) -> None:
        enabled = self._has_feed_url()
        self.sync_button.setEnabled(enabled and self._sync_thread is None)
        if not enabled:
            self.sync_status_label.setText("Schulkalender nicht verknüpft")
            return
        self._refresh_status_from_db()

    def _refresh_status_from_db(self) -> None:
        uid = self.window.active_user_id
        row = users_repo.get_user(self.conn, uid)
        if not row or not row["ical_last_sync_at"]:
            self.sync_status_label.setText("Noch nicht synchronisiert")
            return
        summary = json.loads(row["ical_last_sync_summary"] or "{}")
        if summary.get("error"):
            self.sync_status_label.setText(f"Letzter Sync fehlgeschlagen: {summary['error']}")
            return
        parts = []
        if summary.get("added"):   parts.append(f"{summary['added']} neu")
        if summary.get("updated"): parts.append(f"{summary['updated']} verschoben")
        if summary.get("deleted"): parts.append(f"{summary['deleted']} entfernt")
        suffix = " · " + ", ".join(parts) if parts else " · bereits aktuell"
        self.sync_status_label.setText(f"Zuletzt synchronisiert{suffix}")

    def _start_sync(self) -> None:
        if self._sync_thread is not None:
            return
        self.sync_button.setEnabled(False)
        self.sync_status_label.setText("Synchronisiere…")
        if self._sync_runner is not None:
            # Test-injected synchronous runner
            self._sync_runner(self._on_sync_done)
        else:
            self._sync_thread = QThread()
            self._sync_worker = SyncWorker(db_path(), self.window.active_user_id)
            self._sync_worker.moveToThread(self._sync_thread)
            self._sync_thread.started.connect(self._sync_worker.run)
            self._sync_worker.finished.connect(self._on_sync_done)
            self._sync_worker.finished.connect(self._sync_thread.quit)
            self._sync_thread.finished.connect(self._sync_thread.deleteLater)
            self._sync_thread.start()

    def _on_sync_done(self, result: SyncResult) -> None:
        worker_user_id = self._sync_worker.user_id if self._sync_worker else self.window.active_user_id
        self._sync_thread = None
        self._sync_worker = None
        self.sync_button.setEnabled(True)
        if worker_user_id != self.window.active_user_id:
            return  # user switched; discard UI update
        # Rebuild events list first; the label below is the canonical
        # "just-synced" message and must NOT be overwritten by reload().
        self._rebuild_event_list()
        if result.error:
            self.sync_status_label.setText(f"Sync fehlgeschlagen: {result.error}")
            return
        parts = []
        if result.added:   parts.append(f"{result.added} neu")
        if result.updated: parts.append(f"{result.updated} verschoben")
        if result.deleted: parts.append(f"{result.deleted} entfernt")
        suffix = ", ".join(parts) if parts else "bereits aktuell"
        self.sync_status_label.setText(f"Zuletzt synchronisiert · {suffix}")
        if hasattr(self.window, "events_synced"):
            self.window.events_synced.emit()

    def _rebuild_event_list(self) -> None:
        """reload() without touching the sync status label."""
        uid = self.window.active_user_id
        if uid is None:
            return
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

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_event(self):
        self.window.show_event_edit(event_id=None, return_to="events")

    def _edit_event(self, event_id: int):
        self.window.show_event_edit(event_id=event_id, return_to="events")

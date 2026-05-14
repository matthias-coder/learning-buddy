from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...storage import assessments_repo, attempts_repo
from .._format import fmt_dt, fmt_num
from .._layouts import clear_layout
from .._subjects import note_color, subject_variant
from ..design import FontFamily, Semantic
from ..widgets.clickable_card import ClickableCard
from ..widgets.eyebrow import Eyebrow
from ..widgets.grade_heatmap import GradeHeatmap
from ..widgets.pill import Pill
from ..widgets.sparkline import Sparkline


class HistoryPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._attempts: list = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 28, 40, 24)
        outer.setSpacing(12)

        outer.addWidget(Eyebrow("Rückblick"))
        title = QLabel("Bisherige Versuche")
        title.setObjectName("title")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        self.spark_label = Eyebrow("Notenverlauf  —  älteste links, neueste rechts")
        outer.addWidget(self.spark_label)
        self.spark_container = QWidget()
        self.spark_layout = QVBoxLayout(self.spark_container)
        self.spark_layout.setContentsMargins(0, 0, 0, 0)
        self.spark_layout.setSpacing(0)
        outer.addWidget(self.spark_container)

        # Phase 14: Wochen-Heatmap
        self.heatmap_label = Eyebrow("WOCHEN-ÜBERSICHT")
        outer.addWidget(self.heatmap_label)
        self.heatmap = GradeHeatmap()
        outer.addWidget(self.heatmap)

        self.empty_label = QLabel(
            "Noch keine abgeschlossenen Tests. Mach den ersten — er taucht hier auf."
        )
        self.empty_label.setStyleSheet(f"color: {Semantic.FG_MUTED}; padding: 24px 0;")
        outer.addWidget(self.empty_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.scroll.setWidget(self.list_container)
        outer.addWidget(self.scroll, stretch=1)

        bottom = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(window.show_menu)
        bottom.addWidget(back)
        bottom.addStretch(1)
        export_btn = QPushButton("CSV exportieren")
        export_btn.setObjectName("text")
        export_btn.clicked.connect(self._export_csv)
        bottom.addWidget(export_btn)
        outer.addLayout(bottom)

    def reload(self) -> None:
        self._attempts = attempts_repo.list_all_attempts(
            self.conn, self.window.active_user_id
        )
        self._render_sparkline(self._attempts)
        self._render_heatmap()
        self._render_cards(self._attempts)

    def _render_heatmap(self) -> None:
        from datetime import date, timedelta
        uid = self.window.active_user_id
        if uid is None:
            self.heatmap.hide()
            self.heatmap_label.hide()
            return
        today = date.today()
        monday_today = today - timedelta(days=today.weekday())
        weeks = [monday_today - timedelta(weeks=i) for i in reversed(range(8))]
        raw = assessments_repo.heatmap_data(self.conn, uid, weeks_back=8)
        if not raw:
            self.heatmap.hide()
            self.heatmap_label.hide()
            return
        rows = sorted(raw.items(), key=lambda kv: kv[0])
        self.heatmap.set_data(weeks=weeks, rows=rows)
        self.heatmap.show()
        self.heatmap_label.show()

    def _render_sparkline(self, attempts) -> None:
        clear_layout(self.spark_layout)
        if not attempts:
            self.spark_container.hide()
            self.spark_label.hide()
            return
        notes = [int(a["note"]) for a in reversed(attempts) if a["note"] is not None]
        if len(notes) < 2:
            self.spark_container.hide()
            self.spark_label.hide()
            return
        self.spark_container.show()
        self.spark_label.show()
        sl = Sparkline(notes, y_min=1.0, y_max=6.0, invert_y=True)
        sl.setMinimumHeight(56)
        self.spark_layout.addWidget(sl)

    def _render_cards(self, attempts) -> None:
        clear_layout(self.list_layout)

        if not attempts:
            self.empty_label.show()
            self.scroll.hide()
            return
        self.empty_label.hide()
        self.scroll.show()

        for a in attempts:
            card = _make_attempt_card(a)
            attempt_id = int(a["id"])
            card.clicked.connect(lambda _aid=attempt_id: self.window.show_results(_aid))
            self.list_layout.addWidget(card)
        self.list_layout.addStretch(1)

    def _export_csv(self) -> None:
        if not self._attempts:
            QMessageBox.information(
                self, "Nichts zu exportieren", "Es gibt noch keine abgeschlossenen Tests."
            )
            return
        default_name = (
            f"uebungstests-verlauf-{datetime.now().strftime('%Y-%m-%d')}.csv"
        )
        path_str, _ = QFileDialog.getSaveFileName(
            self, "CSV-Datei speichern",
            str(Path.home() / default_name),
            "CSV-Dateien (*.csv)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(
                    ["Datum", "Fach", "Test", "Note", "Punkte", "Punkte möglich", "Prozent"]
                )
                for a in self._attempts:
                    writer.writerow([
                        fmt_dt(a["finished_at"], with_time=True),
                        a["subject"],
                        a["test_title"],
                        int(a["note"]) if a["note"] is not None else "",
                        fmt_num(a["points_earned"]),
                        int(a["points_possible"]),
                        f"{a['percent']:.1f}" if a["percent"] is not None else "",
                    ])
        except OSError as e:
            QMessageBox.warning(self, "Fehler beim Speichern", str(e))
            return
        QMessageBox.information(
            self, "Export erfolgreich",
            f"{len(self._attempts)} Zeile(n) gespeichert in:\n{path}",
        )


def _make_attempt_card(row) -> ClickableCard:
    card = ClickableCard(object_name="attemptCard")
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    card.setMinimumHeight(96)

    layout = QHBoxLayout(card)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(16)

    left = QVBoxLayout()
    left.setSpacing(4)
    pill_row = QHBoxLayout()
    pill_row.setSpacing(6)
    pill_row.addWidget(Pill(row["subject"], subject_variant(row["subject"])))
    pill_row.addStretch(1)
    left.addLayout(pill_row)

    title = QLabel(row["test_title"])
    title.setFont(QFont(FontFamily.DISPLAY, 15, QFont.Weight.Medium))
    title.setStyleSheet(f"color: {Semantic.FG};")
    title.setWordWrap(True)
    left.addWidget(title)

    date = QLabel(fmt_dt(row["finished_at"], with_time=True))
    date.setStyleSheet(f"color: {Semantic.FG_MUTED}; font-size: 10pt;")
    left.addWidget(date)
    layout.addLayout(left, stretch=1)

    right = QVBoxLayout()
    right.setSpacing(0)
    right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    note_int = int(row["note"]) if row["note"] is not None else 0
    note_lbl = QLabel(str(note_int))
    note_lbl.setStyleSheet(
        f"font-family: 'Fraunces'; font-size: 36pt; font-weight: 500; "
        f"color: {note_color(note_int)};"
    )
    note_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
    right.addWidget(note_lbl)
    pts = QLabel(
        f"{fmt_num(row['points_earned'])} / {row['points_possible']} P. · {row['percent']:.0f} %"
    )
    pts.setStyleSheet(f"color: {Semantic.FG_MUTED}; font-size: 10pt;")
    pts.setAlignment(Qt.AlignmentFlag.AlignRight)
    right.addWidget(pts)
    layout.addLayout(right)

    return card

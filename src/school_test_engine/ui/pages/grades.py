from __future__ import annotations

import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...cockpit import service as cockpit
from ...storage import assessments_repo
from ..design import Color, FontFamily, Semantic
from ..widgets.comparison_view import ComparisonView
from ..widgets.grade_chart import GradeChart
from ..widgets.grade_pill import GradePill
from ..widgets.pill import Pill
from .._subjects import SUBJECTS_ALL, subject_variant


CATEGORY_LABEL = {"schriftlich": "schriftlich", "muendlich": "mündlich", "sonstige": "sonstige"}


def _format_date(iso: str) -> str:
    d = datetime.fromisoformat(iso).date()
    return d.strftime("%d.%m.%Y")


class GradesPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._current_subject = SUBJECTS_ALL[0]

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(16)

        # Header
        head = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(self.window.show_menu)
        head.addWidget(back)
        head.addStretch(1)
        add = QPushButton("+ Note")
        add.setObjectName("primary")
        add.clicked.connect(self._add_assessment)
        head.addWidget(add)
        outer.addLayout(head)

        eyebrow = QLabel("NOTEN")
        eyebrow.setObjectName("eyebrow")
        outer.addWidget(eyebrow)

        title = QLabel("Wie's läuft")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        # Subject pill row
        self._subject_row = QHBoxLayout()
        self._subject_row.setSpacing(6)
        self._subject_buttons: dict[str, QPushButton] = {}
        for s in SUBJECTS_ALL:
            b = QPushButton(s)
            b.setCheckable(True)
            b.setObjectName("subjectTab")
            b.clicked.connect(lambda _, sub=s: self._select_subject(sub))
            self._subject_buttons[s] = b
            self._subject_row.addWidget(b)
        self._subject_row.addStretch(1)
        outer.addLayout(self._subject_row)

        # Scrollable content
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setSpacing(14)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, 1)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reload(self) -> None:
        for sub, btn in self._subject_buttons.items():
            btn.setChecked(sub == self._current_subject)
        self._render_content()

    def _select_subject(self, subject: str):
        self._current_subject = subject
        self.reload()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_content(self):
        uid = self.window.active_user_id
        if uid is None:
            return
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Hero: subject average
        avg = cockpit.subject_grade_average(self.conn, uid, self._current_subject)
        self._content_layout.addWidget(self._build_average_hero(avg))

        # List of assessments
        rows = assessments_repo.list_by_subject(self.conn, uid, self._current_subject)

        # Phase 14: Notenverlauf-Chart
        from datetime import date as _date
        chart_eyebrow = QLabel("NOTENVERLAUF")
        chart_eyebrow.setObjectName("eyebrow")
        self._content_layout.addWidget(chart_eyebrow)
        schriftlich_pts = [
            (_date.fromisoformat(r["assessment_date"]), float(r["grade"]))
            for r in rows if r["category"] == "schriftlich"
        ]
        muendlich_pts = [
            (_date.fromisoformat(r["assessment_date"]), float(r["grade"]))
            for r in rows if r["category"] == "muendlich"
        ]
        chart = GradeChart()
        chart.set_data(schriftlich=schriftlich_pts, muendlich=muendlich_pts)
        self._content_layout.addWidget(chart)

        if not rows:
            empty = QLabel("Noch keine Noten in diesem Fach.\nKlick auf „+ Note“ um deine erste einzutragen.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 11pt; padding: 30px;")
            empty.setWordWrap(True)
            self._content_layout.addWidget(empty)
        else:
            for r in rows:
                self._content_layout.addWidget(self._build_assessment_card(r))

        # Aggregate comparison (across all subjects)
        agg = cockpit.aggregate_comparison(self.conn, uid)
        if agg is not None:
            agg_lbl = QLabel(agg.label)
            agg_lbl.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 11pt; padding-top: 20px;")
            agg_lbl.setWordWrap(True)
            self._content_layout.addWidget(agg_lbl)

    def _build_average_hero(self, avg) -> QFrame:
        f = QFrame()
        f.setObjectName("gradeHero")
        h = QHBoxLayout(f)
        h.setContentsMargins(20, 18, 20, 18)
        h.setSpacing(20)

        if avg.zeugnis_estimate is not None:
            h.addWidget(GradePill(avg.zeugnis_estimate, size=84))
        else:
            placeholder = QLabel("—")
            placeholder.setFixedSize(84, 84)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(
                "background: #f4efe6; color: #b3a98e; font-family: 'Fraunces'; "
                "font-size: 32pt; border-radius: 42px;"
            )
            h.addWidget(placeholder)

        details = QVBoxLayout()
        details.setSpacing(4)
        eyebrow = QLabel("ZEUGNIS-SCHÄTZUNG · 50/50")
        eyebrow.setObjectName("eyebrow")
        details.addWidget(eyebrow)
        zeugnis_value = "—" if avg.zeugnis_estimate is None else f"{avg.zeugnis_estimate:.2f}".replace(".", ",")
        zeugnis_lbl = QLabel(zeugnis_value)
        zeugnis_lbl.setFont(QFont(FontFamily.DISPLAY, 22, QFont.Weight.Normal))
        details.addWidget(zeugnis_lbl)

        breakdown = QLabel(
            f"schriftlich {self._fmt_avg(avg.schriftlich_avg)}   ·   mündlich {self._fmt_avg(avg.muendlich_avg)}"
        )
        breakdown.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
        details.addWidget(breakdown)
        h.addLayout(details)
        h.addStretch(1)
        return f

    def _fmt_avg(self, val: float | None) -> str:
        if val is None:
            return "—"
        return f"{val:.2f}".replace(".", ",")

    def _build_assessment_card(self, row) -> QFrame:
        card = QFrame()
        card.setObjectName("assessmentCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(GradePill(float(row["grade"]), size=44))
        info = QVBoxLayout()
        info.setSpacing(2)
        cat_lbl = QLabel(CATEGORY_LABEL.get(row["category"], row["category"]).upper())
        cat_lbl.setObjectName("eyebrow")
        info.addWidget(cat_lbl)
        date_lbl = QLabel(_format_date(row["assessment_date"]))
        date_lbl.setStyleSheet(f"color: {Semantic.FG}; font-size: 11pt;")
        info.addWidget(date_lbl)
        if row["points"] is not None and row["max_points"] is not None:
            pts = QLabel(f"{row['points']:.0f} / {row['max_points']:.0f} Punkte")
            pts.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
            info.addWidget(pts)
        if row["note"]:
            note = QLabel(row["note"])
            note.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt; font-style: italic;")
            note.setWordWrap(True)
            info.addWidget(note)
        head.addLayout(info, 1)

        edit_btn = QPushButton("Bearbeiten")
        edit_btn.setObjectName("text")
        edit_btn.clicked.connect(lambda _, aid=row["id"]: self._edit_assessment(aid))
        head.addWidget(edit_btn)
        v.addLayout(head)

        # Comparison block if linked
        if row["scheduled_event_id"] is not None:
            cmp = cockpit.comparison_for_assessment(self.conn, row["id"])
            if cmp is not None:
                v.addWidget(ComparisonView(cmp))

        return card

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_assessment(self):
        self.window.show_assessment_edit(
            assessment_id=None,
            return_to="grades",
            prefill_subject=self._current_subject,
        )

    def _edit_assessment(self, assessment_id: int):
        self.window.show_assessment_edit(
            assessment_id=assessment_id,
            return_to="grades",
        )

from __future__ import annotations

import sqlite3

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
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

from ...grading.gaps import TREND_ARROW, apply_trend, topic_stats_from_rows
from ...storage import attempts_repo
from ...study.builder import StudyBuildError, build_study_test
from .._format import fmt_num
from .._layouts import clear_layout
from .._subjects import SUBJECTS_ALL, subject_variant, trend_variant
from ..design import FontFamily, Semantic
from ..widgets.eyebrow import Eyebrow
from ..widgets.pill import Pill
from ..widgets.shadow import apply_warm_shadow
from ..widgets.topic_bar import TopicBar

SUBJECTS = ["Alle", *SUBJECTS_ALL]
STUDY_THRESHOLD = 80.0
ACTION_COL_WIDTH = 80


class GapsPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 28, 40, 24)
        outer.setSpacing(12)

        outer.addWidget(Eyebrow("Analyse"))
        title = QLabel("Was noch hakt")
        title.setObjectName("title")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        lede = QLabel(
            "Themen sortiert nach Schwäche — übe gezielt das, was unten rot leuchtet."
        )
        lede.setObjectName("lede")
        lede.setWordWrap(True)
        outer.addWidget(lede)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(Eyebrow("Fach"))
        self.subject_combo = QComboBox()
        self.subject_combo.addItems(SUBJECTS)
        self.subject_combo.currentTextChanged.connect(self._reload_data)
        filter_row.addWidget(self.subject_combo)
        filter_row.addStretch(1)
        outer.addLayout(filter_row)

        self.empty_label = QLabel(
            "Noch nichts geübt. Sobald du Tests gemacht hast, zeigen wir hier, "
            "was am ehesten Aufmerksamkeit braucht."
        )
        self.empty_label.setWordWrap(True)
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
        outer.addLayout(bottom)

    def reload(self) -> None:
        self._reload_data()

    def _reload_data(self) -> None:
        subject = self.subject_combo.currentText()
        subj_filter = None if subject == "Alle" else subject

        uid = self.window.active_user_id
        stats = topic_stats_from_rows(attempts_repo.topic_stats(self.conn, uid, subj_filter))
        history_rows = attempts_repo.topic_history(self.conn, uid, subj_filter)
        stats = apply_trend(stats, history_rows)
        stats.sort(key=lambda s: s.percent)

        clear_layout(self.list_layout)

        if not stats:
            self.empty_label.show()
            self.scroll.hide()
            return
        self.empty_label.hide()
        self.scroll.show()

        show_subject = subject == "Alle"
        for s in stats:
            card = _make_topic_card(
                s,
                show_subject=show_subject,
                on_practice=lambda _=False, topic=s.topic, subj=s.subject: self._start_practice(topic, subj),
            )
            self.list_layout.addWidget(card)
        self.list_layout.addStretch(1)

    def _start_practice(self, topic: str, subject: str) -> None:
        try:
            test_id = build_study_test(
                self.conn, topic=topic, subject=subject,
                user_id=self.window.active_user_id,
            )
        except StudyBuildError as e:
            QMessageBox.information(self, "Keine Fragen", str(e))
            return
        self.window.start_test(test_id)


def _make_topic_card(s, *, show_subject: bool, on_practice) -> QFrame:
    card = QFrame()
    card.setObjectName("topicCard")
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    card.setMinimumHeight(96)
    apply_warm_shadow(card, blur=10, dy=2, alpha=0.05)

    layout = QHBoxLayout(card)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(16)

    left = QVBoxLayout()
    left.setSpacing(6)

    pill_row = QHBoxLayout()
    pill_row.setSpacing(6)
    if show_subject and s.subject:
        pill_row.addWidget(Pill(s.subject, subject_variant(s.subject)))
    if s.trend != "none":
        arrow_char = TREND_ARROW.get(s.trend, "")
        if arrow_char:
            pill_row.addWidget(Pill(f"{arrow_char} Trend", trend_variant(s.trend)))
    pill_row.addStretch(1)
    left.addLayout(pill_row)

    topic_lbl = QLabel(s.topic)
    topic_lbl.setFont(QFont(FontFamily.DISPLAY, 15, QFont.Weight.Medium))
    topic_lbl.setStyleSheet(f"color: {Semantic.FG};")
    topic_lbl.setWordWrap(True)
    left.addWidget(topic_lbl)

    bar_row = QHBoxLayout()
    bar_row.setSpacing(10)
    bar = TopicBar(s.percent)
    bar.setMinimumWidth(220)
    bar_row.addWidget(bar, stretch=1)
    pts_lbl = QLabel(f"{fmt_num(s.earned)} / {int(s.possible)} P. · {s.percent:.0f} %")
    pts_lbl.setStyleSheet(f"color: {Semantic.FG_MUTED}; font-size: 10pt;")
    bar_row.addWidget(pts_lbl)
    left.addLayout(bar_row)

    layout.addLayout(left, stretch=1)

    if s.percent < STUDY_THRESHOLD and s.subject:
        # Ghost button (no objectName) — quieter than primary clay, so a list
        # of many weak topics doesn't read as a wall of CTAs.
        practice = QPushButton("Üben →")
        practice.setToolTip(
            f"Übungs-Session mit Fragen zu '{s.topic}' aus dem Fach {s.subject}."
        )
        practice.clicked.connect(on_practice)
        layout.addWidget(practice)
    else:
        layout.addSpacing(ACTION_COL_WIDTH)

    return card

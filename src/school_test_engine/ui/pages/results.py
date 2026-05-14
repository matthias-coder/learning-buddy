from __future__ import annotations

import html as html_lib
import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextDocument
from PySide6.QtPrintSupport import QPrintPreviewDialog, QPrinter
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

from ...storage import attempts_repo
from .._format import fmt_dt, fmt_num
from .._layouts import clear_layout, row_get
from .._subjects import note_color
from ..design import Color, FontFamily, Semantic
from ..widgets.eyebrow import Eyebrow
from ..widgets.math_view import MathView
from ..widgets.pill import Pill
from ..widgets.shadow import apply_warm_shadow


# Schwellen für die Topic-Pill-Farbe in der Gaps-Zeile
GAP_THRESHOLD_RED = 50
GAP_THRESHOLD_YELLOW = 80


class ResultsPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._last_attempt: dict | None = None
        self._last_answers: list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 24)
        layout.setSpacing(12)

        self.eyebrow = Eyebrow("Ergebnis")
        layout.addWidget(self.eyebrow)
        self.header = QLabel()
        self.header.setObjectName("title")
        self.header.setFont(QFont(FontFamily.DISPLAY, 22, QFont.Weight.Normal))
        self.header.setWordWrap(True)
        layout.addWidget(self.header)

        summary_card = QFrame()
        summary_card.setObjectName("summaryCard")
        summary_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        apply_warm_shadow(summary_card, blur=14, dy=2, alpha=0.07)

        sl = QHBoxLayout(summary_card)
        sl.setContentsMargins(20, 14, 24, 14)
        sl.setSpacing(20)

        note_col = QVBoxLayout()
        note_col.setSpacing(0)
        note_col.addWidget(Eyebrow("Note"))
        self.note_label = QLabel()
        self.note_label.setObjectName("bigNote")
        self.note_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        note_col.addWidget(self.note_label)
        sl.addLayout(note_col)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet(f"color: {Semantic.BORDER_SUBTLE};")
        divider.setFixedHeight(64)
        sl.addWidget(divider)

        right_col = QVBoxLayout()
        right_col.setSpacing(2)
        right_col.addWidget(Eyebrow("Punkte"))
        self.points_label = QLabel()
        self.points_label.setStyleSheet(
            f"font-family: 'Fraunces'; font-size: 18pt; color: {Semantic.FG};"
        )
        right_col.addWidget(self.points_label)
        self.percent_label = QLabel()
        self.percent_label.setStyleSheet(f"color: {Semantic.FG_MUTED}; font-size: 10pt;")
        right_col.addWidget(self.percent_label)
        sl.addLayout(right_col)
        sl.addStretch(1)

        self.date_label = QLabel()
        self.date_label.setStyleSheet(f"color: {Semantic.FG_MUTED}; font-size: 10pt;")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        sl.addWidget(self.date_label)

        layout.addWidget(summary_card)

        layout.addWidget(Eyebrow("Was noch hakt"))
        self.gaps_scroll = QScrollArea()
        self.gaps_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.gaps_scroll.setWidgetResizable(True)
        self.gaps_scroll.setMaximumHeight(48)
        self.gaps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.gaps_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gaps_container = QWidget()
        self.gaps_layout = QHBoxLayout(self.gaps_container)
        self.gaps_layout.setContentsMargins(0, 4, 0, 4)
        self.gaps_layout.setSpacing(6)
        self.gaps_scroll.setWidget(self.gaps_container)
        layout.addWidget(self.gaps_scroll)

        layout.addWidget(Eyebrow("Antworten im Detail"))
        self.details_scroll = QScrollArea()
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.details_container = QWidget()
        self.details_layout = QVBoxLayout(self.details_container)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        self.details_layout.setSpacing(10)
        self.details_scroll.setWidget(self.details_container)
        layout.addWidget(self.details_scroll, stretch=1)

        bottom = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(window.return_from_results)
        bottom.addWidget(back)
        bottom.addStretch(1)
        print_btn = QPushButton("Drucken")
        print_btn.setObjectName("text")
        print_btn.clicked.connect(self._print)
        bottom.addWidget(print_btn)
        practice = QPushButton("Schwächen üben  →")
        practice.setObjectName("primary")
        practice.setToolTip("Zur Analyse-Seite — übe gezielt die schwachen Themen.")
        practice.clicked.connect(window.show_gaps)
        bottom.addWidget(practice)
        layout.addLayout(bottom)

    def show_attempt(self, conn: sqlite3.Connection, attempt_id: int) -> None:
        attempt = conn.execute(
            "SELECT a.*, t.title, t.subject FROM attempts a "
            "JOIN tests t ON t.id = a.test_id WHERE a.id = ?",
            (attempt_id,),
        ).fetchone()

        self.header.setText(attempt["title"])
        note = int(attempt["note"])
        self.note_label.setText(str(note))
        self.note_label.setStyleSheet(f"color: {note_color(note)};")
        self.points_label.setText(
            f"{fmt_num(attempt['points_earned'])} / {attempt['points_possible']}"
        )
        self.percent_label.setText(f"{attempt['percent']:.1f} %")
        self.date_label.setText(fmt_dt(attempt["finished_at"], with_time=True, fallback=""))

        answers = attempts_repo.get_answers(conn, attempt_id)
        self._render_gaps(answers)
        self._render_details(answers)
        self._last_attempt = dict(attempt)
        self._last_answers = [dict(a) for a in answers]

    def _render_gaps(self, answers) -> None:
        clear_layout(self.gaps_layout)

        per_topic_earned: dict[str, float] = {}
        per_topic_possible: dict[str, float] = {}
        for a in answers:
            t = a["topic"]
            per_topic_earned[t] = per_topic_earned.get(t, 0) + float(a["points_earned"])
            per_topic_possible[t] = per_topic_possible.get(t, 0) + float(a["question_points"])

        rows = []
        for topic, earned in per_topic_earned.items():
            possible = per_topic_possible[topic]
            pct = (earned / possible * 100.0) if possible > 0 else 0.0
            rows.append((pct, topic))
        rows.sort(key=lambda r: r[0])

        if not rows:
            empty = QLabel("—")
            empty.setStyleSheet(f"color: {Semantic.FG_SUBTLE}; padding: 8px;")
            self.gaps_layout.addWidget(empty)
            self.gaps_layout.addStretch(1)
            return

        for pct, topic in rows:
            variant = _gap_variant(pct)
            short = topic if len(topic) <= 28 else topic[:25] + "…"
            self.gaps_layout.addWidget(Pill(f"{short} · {pct:.0f}%", variant))
        self.gaps_layout.addStretch(1)

    def _render_details(self, answers) -> None:
        clear_layout(self.details_layout)

        for a in answers:
            container = QFrame()
            container.setObjectName("resultCard")
            box = QVBoxLayout(container)
            box.setSpacing(8)
            box.setContentsMargins(16, 12, 16, 12)

            head_row = QHBoxLayout()
            head_row.setSpacing(8)
            if a["is_correct"]:
                head_row.addWidget(Pill("✓ richtig", "tea"))
            else:
                head_row.addWidget(Pill("✗ falsch", "rose"))
            head_row.addWidget(Pill(a["topic"], "paper"))
            pts_lbl = QLabel(
                f"{fmt_num(a['points_earned'])} / {a['question_points']} Punkte"
            )
            pts_lbl.setStyleSheet(f"color: {Semantic.FG_MUTED}; font-size: 10pt;")
            head_row.addStretch(1)
            head_row.addWidget(pts_lbl)
            box.addLayout(head_row)

            head = QLabel(a["prompt"])
            head.setWordWrap(True)
            head.setStyleSheet(f"color: {Semantic.FG}; font-weight: 600;")
            box.addWidget(head)

            math_src = row_get(a, "prompt_math")
            if math_src:
                mv = MathView()
                mv.render_math(math_src)
                box.addWidget(mv)

            response = json.loads(a["response"])
            your = QLabel(f"<i>Deine Antwort:</i> {_format_response(response)}")
            your.setWordWrap(True)
            your.setStyleSheet(f"color: {Color.PAPER_600};")
            box.addWidget(your)

            if a["explanation"]:
                exp = QLabel(f"<i>Erklärung:</i> {a['explanation']}")
                exp.setWordWrap(True)
                exp.setStyleSheet(f"color: {Semantic.FG_MUTED};")
                box.addWidget(exp)

            self.details_layout.addWidget(container)

        self.details_layout.addStretch(1)

    def _print(self) -> None:
        if not self._last_attempt:
            return
        html = _build_print_html(self._last_attempt, self._last_answers)
        document = QTextDocument()
        document.setHtml(html)

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setDocName("Übungstest-Ergebnis")
        dialog = QPrintPreviewDialog(printer, self)
        dialog.paintRequested.connect(document.print_)
        dialog.exec()


def _gap_variant(percent: float) -> str:
    if percent < GAP_THRESHOLD_RED:
        return "rose"
    if percent < GAP_THRESHOLD_YELLOW:
        return "honey"
    return "tea"


def _format_response(r) -> str:
    if isinstance(r, list):
        return ", ".join(r) if r else "(keine)"
    return str(r) if r else "(leer)"


_PRINT_BODY_FONT = '"Inter", "Segoe UI", system-ui, sans-serif'
_PRINT_DISPLAY_FONT = '"Fraunces", "Iowan Old Style", Georgia, serif'


def _build_print_html(attempt: dict, answers: list[dict]) -> str:
    def esc(x) -> str:
        return html_lib.escape(str(x)) if x is not None else ""

    title = esc(attempt.get("title", "Test"))
    subject = esc(attempt.get("subject", ""))
    note = int(attempt["note"]) if attempt.get("note") is not None else 0
    note_hex = note_color(note)
    points_earned = fmt_num(attempt.get("points_earned", 0))
    points_possible = attempt.get("points_possible", 0)
    percent = attempt.get("percent", 0.0) or 0.0
    finished_dt = fmt_dt(attempt.get("finished_at"), with_time=True, fallback="")

    rows_html = []
    for idx, a in enumerate(answers, start=1):
        is_correct = a.get("is_correct", 0)
        status_icon = "✓" if is_correct else "✗"
        status_color = Color.TEA_700 if is_correct else Color.ROSE_500
        try:
            response = json.loads(a.get("response", "[]"))
        except (TypeError, ValueError):
            response = []
        response_str = esc(_format_response(response))
        prompt = esc(a.get("prompt", ""))
        math_src = a.get("prompt_math") or ""
        math_html = (
            f'<div style="font-family: \'IBM Plex Mono\', monospace; '
            f'background: {Color.PAPER_100}; padding: 4px 8px; margin: 4px 0;">'
            f'{esc(math_src)}</div>'
            if math_src
            else ""
        )
        expl = a.get("explanation") or ""
        expl_html = (
            f'<div style="color: {Semantic.FG_MUTED}; font-style: italic; '
            f'margin-top: 4px;">Erklärung: {esc(expl)}</div>'
            if expl
            else ""
        )
        rows_html.append(
            f"""
            <tr><td style="padding: 10px 0; border-bottom: 1px solid {Semantic.BORDER_SUBTLE};">
              <b style="color: {Semantic.FG};">Frage {idx}</b>
              <span style="color: {status_color}; font-weight: 600;"> &nbsp; {status_icon}
                {fmt_num(a.get('points_earned', 0))} / {a.get('question_points', 0)} P.</span><br>
              <div style="margin: 4px 0; color: {Semantic.FG};">{prompt}</div>
              {math_html}
              <div style="color: {Color.PAPER_600};">Deine Antwort: <i>{response_str}</i></div>
              {expl_html}
            </td></tr>
            """
        )

    return f"""
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: {_PRINT_BODY_FONT}; font-size: 11pt; color: {Semantic.FG};">
  <h1 style="font-family: {_PRINT_DISPLAY_FONT}; font-weight: 500; margin-bottom: 0; color: {Semantic.FG_STRONG};">{title}</h1>
  <div style="color: {Semantic.FG_MUTED}; margin-bottom: 16px;">
    Fach: {subject} &nbsp;·&nbsp; Datum: {finished_dt}
  </div>

  <table style="margin: 12px 0; border-collapse: collapse;">
    <tr>
      <td style="padding-right: 32px; vertical-align: top;">
        <div style="font-family: {_PRINT_DISPLAY_FONT}; font-size: 56pt; font-weight: 500; line-height: 1; color: {note_hex};">{note}</div>
        <div style="color: {Semantic.FG_MUTED};">Note</div>
      </td>
      <td style="vertical-align: top;">
        <div style="font-family: {_PRINT_DISPLAY_FONT}; font-size: 18pt; color: {Semantic.FG};"><b>{points_earned} / {points_possible}</b> Punkte</div>
        <div style="color: {Color.PAPER_600};">{percent:.1f} %</div>
      </td>
    </tr>
  </table>

  <h2 style="font-family: {_PRINT_DISPLAY_FONT}; font-weight: 500; margin-top: 24px; color: {Semantic.FG};">Antworten im Detail</h2>
  <table style="width: 100%; border-collapse: collapse;">
    {''.join(rows_html)}
  </table>
</body>
</html>
"""

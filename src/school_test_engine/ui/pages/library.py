from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
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

from ...storage import attempts_repo, tests_repo
from .._layouts import clear_layout
from .._subjects import subject_variant
from ..design import FontFamily
from ..widgets.clickable_card import ClickableCard
from ..widgets.eyebrow import Eyebrow
from ..widgets.pill import Pill


class LibraryPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._selected_test_id: int | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 30, 40, 30)
        outer.setSpacing(14)

        outer.addWidget(Eyebrow("Übungs-Bibliothek"))
        title = QLabel("Was üben wir heute?")
        title.setObjectName("title")
        title.setFont(QFont(FontFamily.DISPLAY, 30, QFont.Weight.Normal))
        outer.addWidget(title)

        # Resume-Banner
        self.resume_frame = QFrame()
        self.resume_frame.setObjectName("resumeBanner")
        rl = QVBoxLayout(self.resume_frame)
        rl.setContentsMargins(14, 12, 14, 12)
        rl.setSpacing(8)
        rl.addWidget(Eyebrow("Pausiert"))
        self.resume_rows_layout = QVBoxLayout()
        self.resume_rows_layout.setSpacing(6)
        rl.addLayout(self.resume_rows_layout)
        self._resume_rows: list[_ResumeRow] = []
        outer.addWidget(self.resume_frame)

        # Scrollbare Card-Liste
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.scroll.setWidget(self.list_container)
        outer.addWidget(self.scroll, stretch=1)

        # Empty-State-Label
        self.empty_label = QLabel(
            "Noch nichts in der Bibliothek. Über 'Test importieren' im Hauptmenü "
            "die erste JSON-Datei einlesen — die Vorlage dafür findest du in "
            "examples/PROMPT-FOR-AI.md."
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet("color: #6f6757; padding: 24px;")
        outer.addWidget(self.empty_label)
        self.empty_label.hide()


    # ------------------------------------------------------------------

    def reload(self) -> None:
        self._reload_resume_banner()
        self._reload_tests_list()

    def _reload_resume_banner(self) -> None:
        clear_layout(self.resume_rows_layout)
        self._resume_rows = []
        incomplete = attempts_repo.list_incomplete_attempts(
            self.conn, self.window.active_user_id
        )
        for att in incomplete:
            aid = int(att["id"])
            n_questions = self.conn.execute(
                "SELECT COUNT(*) AS n FROM questions WHERE test_id = ?",
                (int(att["test_id"]),),
            ).fetchone()["n"]
            idx = int(att["current_index"] or 0)
            row = _ResumeRow(
                f"<b>{att['test_title']}</b> – Frage {idx + 1} von {n_questions}"
            )
            row.resume_btn.clicked.connect(lambda _=False, _a=aid: self._do_resume(_a))
            row.discard_btn.clicked.connect(lambda _=False, _a=aid: self._discard_resume(_a))
            self.resume_rows_layout.addWidget(row)
            self._resume_rows.append(row)
        self.resume_frame.setVisible(bool(self._resume_rows))

    def _reload_tests_list(self) -> None:
        clear_layout(self.list_layout)

        rows = tests_repo.list_tests(self.conn, self.window.active_user_id)
        if not rows:
            self.empty_label.show()
            self.scroll.hide()
            return
        self.empty_label.hide()
        self.scroll.show()

        for r in rows:
            card = _make_test_card(r, on_pdf=self._export_pdf)
            tid = int(r["id"])
            card.clicked.connect(lambda _tid=tid: self.window.start_test(_tid))
            self.list_layout.addWidget(card)
        self.list_layout.addStretch(1)

    # ------------------------------------------------------------------

    def _do_resume(self, attempt_id: int) -> None:
        self.window.resume_attempt(attempt_id)

    def _export_pdf(self, test_id: int, subject: str) -> None:
        from datetime import date
        from ...pdf_export.test_sheet import export_test_sheet
        from ...pdf_export._common import save_pdf_with_dialog
        html = export_test_sheet(self.conn, test_id)
        default = f"learning-buddy-{subject.lower()}-{date.today().isoformat()}.pdf"
        save_pdf_with_dialog(self, html, default)

    def _discard_resume(self, attempt_id: int) -> None:
        reply = QMessageBox.question(
            self,
            "Versuch verwerfen?",
            "Den pausierten Versuch wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            attempts_repo.discard_attempt(self.conn, attempt_id)
            self.reload()


class _ResumeRow(QWidget):
    """One compact paused-attempt row: label + Verwerfen / Fortsetzen."""

    def __init__(self, text: str):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: #2f2b22;")
        lay.addWidget(self.label, stretch=1)
        self.discard_btn = QPushButton("Verwerfen")
        self.discard_btn.setObjectName("danger")
        lay.addWidget(self.discard_btn)
        self.resume_btn = QPushButton("Fortsetzen →")
        self.resume_btn.setObjectName("primary")
        lay.addWidget(self.resume_btn)


def _make_test_card(row, on_pdf=None) -> ClickableCard:
    card = ClickableCard(object_name="actionCard")
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    card.setMinimumHeight(96)

    layout = QHBoxLayout(card)
    layout.setContentsMargins(20, 14, 20, 14)
    layout.setSpacing(16)

    # Linke Seite: Subject-Pill + Titel + Meta
    left = QVBoxLayout()
    left.setSpacing(6)
    pill_row = QHBoxLayout()
    pill_row.setSpacing(6)
    pill_row.addWidget(Pill(row["subject"], subject_variant(row["subject"])))
    pill_row.addStretch(1)
    left.addLayout(pill_row)

    title = QLabel(row["title"])
    title.setFont(QFont(FontFamily.DISPLAY, 16, QFont.Weight.Medium))
    title.setStyleSheet("color: #1e1b15;")
    title.setWordWrap(True)
    left.addWidget(title)

    n = row["n_questions"] or 0
    pts = row["total_points"] or 0
    meta = QLabel(f"{n} Fragen · {pts} Punkte")
    meta.setStyleSheet("color: #6f6757; font-size: 10pt;")
    left.addWidget(meta)
    layout.addLayout(left, stretch=1)

    # Rechte Seite: optionaler PDF-Button + Clay-Pfeil
    if on_pdf is not None:
        pdf_btn = QPushButton("PDF")
        pdf_btn.setObjectName("text")
        pdf_btn.clicked.connect(
            lambda checked=False, tid=int(row["id"]), subj=row["subject"]: on_pdf(tid, subj)
        )
        layout.addWidget(pdf_btn)

    arrow = QLabel("→")
    arrow.setStyleSheet("color: #c26a3d; font-size: 18pt; font-weight: 600;")
    arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(arrow)

    return card

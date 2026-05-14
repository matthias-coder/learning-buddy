from __future__ import annotations

import json
import sqlite3

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...grading.scoring import score_multi, score_short, score_single
from ...storage import attempts_repo, tests_repo
from ...util.shuffle import new_seed, shuffled
from ..design import FontFamily
from ..widgets.eyebrow import Eyebrow
from ..widgets.math_view import MathView
from ..widgets.pill import Pill


class RunnerPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn

        self._test_row = None
        self._questions: list = []
        self._choice_orders: dict[int, list[str]] = {}
        self._index = 0
        self._attempt_id: int | None = None
        self._seed: int = 0
        self._answers: dict[int, dict] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll, 1)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)

        # Top: Eyebrow "Frage N / M" + Übersicht-Knopf
        top_row = QHBoxLayout()
        self.header_eyebrow = Eyebrow("Frage")
        top_row.addWidget(self.header_eyebrow)
        top_row.addStretch(1)
        self.overview_btn = QPushButton("Übersicht")
        self.overview_btn.clicked.connect(self._goto_overview)
        top_row.addWidget(self.overview_btn)
        layout.addLayout(top_row)

        # Meta-Zeile: Topic-Text + Difficulty-Pill + Punkte-Pill
        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        self.topic_label = QLabel()
        self.topic_label.setStyleSheet("color: #4a4538; font-size: 10pt;")
        meta_row.addWidget(self.topic_label)
        meta_row.addStretch(1)
        self.difficulty_holder = QHBoxLayout()
        self.difficulty_holder.setSpacing(6)
        meta_row.addLayout(self.difficulty_holder)
        layout.addLayout(meta_row)

        self.prompt_label = QLabel()
        self.prompt_label.setWordWrap(True)
        self.prompt_label.setFont(QFont(FontFamily.DISPLAY, 20, QFont.Weight.Medium))
        self.prompt_label.setStyleSheet("color: #1e1b15;")
        layout.addWidget(self.prompt_label)

        self.math_view = MathView()
        self.math_view.hide()
        layout.addWidget(self.math_view)

        self.answer_area = QVBoxLayout()
        wrapper = QWidget()
        wrapper.setLayout(self.answer_area)
        layout.addWidget(wrapper, stretch=1)

        buttons = QHBoxLayout()
        self.back_btn = QPushButton("← Zurück")
        self.back_btn.clicked.connect(self._on_back)
        buttons.addWidget(self.back_btn)

        self.mark_btn = QPushButton("🚩  Markieren")
        self.mark_btn.clicked.connect(self._on_mark_toggle)
        buttons.addWidget(self.mark_btn)

        buttons.addStretch(1)

        self.abort_btn = QPushButton("Pausieren")
        self.abort_btn.clicked.connect(self._abort)
        buttons.addWidget(self.abort_btn)

        self.next_btn = QPushButton("Weiter →")
        self.next_btn.setObjectName("primary")
        self.next_btn.clicked.connect(self._on_next)
        buttons.addWidget(self.next_btn)

        # Navigation row OUTSIDE the scroll area so it stays visible
        nav_container = QWidget()
        nav_container.setLayout(buttons)
        buttons.setContentsMargins(40, 12, 40, 24)
        outer.addWidget(nav_container)

        self._radio_group: QButtonGroup | None = None
        self._checkboxes: list[QCheckBox] = []
        self._line_edit: QLineEdit | None = None

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def start_new(self, test_id: int) -> None:
        self._test_row = tests_repo.get_test(self.conn, test_id)
        raw_questions = tests_repo.get_questions(self.conn, test_id)
        seed = new_seed()
        total_points = sum(q["points"] for q in raw_questions)
        attempt_id = attempts_repo.start_attempt(
            self.conn, test_id, total_points, self.window.active_user_id, shuffle_seed=seed
        )
        self._setup(attempt_id, seed, raw_questions, current_index=0, db_answers={})

    def resume(self, attempt_id: int) -> None:
        attempt = attempts_repo.get_attempt(self.conn, attempt_id)
        if attempt is None:
            return
        self._test_row = tests_repo.get_test(self.conn, int(attempt["test_id"]))
        raw_questions = tests_repo.get_questions(self.conn, int(attempt["test_id"]))
        db_answers = attempts_repo.get_answer_map(self.conn, attempt_id)
        seed = int(attempt["shuffle_seed"] or 0)
        self._setup(
            attempt_id,
            seed,
            raw_questions,
            current_index=int(attempt["current_index"] or 0),
            db_answers=db_answers,
        )

    def jump_to_question(self, index: int) -> None:
        self._save_current_answer()
        self._index = max(0, min(index, len(self._questions) - 1))
        attempts_repo.update_current_index(self.conn, self._attempt_id, self._index)
        self._render_question()

    def get_status_overview(self) -> list[dict]:
        """For the review page: status per question in shuffled order."""
        out = []
        for pos, q in enumerate(self._questions):
            state = self._answers.get(int(q["id"]), {})
            response = state.get("response", [])
            is_answered = bool(response) if isinstance(response, (list, tuple)) else bool(str(response).strip())
            out.append(
                {
                    "index": pos,
                    "prompt": q["prompt"],
                    "topic": q["topic"],
                    "answered": is_answered,
                    "marked": bool(state.get("marked", False)),
                    "points": int(q["points"]),
                }
            )
        return out

    def submit_final(self) -> None:
        from ..main_window import MainWindow  # local import to avoid cycle
        self._save_current_answer()
        total_possible = sum(int(q["points"]) for q in self._questions)
        total_earned = sum(float(a.get("points_earned", 0)) for a in self._answers.values())
        percent = (total_earned / total_possible * 100.0) if total_possible > 0 else 0.0
        schluessel = json.loads(self._test_row["notenschluessel"])
        schluessel_int = {int(k): int(v) for k, v in schluessel.items()}
        from ...grading.notenschluessel import percent_to_note
        note = percent_to_note(percent, schluessel_int)
        attempts_repo.finish_attempt(
            self.conn, self._attempt_id, total_earned, percent, note
        )
        self.window.show_results(self._attempt_id)
        _ = MainWindow  # keep import referenced

    # ------------------------------------------------------------------
    # Setup + rendering
    # ------------------------------------------------------------------

    def _setup(
        self,
        attempt_id: int,
        seed: int,
        raw_questions: list,
        current_index: int,
        db_answers: dict,
    ) -> None:
        self._attempt_id = attempt_id
        self._seed = seed
        self._questions = shuffled(list(raw_questions), seed, salt="questions")
        self._choice_orders = {}
        for q in self._questions:
            payload = json.loads(q["payload"])
            if "choices" in payload:
                ids = [c["id"] for c in payload["choices"]]
                self._choice_orders[int(q["id"])] = shuffled(
                    ids, seed, salt=f"choices:{q['ext_id']}"
                )

        self._answers = {}
        for qid, row in db_answers.items():
            self._answers[int(qid)] = {
                "response": json.loads(row["response"]),
                "marked": bool(row["marked"]),
                "points_earned": float(row["points_earned"]),
                "is_correct": bool(row["is_correct"]),
            }

        self._index = max(0, min(current_index, len(self._questions) - 1))
        self._render_question()

    def _clear_answer_area(self) -> None:
        while self.answer_area.count():
            item = self.answer_area.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._radio_group = None
        self._checkboxes = []
        self._line_edit = None

    def _render_question(self) -> None:
        q = self._questions[self._index]
        n = len(self._questions)
        mark_state = self._answers.get(int(q["id"]), {}).get("marked", False)
        marker = "  🚩" if mark_state else ""
        self.header_eyebrow.setText(f"FRAGE {self._index + 1} VON {n}{marker}")
        self.topic_label.setText(q["topic"])

        # Difficulty + Punkte als Pills neu rendern
        while self.difficulty_holder.count():
            it = self.difficulty_holder.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        diff_variant = {"leicht": "tea", "mittel": "honey", "schwer": "rose"}.get(
            q["difficulty"], "paper"
        )
        self.difficulty_holder.addWidget(Pill(q["difficulty"], diff_variant))
        self.difficulty_holder.addWidget(Pill(f"{q['points']} P.", "paper"))

        self.prompt_label.setText(q["prompt"])

        if q["prompt_math"]:
            self.math_view.render_math(q["prompt_math"])
            self.math_view.show()
        else:
            self.math_view.hide()

        self._clear_answer_area()
        qtype = q["type"]
        payload = json.loads(q["payload"])
        prev_response = self._answers.get(int(q["id"]), {}).get("response", [])

        if qtype == "single_choice":
            self._radio_group = QButtonGroup(self)
            ordered_ids = self._choice_orders[int(q["id"])]
            choices_by_id = {c["id"]: c for c in payload["choices"]}
            for cid in ordered_ids:
                choice = choices_by_id[cid]
                rb = QRadioButton(choice["text"])
                rb.setProperty("choice_id", choice["id"])
                if isinstance(prev_response, list) and choice["id"] in prev_response:
                    rb.setChecked(True)
                self.answer_area.addWidget(rb)
                self._radio_group.addButton(rb)
        elif qtype == "multi_choice":
            hint = QLabel(
                "Mehrere richtige Antworten möglich — falsche Auswahl zieht Punkte ab."
            )
            hint.setStyleSheet("color: #6f6757; font-size: 10pt; font-style: italic;")
            self.answer_area.addWidget(hint)
            ordered_ids = self._choice_orders[int(q["id"])]
            choices_by_id = {c["id"]: c for c in payload["choices"]}
            prev_set = set(prev_response) if isinstance(prev_response, list) else set()
            for cid in ordered_ids:
                choice = choices_by_id[cid]
                cb = QCheckBox(choice["text"])
                cb.setProperty("choice_id", choice["id"])
                if choice["id"] in prev_set:
                    cb.setChecked(True)
                self.answer_area.addWidget(cb)
                self._checkboxes.append(cb)
        elif qtype == "short_answer":
            self._line_edit = QLineEdit()
            self._line_edit.setPlaceholderText("Deine Antwort ...")
            if isinstance(prev_response, str):
                self._line_edit.setText(prev_response)
            self.answer_area.addWidget(self._line_edit)
        else:
            self.answer_area.addWidget(QLabel(f"Unbekannter Fragetyp: {qtype}"))

        self.answer_area.addStretch(1)

        self.back_btn.setEnabled(self._index > 0)
        self.mark_btn.setText("Markierung entfernen" if mark_state else "🚩  Markieren")
        is_last = self._index == len(self._questions) - 1
        self.next_btn.setText("Zur Übersicht →" if is_last else "Weiter →")

    # ------------------------------------------------------------------
    # Answer collection + persistence
    # ------------------------------------------------------------------

    def _collect_response(self) -> list[str] | str:
        q = self._questions[self._index]
        qtype = q["type"]
        if qtype == "single_choice" and self._radio_group is not None:
            for btn in self._radio_group.buttons():
                if btn.isChecked():
                    return [btn.property("choice_id")]
            return []
        if qtype == "multi_choice":
            return [
                cb.property("choice_id") for cb in self._checkboxes if cb.isChecked()
            ]
        if qtype == "short_answer" and self._line_edit is not None:
            return self._line_edit.text()
        return []

    def _score_response(self, q, response) -> tuple[float, bool]:
        payload = json.loads(q["payload"])
        qtype = q["type"]
        if qtype == "single_choice":
            r = score_single(payload["correct"], response if isinstance(response, list) else [], int(q["points"]))
        elif qtype == "multi_choice":
            r = score_multi(
                payload["correct"],
                response if isinstance(response, list) else [],
                int(q["points"]),
                scoring=payload.get("scoring", "partial"),
            )
        elif qtype == "short_answer":
            r = score_short(
                payload["accepted_answers"],
                response if isinstance(response, str) else "",
                int(q["points"]),
                case_sensitive=payload.get("case_sensitive", False),
                trim_whitespace=payload.get("trim_whitespace", True),
            )
        else:
            return 0.0, False
        return r.points_earned, r.is_correct

    def _save_current_answer(self, *, marked_override: bool | None = None) -> None:
        if self._attempt_id is None or not self._questions:
            return
        q = self._questions[self._index]
        qid = int(q["id"])
        response = self._collect_response()
        points, is_correct = self._score_response(q, response)
        prev_marked = self._answers.get(qid, {}).get("marked", False)
        marked = marked_override if marked_override is not None else prev_marked
        self._answers[qid] = {
            "response": response,
            "marked": marked,
            "points_earned": points,
            "is_correct": is_correct,
        }
        attempts_repo.upsert_answer(
            self.conn, self._attempt_id, qid, response, points, is_correct, marked
        )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_back(self) -> None:
        self._save_current_answer()
        if self._index > 0:
            self._index -= 1
            attempts_repo.update_current_index(self.conn, self._attempt_id, self._index)
            self._render_question()

    def _on_next(self) -> None:
        self._save_current_answer()
        if self._index < len(self._questions) - 1:
            self._index += 1
            attempts_repo.update_current_index(self.conn, self._attempt_id, self._index)
            self._render_question()
        else:
            self.window.show_review(self._attempt_id)

    def _on_mark_toggle(self) -> None:
        q = self._questions[self._index]
        qid = int(q["id"])
        new_state = not self._answers.get(qid, {}).get("marked", False)
        self._save_current_answer(marked_override=new_state)
        self._render_question()

    def _goto_overview(self) -> None:
        self._save_current_answer()
        self.window.show_review(self._attempt_id)

    def _abort(self) -> None:
        reply = QMessageBox.question(
            self,
            "Test pausieren?",
            "Pausieren und zurück ins Menü — du kannst später dort weitermachen, "
            "wo du aufgehört hast.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._save_current_answer()
            self.window.show_menu()

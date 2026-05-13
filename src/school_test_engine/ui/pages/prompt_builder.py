from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...prompt_builder.assembler import assemble_prompt
from ...storage import prompt_drafts_repo, users_repo
from .._layouts import row_get
from .._subjects import SUBJECTS_ALL
from ..design import Color, FontFamily, Semantic


class PromptBuilderPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._current_subject = SUBJECTS_ALL[0]
        self._loading = False  # suppress autosave while we populate fields

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(14)

        # Header
        head = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(self.window.show_menu)
        head.addWidget(back)
        head.addStretch(1)

        self.copy_btn = QPushButton("📋 Kopieren")
        self.copy_btn.setObjectName("primary")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        head.addWidget(self.copy_btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {Semantic.ACCENT}; font-size: 10pt;")
        head.addWidget(self._status_lbl)
        outer.addLayout(head)

        eyebrow = QLabel("TEST BAUEN")
        eyebrow.setObjectName("eyebrow")
        outer.addWidget(eyebrow)

        title = QLabel("Übungstest erzeugen")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        # --- Form ---
        form_row1 = QHBoxLayout()
        form_row1.setSpacing(12)
        form_row1.addWidget(QLabel("Fach:"))
        self.subject_combo = QComboBox()
        self.subject_combo.addItems(SUBJECTS_ALL)
        self.subject_combo.setEditable(True)
        self.subject_combo.currentTextChanged.connect(self._on_subject_changed)
        form_row1.addWidget(self.subject_combo)
        form_row1.addSpacing(20)
        form_row1.addWidget(QLabel("Anzahl:"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 50)
        self.count_spin.setValue(10)
        self.count_spin.valueChanged.connect(self._on_changed)
        form_row1.addWidget(self.count_spin)
        form_row1.addStretch(1)
        outer.addLayout(form_row1)

        outer.addWidget(QLabel("Themen (eine Zeile = ein Topic):"))
        self.topics_edit = QPlainTextEdit()
        self.topics_edit.setPlaceholderText("Lineare Gleichungen\nQuadratische Gleichungen")
        self.topics_edit.setMaximumHeight(110)
        self.topics_edit.textChanged.connect(self._on_changed)
        outer.addWidget(self.topics_edit)

        # Distribution row
        dist_row = QHBoxLayout()
        dist_row.setSpacing(10)
        dist_row.addWidget(QLabel("Schwierigkeit:"))
        self.dist_group = QButtonGroup(self)
        self.dist_auto = QRadioButton("auto (40/40/20)")
        self.dist_auto.setChecked(True)
        self.dist_auto.toggled.connect(self._on_dist_mode_changed)
        self.dist_group.addButton(self.dist_auto)
        dist_row.addWidget(self.dist_auto)

        self.dist_manual = QRadioButton("manuell:")
        self.dist_manual.toggled.connect(self._on_dist_mode_changed)
        self.dist_group.addButton(self.dist_manual)
        dist_row.addWidget(self.dist_manual)

        self.leicht_spin = QSpinBox()
        self.leicht_spin.setRange(0, 50); self.leicht_spin.setValue(4)
        self.leicht_spin.valueChanged.connect(self._on_changed)
        dist_row.addWidget(QLabel("L:")); dist_row.addWidget(self.leicht_spin)

        self.mittel_spin = QSpinBox()
        self.mittel_spin.setRange(0, 50); self.mittel_spin.setValue(4)
        self.mittel_spin.valueChanged.connect(self._on_changed)
        dist_row.addWidget(QLabel("M:")); dist_row.addWidget(self.mittel_spin)

        self.schwer_spin = QSpinBox()
        self.schwer_spin.setRange(0, 50); self.schwer_spin.setValue(2)
        self.schwer_spin.valueChanged.connect(self._on_changed)
        dist_row.addWidget(QLabel("S:")); dist_row.addWidget(self.schwer_spin)

        dist_row.addStretch(1)
        outer.addLayout(dist_row)

        self.dist_warn = QLabel("")
        self.dist_warn.setStyleSheet("color: #7e3b39; font-size: 10pt;")
        outer.addWidget(self.dist_warn)

        # Style-Briefing preview row
        style_row = QHBoxLayout()
        self.style_label = QLabel("Stil-Briefing (aus Profil): —")
        self.style_label.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
        self.style_label.setWordWrap(True)
        style_row.addWidget(self.style_label, 1)
        edit_link = QPushButton("Profil bearbeiten")
        edit_link.setObjectName("text")
        edit_link.clicked.connect(lambda: self.window.show_profile_manager("menu"))
        style_row.addWidget(edit_link)
        outer.addLayout(style_row)

        # --- Output ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #d8cdb8;")
        outer.addWidget(sep)

        outer.addWidget(QLabel("🪄 Generierter Prompt:"))
        self.output_view = QPlainTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setObjectName("promptOutput")
        outer.addWidget(self.output_view, 1)

        self._set_manual_enabled(False)
        self._update_status_clear_timer = QTimer(self)
        self._update_status_clear_timer.setSingleShot(True)
        self._update_status_clear_timer.timeout.connect(lambda: self._status_lbl.setText(""))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reload(self) -> None:
        self.show_for(subject=None, topics=None)

    def show_for(self, subject: str | None = None, topics: list[str] | None = None) -> None:
        uid = self.window.active_user_id
        if uid is None:
            return
        self._loading = True
        try:
            user = users_repo.get_user(self.conn, uid)
            briefing = row_get(user, "ai_style_briefing") if user else None
            if briefing:
                preview = briefing.splitlines()[0]
                if len(preview) > 80:
                    preview = preview[:77] + "…"
                self.style_label.setText(f'Stil-Briefing (aus Profil): "{preview}"')
            else:
                self.style_label.setText(
                    "Stil-Briefing (aus Profil): — (Hinweis im Profil hinterlegen für persönlichen KI-Stil)"
                )

            # Decide subject
            target_subject = subject or self._current_subject
            idx = self.subject_combo.findText(target_subject)
            if idx >= 0:
                self.subject_combo.setCurrentIndex(idx)
            else:
                self.subject_combo.setEditText(target_subject)
            self._current_subject = target_subject

            # Load draft for the subject
            draft = prompt_drafts_repo.get(self.conn, uid, target_subject)

            # Topics: explicit override wins, then draft, else empty
            if topics is not None:
                self.topics_edit.setPlainText("\n".join(topics))
            elif draft and draft["last_topic"]:
                self.topics_edit.setPlainText(draft["last_topic"])
            else:
                self.topics_edit.setPlainText("")

            # Count
            self.count_spin.setValue(draft["last_count"] if draft else 10)

            # Distribution
            dist = draft["last_dist"] if draft else "auto"
            if dist == "auto":
                self.dist_auto.setChecked(True)
                self._set_manual_enabled(False)
            else:
                # manuell:L-M-S
                payload = dist.split(":", 1)[1] if ":" in dist else ""
                parts = payload.split("-")
                if len(parts) == 3:
                    try:
                        l, m, s = (int(p) for p in parts)
                        self.leicht_spin.setValue(l)
                        self.mittel_spin.setValue(m)
                        self.schwer_spin.setValue(s)
                    except ValueError:
                        pass
                self.dist_manual.setChecked(True)
                self._set_manual_enabled(True)
        finally:
            self._loading = False
        self._rebuild_prompt()

    def hideEvent(self, event) -> None:
        self._autosave()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _current_dist_string(self) -> str:
        if self.dist_auto.isChecked():
            return "auto"
        return f"manuell:{self.leicht_spin.value()}-{self.mittel_spin.value()}-{self.schwer_spin.value()}"

    def _current_topics(self) -> list[str]:
        return [t.strip() for t in self.topics_edit.toPlainText().splitlines() if t.strip()]

    def _set_manual_enabled(self, enabled: bool) -> None:
        for w in (self.leicht_spin, self.mittel_spin, self.schwer_spin):
            w.setEnabled(enabled)

    def _validate_distribution(self) -> bool:
        """Return True if current distribution is consistent with count."""
        if self.dist_auto.isChecked():
            self.dist_warn.setText("")
            return True
        total = self.leicht_spin.value() + self.mittel_spin.value() + self.schwer_spin.value()
        if total != self.count_spin.value():
            self.dist_warn.setText(
                f"Summe {total} ≠ Anzahl {self.count_spin.value()} — passe an"
            )
            return False
        self.dist_warn.setText("")
        return True

    # ------------------------------------------------------------------
    # Live build
    # ------------------------------------------------------------------

    def _rebuild_prompt(self) -> None:
        uid = self.window.active_user_id
        briefing = None
        if uid is not None:
            user = users_repo.get_user(self.conn, uid)
            if user is not None:
                briefing = row_get(user, "ai_style_briefing")

        ok = self._validate_distribution()
        dist_str = self._current_dist_string() if ok else "manuell:inkonsistent"
        out = assemble_prompt(
            subject=self.subject_combo.currentText().strip() or SUBJECTS_ALL[0],
            topics=self._current_topics(),
            count=self.count_spin.value(),
            distribution=dist_str,
            style_briefing=briefing,
        )
        self.output_view.setPlainText(out)
        self.copy_btn.setEnabled(ok)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _on_subject_changed(self, text: str) -> None:
        if self._loading:
            return
        # Save current draft before switching
        self._autosave()
        # Reload with new subject
        self._current_subject = text.strip() or SUBJECTS_ALL[0]
        self.show_for(subject=self._current_subject)

    def _on_dist_mode_changed(self, _checked: bool) -> None:
        if self._loading:
            return
        self._set_manual_enabled(self.dist_manual.isChecked())
        self._rebuild_prompt()

    def _on_changed(self, *_args) -> None:
        if self._loading:
            return
        self._rebuild_prompt()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _autosave(self) -> None:
        uid = self.window.active_user_id
        if uid is None:
            return
        subject = self.subject_combo.currentText().strip()
        if not subject:
            return
        topics_text = "\n".join(self._current_topics())
        prompt_drafts_repo.upsert(
            self.conn, uid, subject,
            last_topic=topics_text or None,
            last_count=self.count_spin.value(),
            last_dist=self._current_dist_string(),
        )

    def _copy_to_clipboard(self) -> None:
        self._autosave()
        QApplication.clipboard().setText(self.output_view.toPlainText())
        self._status_lbl.setText("Kopiert ✓")
        self._update_status_clear_timer.start(2000)

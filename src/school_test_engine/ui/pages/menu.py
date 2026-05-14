from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...cockpit import service as cockpit
from ...daily import builder as daily_builder
from ...daily import streak as daily_streak
from ...storage import users_repo, events_repo, assessments_repo, daily_sessions_repo
from .._layouts import row_get
from ..design import Color, FontFamily, Semantic
from ..dialogs.assessment_dialog import AssessmentDialog
from ..dialogs.event_dialog import EventDialog
from ..responsive import is_narrow
from ..widgets.avatar_badge import round_pixmap
from ..widgets.clickable_card import ClickableCard
from ..widgets.daily_card import DailyCard
from ..widgets.exam_card import ExamCard
from ..widgets.hamburger_menu import HamburgerMenu


LOGOMARK_PATH = Path(__file__).resolve().parents[3].parent / "assets" / "logomark.svg"


class MenuPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

        outer = QVBoxLayout(self)
        outer.setSpacing(20)
        outer.setContentsMargins(48, 36, 48, 36)
        self._outer = outer

        # Top bar
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        if LOGOMARK_PATH.exists():
            logo = QSvgWidget(str(LOGOMARK_PATH))
            logo.setFixedSize(QSize(36, 36))
            top_row.addWidget(logo)
        wordmark = QLabel("die <i>Kessler</i> Übungstests")
        wordmark.setFont(QFont(FontFamily.DISPLAY, 14, QFont.Weight.Normal))
        wordmark.setStyleSheet(f"color: {Color.PAPER_700};")
        top_row.addWidget(wordmark)
        top_row.addStretch(1)

        # New top-bar icon buttons
        builder_btn = QPushButton("📝 Test bauen")
        builder_btn.setObjectName("topBarAction")
        builder_btn.clicked.connect(lambda: self.window.show_prompt_builder())
        top_row.addWidget(builder_btn)

        events_btn = QPushButton("📅 Termine")
        events_btn.setObjectName("topBarAction")
        events_btn.clicked.connect(self.window.show_events)
        top_row.addWidget(events_btn)

        grades_btn = QPushButton("📊 Noten")
        grades_btn.setObjectName("topBarAction")
        grades_btn.clicked.connect(self.window.show_grades)
        top_row.addWidget(grades_btn)

        # Phase 11: store action-button refs for narrow-mode toggling
        self._top_bar_actions = [builder_btn, events_btn, grades_btn]

        # Hamburger fallback (hidden in wide mode)
        self._hamburger = HamburgerMenu()
        self._hamburger.add_action("📝 Test bauen", lambda: self.window.show_prompt_builder())
        self._hamburger.add_action("📅 Termine", self.window.show_events)
        self._hamburger.add_action("📊 Noten", self.window.show_grades)
        self._hamburger.setVisible(False)  # default: wide-mode
        top_row.addWidget(self._hamburger)

        self.chip = _ProfileChip()
        self.chip.switch_clicked.connect(self._switch_profile)
        top_row.addWidget(self.chip)
        outer.addLayout(top_row)

        # Eyebrow + Greeting
        self.eyebrow = QLabel("HEUTE")
        self.eyebrow.setObjectName("eyebrow")
        self.eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.eyebrow)

        self.greeting = QLabel("Hallo")
        self.greeting.setObjectName("title")
        self.greeting.setFont(QFont(FontFamily.DISPLAY, 36, QFont.Weight.Normal))
        self.greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.greeting)
        outer.addSpacing(12)

        # Dynamic content area — rebuilt on reload()
        self._dynamic_container = QWidget()
        self._dynamic_layout = QVBoxLayout(self._dynamic_container)
        self._dynamic_layout.setSpacing(16)
        self._dynamic_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._dynamic_container)
        outer.addStretch(1)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reload(self) -> None:
        uid = self.window.active_user_id
        if uid is None:
            return
        user = users_repo.get_user(self.window.conn, uid)
        if user is None:
            return
        self.chip.set_user(user["avatar"], user["name"], row_get(user, "avatar_image"))
        self.greeting.setText(f"Hallo, {user['name']}")

        # Rebuild dynamic content
        while self._dynamic_layout.count():
            item = self._dynamic_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        events = cockpit.upcoming_events_for_menu(self.window.conn, uid, today=date.today())
        if events:
            self._build_ka_hero(events)
            self._build_compact_grid()
        else:
            self._build_empty_state()
            self._build_full_grid()

    def _switch_profile(self) -> None:
        self.window.show_profile_picker()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        narrow = is_narrow(self)
        # Toggle top-bar buttons
        for btn in self._top_bar_actions:
            btn.setVisible(not narrow)
        self._hamburger.setVisible(narrow)
        # Toggle the action-grid: rebuild dynamic content so columns change
        # Note: dynamic_layout is rebuilt in reload(); we trigger reload only if
        # the narrow-state actually changed since the last call.
        if getattr(self, "_last_narrow_state", None) != narrow:
            self._last_narrow_state = narrow
            self.reload()

    # ------------------------------------------------------------------
    # Layout variants
    # ------------------------------------------------------------------

    def _build_ka_hero(self, events) -> None:
        eyebrow = QLabel("NÄCHSTE KLASSENARBEITEN")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dynamic_layout.addWidget(eyebrow)

        strip = QHBoxLayout()
        strip.setSpacing(14)
        strip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for ev in events:
            card = ExamCard(ev)
            card.practice_clicked.connect(self._on_practice_clicked)
            card.enter_grade_clicked.connect(self._on_enter_grade)
            card.edit_clicked.connect(self._on_edit_event)
            strip.addWidget(card)
        wrap = QWidget()
        wrap.setLayout(strip)
        self._dynamic_layout.addWidget(wrap)

    def _build_empty_state(self) -> None:
        f = QFrame()
        f.setObjectName("emptyEvents")
        h = QHBoxLayout(f)
        h.setContentsMargins(20, 16, 20, 16)
        h.setSpacing(12)
        lbl = QLabel("Keine Klassenarbeiten geplant.")
        lbl.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 11pt;")
        h.addWidget(lbl)
        h.addStretch(1)
        btn = QPushButton("+ Termin")
        btn.setObjectName("text")
        btn.clicked.connect(self._on_add_event_from_menu)
        h.addWidget(btn)
        self._dynamic_layout.addWidget(f)

    def _build_compact_grid(self) -> None:
        """Quick-access row when KAs are present — single row of 4 small tiles."""
        grid_wrap = QHBoxLayout()
        grid_wrap.addStretch(1)
        container = QWidget()
        container.setMaximumWidth(820)
        narrow = is_narrow(self)
        row = QVBoxLayout(container) if narrow else QHBoxLayout(container)
        row.setSpacing(12)
        row.setContentsMargins(0, 0, 0, 0)

        items = [
            ("LIBRARY", "Bibliothek", self.window.show_library),
            ("HAKT", "Lücken", self.window.show_gaps),
            ("RÜCKBLICK", "Verlauf", self.window.show_history),
            ("IMPORT", "Test importieren", self.window.show_import),
        ]
        for eyebrow_text, title, action in items:
            tile = _make_compact_tile(eyebrow_text, title)
            tile.clicked.connect(action)
            row.addWidget(tile)
        grid_wrap.addWidget(container)
        grid_wrap.addStretch(1)
        self._dynamic_layout.addLayout(grid_wrap)

        # Phase 10: Daily-5 card
        uid = self.window.active_user_id
        if uid is not None:
            state, streak, last_grade = self._compute_daily_state(uid)
            card = DailyCard(state, streak, last_grade=last_grade)
            card.practice_clicked.connect(self.window.start_daily_five)
            self._dynamic_layout.addWidget(card)

    def _build_full_grid(self) -> None:
        grid_wrap = QHBoxLayout()
        grid_wrap.addStretch(1)
        grid_container = QWidget()
        grid_container.setMaximumWidth(820)
        grid = QGridLayout(grid_container)
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)

        start = _make_action_card("ÜBEN", "Test starten", "Wähle einen Test aus deiner Bibliothek")
        start.clicked.connect(self.window.show_library)

        imp = _make_action_card("AUFGABEN", "Test importieren", "Neue Fragen aus einer JSON-Datei einlesen")
        imp.clicked.connect(self.window.show_import)

        gaps = _make_action_card("ANALYSE", "Was noch hakt", "Themen sortiert nach Schwäche — mit Üben-Knopf")
        gaps.clicked.connect(self.window.show_gaps)

        hist = _make_action_card("RÜCKBLICK", "Bisherige Versuche", "Alle Tests mit Note und Datum")
        hist.clicked.connect(self.window.show_history)

        narrow = is_narrow(self)
        cols = 1 if narrow else 2
        cards = [start, imp, gaps, hist]
        for idx, card in enumerate(cards):
            row, col = divmod(idx, cols)
            grid.addWidget(card, row, col)

        grid_wrap.addWidget(grid_container)
        grid_wrap.addStretch(1)
        self._dynamic_layout.addLayout(grid_wrap)

        # Phase 10: Daily-5 card
        uid = self.window.active_user_id
        if uid is not None:
            state, streak, last_grade = self._compute_daily_state(uid)
            card = DailyCard(state, streak, last_grade=last_grade)
            card.practice_clicked.connect(self.window.start_daily_five)
            self._dynamic_layout.addWidget(card)

    # ------------------------------------------------------------------
    # Daily-5 helpers
    # ------------------------------------------------------------------

    def _compute_daily_state(self, uid: int) -> tuple[str, int, int | None]:
        """Return (state, streak, last_grade)."""
        today = date.today()
        today_iso = today.isoformat()

        streak = daily_streak.current_streak(self.window.conn, uid, today)

        session = daily_sessions_repo.get_for_today(self.window.conn, uid, today_iso)
        if session is not None and session["completed_at"] is not None:
            # Done — look up the attempt's grade
            attempt_row = self.window.conn.execute(
                "SELECT note FROM attempts WHERE id = ?",
                (session["attempt_id"],),
            ).fetchone() if session["attempt_id"] else None
            last_grade = attempt_row["note"] if attempt_row else None
            return ("done", streak, last_grade)

        if not daily_builder.has_enough_questions(self.window.conn, uid):
            return ("no_library", streak, None)

        return ("due", streak, None)

    # ------------------------------------------------------------------
    # ExamCard actions
    # ------------------------------------------------------------------

    def _on_practice_clicked(self, event_id: int) -> None:
        import json
        ev = events_repo.get(self.window.conn, event_id)
        if ev is None:
            return
        topics = json.loads(ev["topics"] or "[]")
        self.window.show_prompt_builder(subject=ev["subject"], topics=topics)

    def _on_enter_grade(self, event_id: int) -> None:
        from PySide6.QtWidgets import QDialog
        ev = events_repo.get(self.window.conn, event_id)
        if ev is None:
            return
        dlg = AssessmentDialog(
            self, prefill_subject=ev["subject"], prefill_event_id=event_id
        )
        # Prefill date with KA date
        from PySide6.QtCore import QDate
        d = ev["event_date"]
        dlg.date_edit.setDate(QDate(int(d[:4]), int(d[5:7]), int(d[8:10])))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.data()
            assessments_repo.create(
                self.window.conn, self.window.active_user_id,
                data["subject"], data["category"], data["assessment_date"],
                grade=data["grade"], points=data["points"], max_points=data["max_points"],
                note=data["note"], scheduled_event_id=event_id,
            )
            self.reload()

    def _on_edit_event(self, event_id: int) -> None:
        from PySide6.QtWidgets import QDialog
        ev = events_repo.get(self.window.conn, event_id)
        if ev is None:
            return
        dlg = EventDialog(self, initial=ev)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.is_delete():
            events_repo.delete(self.window.conn, event_id)
        else:
            data = dlg.data()
            events_repo.update(
                self.window.conn, event_id,
                subject=data["subject"], kind=data["kind"], event_date=data["event_date"],
                topics=data["topics"], note=data["note"],
            )
        self.reload()

    def _on_add_event_from_menu(self) -> None:
        from PySide6.QtWidgets import QDialog
        dlg = EventDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.data()
            events_repo.create(
                self.window.conn, self.window.active_user_id,
                data["subject"], data["kind"], data["event_date"],
                topics=data["topics"], note=data["note"],
            )
            self.reload()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


class _ProfileChip(QFrame):
    """Kompakte Anzeige des aktiven Profils mit 'Wechseln'-Button."""

    switch_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("profileChip")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 4, 6, 4)
        h.setSpacing(8)

        self.avatar = QLabel("👤")
        self.avatar.setObjectName("profileChipAvatar")
        self.avatar.setFixedSize(28, 28)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self.avatar)

        self.name = QLabel("…")
        self.name.setObjectName("profileChipName")
        h.addWidget(self.name)

        switch = QPushButton("Wechseln")
        switch.setObjectName("text")
        switch.clicked.connect(self.switch_clicked)
        h.addWidget(switch)

    def set_user(self, avatar: str, name: str, image_bytes: bytes | None = None) -> None:
        if image_bytes:
            pm = QPixmap()
            if pm.loadFromData(image_bytes):
                self.avatar.setPixmap(round_pixmap(pm, 28))
                self.avatar.setText("")
                self.name.setText(name)
                return
        self.avatar.clear()
        self.avatar.setText(avatar)
        self.name.setText(name)


def _make_action_card(eyebrow_text: str, title_text: str, description: str) -> ClickableCard:
    card = ClickableCard(object_name="actionCard")
    card.setMinimumSize(340, 150)
    card.setMaximumHeight(180)
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(22, 18, 22, 16)
    layout.setSpacing(6)
    eyebrow = QLabel(eyebrow_text)
    eyebrow.setObjectName("eyebrow")
    layout.addWidget(eyebrow)
    title = QLabel(title_text)
    title.setObjectName("h2")
    title.setFont(QFont(FontFamily.DISPLAY, 18, QFont.Weight.Medium))
    title.setWordWrap(True)
    title.setStyleSheet(f"color: {Semantic.FG};")
    layout.addWidget(title)
    desc = QLabel(description)
    desc.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
    desc.setWordWrap(True)
    layout.addWidget(desc)
    layout.addStretch(1)
    arrow_row = QHBoxLayout()
    arrow_row.addStretch(1)
    arrow = QLabel("→")
    arrow.setStyleSheet(f"color: {Semantic.ACCENT}; font-size: 16pt; font-weight: 600;")
    arrow_row.addWidget(arrow)
    layout.addLayout(arrow_row)
    return card


def _make_compact_tile(eyebrow_text: str, title_text: str) -> ClickableCard:
    card = ClickableCard(object_name="compactTile")
    card.setMinimumSize(180, 88)
    card.setMaximumHeight(100)
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    v = QVBoxLayout(card)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(2)
    eyebrow = QLabel(eyebrow_text)
    eyebrow.setObjectName("eyebrow")
    v.addWidget(eyebrow)
    title = QLabel(title_text)
    title.setFont(QFont(FontFamily.DISPLAY, 14, QFont.Weight.Medium))
    title.setStyleSheet(f"color: {Semantic.FG};")
    v.addWidget(title)
    v.addStretch(1)
    return card

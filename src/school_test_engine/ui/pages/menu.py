from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...cockpit import service as cockpit
from ...daily import builder as daily_builder
from ...daily import streak as daily_streak
from ...storage import users_repo, events_repo, daily_sessions_repo
from .._layouts import row_get
from ..design import Color, FontFamily, Semantic
from ..responsive import is_narrow
from ..widgets.action_card import make_action_card
from ..widgets.avatar_badge import AvatarBadge
from ..widgets.clickable_card import ClickableCard
from ..widgets.daily_card import DailyCard
from ..widgets.exam_card import ExamCard


LOGOMARK_PATH = Path(__file__).resolve().parents[3].parent / "assets" / "logomark.svg"


class MenuPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

        outer = QVBoxLayout(self)
        outer.setSpacing(20)
        outer.setContentsMargins(48, 36, 48, 36)
        self._outer = outer

        # Top bar — Logo+Wordmark is itself the navigation trigger
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        self._logo_menu = _LogoMenuButton()
        self._logo_menu.add_action("Test erstellen", self.window.show_test_create)
        self._logo_menu.add_action("Termine", self.window.show_events)
        self._logo_menu.add_action("Noten", self.window.show_grades)
        top_row.addWidget(self._logo_menu)
        top_row.addStretch(1)

        self.chip = _ProfileChip()
        self.chip.switch_clicked.connect(self._switch_profile)
        top_row.addWidget(self.chip)
        outer.addLayout(top_row)

        if hasattr(window, "events_synced"):
            window.events_synced.connect(self.reload)

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
        footer = QLabel("designed by Matthias")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #a89e89; font-size: 9pt;")
        outer.addWidget(footer)

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

        # Rebuild dynamic content — recursive clear so nested QHBoxLayouts/QGridLayouts
        # don't leak their child widgets across reloads (Phase 12.1 fix).
        self._clear_layout_recursive(self._dynamic_layout)

        events = cockpit.upcoming_events_for_menu(self.window.conn, uid, today=date.today())
        if events:
            self._build_ka_hero(events)
            self._build_compact_grid()
        else:
            self._build_empty_state()
            self._build_full_grid()

    @staticmethod
    def _clear_layout_recursive(layout) -> None:
        """Recursively detach + delete every widget inside a layout (including
        nested layouts). `setParent(None)` removes the widget from its parent's
        children list IMMEDIATELY (so it stops being rendered + counted), then
        `deleteLater` schedules actual destruction. Without setParent(None),
        widgets stay visible as orphans of the original container until the
        event loop processes deletions — leading to ghosted duplicates when
        reload() runs multiple times quickly (e.g. during initial resize events)."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
                continue
            child_layout = item.layout()
            if child_layout is not None:
                MenuPage._clear_layout_recursive(child_layout)
                child_layout.deleteLater()

    def _switch_profile(self) -> None:
        self.window.show_profile_picker()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        narrow = is_narrow(self)
        # Rebuild dynamic content when narrow-state flips so the action-grid
        # changes column count.
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
            card.study_plan_clicked.connect(self._on_export_study_plan)
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
            state, streak = self._compute_daily_state(uid)
            card = DailyCard(state, streak)
            card.practice_clicked.connect(self.window.start_daily_five)
            self._dynamic_layout.addWidget(card)

    def _build_full_grid(self) -> None:
        grid_wrap = QHBoxLayout()
        grid_wrap.addStretch(1)
        grid_container = QWidget()
        # Phase 12.2 fix: same pattern as profile-picker — without setMinimumWidth
        # the container shrinks to QGridLayout's natural minimumSize (sum of card
        # min sizes), making cards look left-shifted instead of centered.
        grid_container.setMinimumWidth(820)
        grid_container.setMaximumWidth(820)
        grid = QGridLayout(grid_container)
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)

        start = make_action_card("ÜBEN", "Test starten", "Wähle einen Test aus deiner Bibliothek")
        start.clicked.connect(self.window.show_library)

        gaps = make_action_card("ANALYSE", "Was noch hakt", "Themen sortiert nach Schwäche — mit Üben-Knopf")
        gaps.clicked.connect(self.window.show_gaps)

        hist = make_action_card("RÜCKBLICK", "Bisherige Versuche", "Alle Tests mit Note und Datum")
        hist.clicked.connect(self.window.show_history)

        narrow = is_narrow(self)
        cols = 1 if narrow else 2
        cards = [start, gaps, hist]
        for idx, card in enumerate(cards):
            row, col = divmod(idx, cols)
            grid.addWidget(card, row, col)

        grid_wrap.addWidget(grid_container)
        grid_wrap.addStretch(1)
        self._dynamic_layout.addLayout(grid_wrap)

        # Phase 10: Daily-5 card
        uid = self.window.active_user_id
        if uid is not None:
            state, streak = self._compute_daily_state(uid)
            card = DailyCard(state, streak)
            card.practice_clicked.connect(self.window.start_daily_five)
            self._dynamic_layout.addWidget(card)

    # ------------------------------------------------------------------
    # Daily-5 helpers
    # ------------------------------------------------------------------

    def _compute_daily_state(self, uid: int) -> tuple[str, int]:
        """Return (state, streak)."""
        today = date.today()
        today_iso = today.isoformat()

        streak = daily_streak.current_streak(self.window.conn, uid, today)

        session = daily_sessions_repo.get_for_today(self.window.conn, uid, today_iso)
        if session is not None and session["completed_at"] is not None:
            return ("done", streak)

        if not daily_builder.has_enough_questions(self.window.conn, uid):
            return ("no_library", streak)

        return ("due", streak)

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
        ev = events_repo.get(self.window.conn, event_id)
        if ev is None:
            return
        self.window.show_assessment_edit(
            assessment_id=None,
            return_to="menu",
            prefill_subject=ev["subject"],
            prefill_event_id=event_id,
        )

    def _on_edit_event(self, event_id: int) -> None:
        self.window.show_event_edit(event_id=event_id, return_to="menu")

    def _on_export_study_plan(self, event_id: int) -> None:
        from datetime import date
        from ...pdf_export.study_plan import export_study_plan
        from ...pdf_export._common import save_pdf_with_dialog
        html = export_study_plan(self.window.conn, event_id)
        default = f"learning-buddy-lernplan-{date.today().isoformat()}.pdf"
        save_pdf_with_dialog(self, html, default)

    def _on_add_event_from_menu(self) -> None:
        self.window.show_event_edit(event_id=None, return_to="menu")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


class _LogoMenuButton(QFrame):
    """Logo + 'Learning Buddy' wordmark + caret — clicking opens the navigation menu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logoMenu")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._menu = QMenu(self)

        h = QHBoxLayout(self)
        h.setContentsMargins(6, 4, 12, 4)
        h.setSpacing(8)
        if LOGOMARK_PATH.exists():
            logo = QSvgWidget(str(LOGOMARK_PATH))
            logo.setFixedSize(QSize(32, 32))
            h.addWidget(logo)
        wm = QLabel("Learning Buddy")
        wm.setFont(QFont(FontFamily.DISPLAY, 14, QFont.Weight.Normal))
        wm.setStyleSheet(f"color: {Color.PAPER_700};")
        h.addWidget(wm)
        caret = QLabel("▾")
        caret.setStyleSheet(f"color: {Color.PAPER_500}; font-size: 11pt;")
        h.addWidget(caret)

    def add_action(self, label: str, callback) -> None:
        action = self._menu.addAction(label)
        action.triggered.connect(callback)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._menu.popup(self.mapToGlobal(self.rect().bottomLeft()))
        super().mousePressEvent(event)


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

        self.avatar = AvatarBadge(emoji="ignored", image_bytes=None, diameter=28)
        self.avatar.setObjectName("profileChipAvatar")
        h.addWidget(self.avatar)

        self.name = QLabel("…")
        self.name.setObjectName("profileChipName")
        h.addWidget(self.name)

        switch = QPushButton("Wechseln")
        switch.setObjectName("text")
        switch.clicked.connect(self.switch_clicked)
        h.addWidget(switch)

    def set_user(self, avatar: str, name: str, image_bytes: bytes | None = None) -> None:
        self.avatar.set_avatar(emoji="ignored", image_bytes=image_bytes)
        self.name.setText(name)


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

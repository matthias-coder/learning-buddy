from __future__ import annotations

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

from ...storage import users_repo
from .._layouts import row_get
from ..design import Color, FontFamily, Semantic
from ..widgets.avatar_badge import round_pixmap
from ..widgets.clickable_card import ClickableCard


LOGOMARK_PATH = Path(__file__).resolve().parents[3].parent / "assets" / "logomark.svg"


class MenuPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

        outer = QVBoxLayout(self)
        outer.setSpacing(20)
        outer.setContentsMargins(48, 36, 48, 36)

        # Top-Bar: Logomark + Wordmark links, Profil-Chip rechts
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
        self.chip = _ProfileChip()
        self.chip.switch_clicked.connect(self._switch_profile)
        top_row.addWidget(self.chip)
        outer.addLayout(top_row)

        # Eyebrow + Begrüßung
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

        # 2×2 Card-Grid in zentriertem Container
        grid_wrap = QHBoxLayout()
        grid_wrap.addStretch(1)
        grid_container = QWidget()
        grid_container.setMaximumWidth(820)
        grid = QGridLayout(grid_container)
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)

        start = _make_action_card("ÜBEN", "Test starten", "Wähle einen Test aus deiner Bibliothek")
        start.clicked.connect(window.show_library)
        grid.addWidget(start, 0, 0)

        imp = _make_action_card("AUFGABEN", "Test importieren", "Neue Fragen aus einer JSON-Datei einlesen")
        imp.clicked.connect(window.show_import)
        grid.addWidget(imp, 0, 1)

        gaps = _make_action_card("ANALYSE", "Was noch hakt", "Themen sortiert nach Schwäche — mit Üben-Knopf")
        gaps.clicked.connect(window.show_gaps)
        grid.addWidget(gaps, 1, 0)

        hist = _make_action_card("RÜCKBLICK", "Bisherige Versuche", "Alle Tests mit Note und Datum")
        hist.clicked.connect(window.show_history)
        grid.addWidget(hist, 1, 1)

        grid_wrap.addWidget(grid_container)
        grid_wrap.addStretch(1)
        outer.addLayout(grid_wrap)

        outer.addStretch(1)

    def reload(self) -> None:
        uid = self.window.active_user_id
        if uid is None:
            return
        user = users_repo.get_user(self.window.conn, uid)
        if user is None:
            return
        self.chip.set_user(user["avatar"], user["name"], row_get(user, "avatar_image"))
        self.greeting.setText(f"Hallo, {user['name']}")

    def _switch_profile(self) -> None:
        self.window.show_profile_picker()


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
    """Action-Card mit Eyebrow + Fraunces-Titel + Beschreibung + Pfeil."""
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

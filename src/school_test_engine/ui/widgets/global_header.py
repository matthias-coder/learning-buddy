"""Global top-bar shown on every page except the Profile-Picker.

Houses the Learning-Buddy logo + dropdown menu (Test erstellen / Termine / Noten
/ Profil wechseln) on the left, and the active-profile chip (avatar + name) on
the right. Visibility is bound to active_user_id by MainWindow.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QWidget,
)

from ..design import Color, FontFamily
from .avatar_badge import AvatarBadge


LOGOMARK_PATH = Path(__file__).resolve().parents[3].parent / "assets" / "logomark.svg"


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

    def add_separator(self) -> None:
        self._menu.addSeparator()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._menu.popup(self.mapToGlobal(self.rect().bottomLeft()))
        super().mousePressEvent(event)


class _ProfileChip(QFrame):
    """Compact display of the active profile — avatar + name only."""

    def __init__(self):
        super().__init__()
        self.setObjectName("profileChip")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 4, 12, 4)
        h.setSpacing(8)

        self.avatar = AvatarBadge(emoji="ignored", image_bytes=None, diameter=28)
        self.avatar.setObjectName("profileChipAvatar")
        h.addWidget(self.avatar)

        self.name = QLabel("…")
        self.name.setObjectName("profileChipName")
        h.addWidget(self.name)

    def set_user(self, name: str, image_bytes: bytes | None = None) -> None:
        self.avatar.set_avatar(emoji="ignored", image_bytes=image_bytes)
        self.name.setText(name)


class GlobalHeader(QWidget):
    """Top bar with logo-menu (navigation), page-action slot and profile chip.

    MainWindow hides this when there is no active user (Profile-Picker).
    Pages register their action buttons via set_page_actions() — keeps a
    single Action row instead of two stacked Action rows on inner pages.
    """

    def __init__(self, window):
        super().__init__()
        self.window = window

        layout = QHBoxLayout(self)
        layout.setContentsMargins(48, 16, 48, 12)
        layout.setSpacing(10)

        self._logo_menu = _LogoMenuButton()
        self._logo_menu.add_action("Start", window.show_menu)
        self._logo_menu.add_separator()
        self._logo_menu.add_action("Test erstellen", window.show_test_create)
        self._logo_menu.add_action("Termine", window.show_events)
        self._logo_menu.add_action("Noten", window.show_grades)
        self._logo_menu.add_separator()
        self._logo_menu.add_action("Profil wechseln", window.show_profile_picker)
        layout.addWidget(self._logo_menu)

        layout.addStretch(1)

        # Page-action slot — pages drop their primary buttons here so the
        # global header is the single action strip on every inner page.
        self._action_row = QHBoxLayout()
        self._action_row.setSpacing(8)
        layout.addLayout(self._action_row)

        self.chip = _ProfileChip()
        layout.addWidget(self.chip)

    def set_user(self, name: str, image_bytes: bytes | None = None) -> None:
        self.chip.set_user(name, image_bytes)

    def set_page_actions(self, widgets: list) -> None:
        """Replace the page-action slot's contents. Call with [] to clear."""
        while self._action_row.count():
            item = self._action_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        for w in widgets:
            self._action_row.addWidget(w)

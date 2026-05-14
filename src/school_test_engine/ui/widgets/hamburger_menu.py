from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QMenu, QPushButton

from ..responsive import MIN_TOUCH_SIZE


class HamburgerMenu(QPushButton):
    """Narrow-mode action menu button. Click opens a popup with added actions.

    Use add_action(label, callback) to register entries. The button itself uses
    object name "hamburger" so QSS can style it.
    """

    def __init__(self, parent=None):
        super().__init__("☰", parent)
        self.setObjectName("hamburger")
        self.setFixedSize(MIN_TOUCH_SIZE, MIN_TOUCH_SIZE)
        self._menu = QMenu(self)
        self.setMenu(self._menu)

    def add_action(self, label: str, callback: Callable[[], None]) -> None:
        action = self._menu.addAction(label)
        action.triggered.connect(callback)

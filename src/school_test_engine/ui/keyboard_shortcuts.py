"""Phase 14 Track B: centralized keyboard shortcut bindings for runner-like pages."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget


def install_runner_shortcuts(
    page: QWidget,
    *,
    on_prev: Callable[[], None],
    on_next: Callable[[], None],
    on_mark: Callable[[], None],
    on_overview: Callable[[], None],
    on_abort: Callable[[], None],
) -> list[QShortcut]:
    """Install Phase-14 keyboard shortcuts on a runner-like page.

    Bindings:
      Left           → on_prev
      Right          → on_next
      Enter / Return → on_next
      M              → on_mark
      O              → on_overview
      Esc            → on_abort

    Tab + Space for option selection is handled natively by Qt's QRadioButton /
    QCheckBox focus handling and is NOT registered here.

    Returns the list of created QShortcut instances. The caller should retain
    this list so the shortcuts live as long as the page.
    """
    shortcuts: list[QShortcut] = []

    def _add(key, callback: Callable[[], None]) -> None:
        sc = QShortcut(QKeySequence(key), page)
        sc.activated.connect(callback)
        shortcuts.append(sc)

    _add(Qt.Key.Key_Left, on_prev)
    _add(Qt.Key.Key_Right, on_next)
    _add(Qt.Key.Key_Return, on_next)
    _add(Qt.Key.Key_Enter, on_next)
    _add(Qt.Key.Key_M, on_mark)
    _add(Qt.Key.Key_O, on_overview)
    _add(Qt.Key.Key_Escape, on_abort)

    return shortcuts

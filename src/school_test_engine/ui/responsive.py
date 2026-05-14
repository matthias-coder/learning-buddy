from __future__ import annotations

from PySide6.QtWidgets import QWidget


BREAKPOINT_NARROW = 768
"""Below this window width, UI switches to narrow-mode (hamburger menu,
single-column layouts). Standard mobile/tablet boundary."""

MIN_TOUCH_SIZE = 44
"""Apple HIG minimum touch target size in pixels. Also feels comfortable
for mouse users — no downside to enforcing on desktop."""


def is_narrow(widget: QWidget) -> bool:
    """True if the widget's top-level window is below the narrow breakpoint.

    Use this in resizeEvent or reload() to decide between wide/narrow layouts.
    """
    # Use QWidget.window explicitly: some pages shadow .window with an attribute
    # that points to the MainWindow (callable as an instance). Calling the
    # bound method via the class avoids that collision.
    top = QWidget.window(widget)
    return top.width() < BREAKPOINT_NARROW

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
    top = widget.window()
    return top.width() < BREAKPOINT_NARROW

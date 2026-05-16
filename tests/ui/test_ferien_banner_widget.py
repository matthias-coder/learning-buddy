from __future__ import annotations

from datetime import date

import pytest

from school_test_engine.school_calendar.service import FerienBannerState


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_banner_label_reflects_state():
    from school_test_engine.ui.widgets.ferien_banner import FerienBanner
    s = FerienBannerState(
        mode="countdown",
        label="Noch 23 Tage bis Herbstferien — 17.10.2026",
        days=23, target_date=date(2026, 10, 17),
        vacation_title="Herbstferien",
    )
    b = FerienBanner(s)
    assert "23" in b._label.text()
    assert "Herbstferien" in b._label.text()


def test_banner_click_calls_window_show_school_calendar(qapp):
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtGui import QMouseEvent
    from school_test_engine.ui.widgets.ferien_banner import FerienBanner

    class _StubWindow:
        def __init__(self):
            self.called = 0
        def show_school_calendar(self):
            self.called += 1

    win = _StubWindow()
    s = FerienBannerState(mode="countdown", label="x", days=1,
                          target_date=date(2026, 1, 1), vacation_title="X")
    b = FerienBanner(s, get_window=lambda: win)
    ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(1, 1), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    b.mousePressEvent(ev)
    assert win.called == 1

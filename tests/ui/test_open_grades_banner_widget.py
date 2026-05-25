from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_banner_text_singular_for_count_1():
    from school_test_engine.ui.widgets.open_grades_banner import OpenGradesBanner
    b = OpenGradesBanner(count=1)
    from PySide6.QtWidgets import QLabel
    texts = [lbl.text() for lbl in b.findChildren(QLabel)]
    assert any("1 offene Note" in t for t in texts)


def test_banner_text_plural_for_count_3():
    from school_test_engine.ui.widgets.open_grades_banner import OpenGradesBanner
    b = OpenGradesBanner(count=3)
    from PySide6.QtWidgets import QLabel
    texts = [lbl.text() for lbl in b.findChildren(QLabel)]
    assert any("3 offene Noten" in t for t in texts)


def test_banner_click_navigates_to_school_calendar_with_initial_tab(qapp):
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtGui import QMouseEvent
    from school_test_engine.ui.widgets.open_grades_banner import OpenGradesBanner

    class _StubWindow:
        def __init__(self):
            self.calls = []
        def show_school_calendar(self, initial_tab=None):
            self.calls.append(("show_school_calendar", initial_tab))

    win = _StubWindow()
    b = OpenGradesBanner(count=2, get_window=lambda: win)
    ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(1, 1), QPointF(1, 1),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    b.mousePressEvent(ev)
    assert win.calls == [("show_school_calendar", "past")]

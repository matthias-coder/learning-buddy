from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_back_button_renders_text_and_arrow():
    from school_test_engine.ui.widgets.back_button import BackButton
    b = BackButton()
    # Find the text-label child:
    from PySide6.QtWidgets import QLabel
    labels = b.findChildren(QLabel)
    texts = [lbl.text() for lbl in labels]
    assert any("Zurück" in t for t in texts)
    assert any("←" in t or "⮜" in t for t in texts)


def test_back_button_click_emits_signal():
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtGui import QMouseEvent
    from school_test_engine.ui.widgets.back_button import BackButton

    b = BackButton()
    received = []
    b.clicked.connect(lambda: received.append(1))

    ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(1, 1), QPointF(1, 1),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    b.mousePressEvent(ev)
    assert received == [1]


def test_back_button_uses_pointing_cursor():
    from PySide6.QtCore import Qt
    from school_test_engine.ui.widgets.back_button import BackButton
    b = BackButton()
    assert b.cursor().shape() == Qt.CursorShape.PointingHandCursor

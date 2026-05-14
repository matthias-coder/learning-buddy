import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


def test_flow_layout_constructs(app):
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    layout = FlowLayout()
    assert layout.count() == 0


def test_flow_layout_adds_widgets(app):
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    container = QWidget()
    layout = FlowLayout(container)
    for _ in range(3):
        layout.addWidget(QPushButton("X"))
    assert layout.count() == 3


def test_flow_layout_heightForWidth_wraps(app):
    """When width is small, total height grows (rows wrap)."""
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    container = QWidget()
    layout = FlowLayout(container)
    for _ in range(10):
        b = QPushButton("Item")
        b.setFixedSize(100, 30)
        layout.addWidget(b)

    narrow_height = layout.heightForWidth(150)   # ~1 item per row
    wide_height = layout.heightForWidth(1200)    # many items per row
    assert narrow_height > wide_height


def test_flow_layout_takeAt_removes(app):
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    container = QWidget()
    layout = FlowLayout(container)
    layout.addWidget(QPushButton("A"))
    layout.addWidget(QPushButton("B"))
    item = layout.takeAt(0)
    assert item is not None
    assert layout.count() == 1


def test_flow_layout_has_height_for_width(app):
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    layout = FlowLayout()
    assert layout.hasHeightForWidth() is True


def test_flow_layout_expanding_directions_none(app):
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    layout = FlowLayout()
    # FlowLayout doesn't expand on its own — children control sizing
    assert layout.expandingDirections().value == 0

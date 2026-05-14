import pytest

from PySide6.QtWidgets import QApplication, QWidget
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


def test_constants_present():
    from school_test_engine.ui.responsive import BREAKPOINT_NARROW, MIN_TOUCH_SIZE
    assert BREAKPOINT_NARROW == 768
    assert MIN_TOUCH_SIZE == 44


def test_is_narrow_below_threshold(app):
    from school_test_engine.ui.responsive import is_narrow
    w = QWidget()
    w.resize(500, 600)
    assert is_narrow(w) is True


def test_is_narrow_at_threshold(app):
    from school_test_engine.ui.responsive import is_narrow
    w = QWidget()
    w.resize(768, 600)
    # 768 is NOT < 768; should be False (wide mode starts at 768)
    assert is_narrow(w) is False


def test_is_narrow_above_threshold(app):
    from school_test_engine.ui.responsive import is_narrow
    w = QWidget()
    w.resize(1280, 720)
    assert is_narrow(w) is False


def test_is_narrow_uses_top_level_window(app):
    """is_narrow should check the top-level window, not the immediate widget."""
    from school_test_engine.ui.responsive import is_narrow
    parent = QWidget()
    parent.resize(500, 400)
    child = QWidget(parent)
    child.resize(2000, 2000)  # child can be huge, but window is small
    assert is_narrow(child) is True

import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


def test_hamburger_menu_constructs(app):
    from school_test_engine.ui.widgets.hamburger_menu import HamburgerMenu
    h = HamburgerMenu()
    assert h.text() == "☰"


def test_hamburger_menu_has_min_touch_size(app):
    from school_test_engine.ui.widgets.hamburger_menu import HamburgerMenu
    from school_test_engine.ui.responsive import MIN_TOUCH_SIZE
    h = HamburgerMenu()
    assert h.width() == MIN_TOUCH_SIZE
    assert h.height() == MIN_TOUCH_SIZE


def test_hamburger_menu_add_action_appears(app):
    from school_test_engine.ui.widgets.hamburger_menu import HamburgerMenu
    h = HamburgerMenu()
    fired = []
    h.add_action("Test", lambda: fired.append(1))
    # Trigger via menu interface
    actions = h.menu().actions()
    assert len(actions) == 1
    assert actions[0].text() == "Test"
    actions[0].trigger()
    assert fired == [1]

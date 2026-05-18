from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_logo_menu_has_schulkalender_entry():
    from school_test_engine.ui.widgets.global_header import GlobalHeader

    class _StubWindow:
        def __init__(self):
            self.called = 0
        def show_menu(self): pass
        def show_test_create(self): pass
        def show_events(self): pass
        def show_grades(self): pass
        def show_error_book(self): pass
        def show_school_calendar(self):
            self.called += 1
        def show_profile_picker(self): pass
        def _navigate_back(self): pass

    win = _StubWindow()
    header = GlobalHeader(win)
    actions = header._logo_menu._menu.actions()
    labels = [a.text() for a in actions if a.text()]
    assert "Schulkalender" in labels
    for a in actions:
        if a.text() == "Schulkalender":
            a.trigger()
    assert win.called == 1

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.ui.widgets.global_header import GlobalHeader


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


class _MockWindow:
    def show_menu(self): pass
    def show_test_create(self): pass
    def show_events(self): pass
    def show_grades(self): pass
    def show_error_book(self): pass
    def show_school_calendar(self): pass
    def show_profile_picker(self): pass


def test_logo_menu_has_fehlerheft_entry(qt_app):
    header = GlobalHeader(_MockWindow())
    labels = [a.text() for a in header._logo_menu._menu.actions() if not a.isSeparator()]
    assert "Fehlerheft" in labels
    # Reihenfolge: nach Noten, vor Profil wechseln
    idx_noten = labels.index("Noten")
    idx_fehler = labels.index("Fehlerheft")
    idx_profil = labels.index("Profil wechseln")
    assert idx_noten < idx_fehler < idx_profil

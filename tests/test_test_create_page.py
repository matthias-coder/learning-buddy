"""TestCreatePage — landing page that fans out to prompt_builder or import_wizard."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    inst = QApplication.instance() or QApplication([])
    return inst


class _StubWindow:
    def __init__(self):
        self.navigated_to: str | None = None

    def show_menu(self):
        self.navigated_to = "menu"

    def show_prompt_builder(self):
        self.navigated_to = "prompt_builder"

    def show_import(self):
        self.navigated_to = "import"


def test_constructs(app):
    from school_test_engine.ui.pages.test_create import TestCreatePage
    page = TestCreatePage(_StubWindow())
    assert page is not None


def test_ki_card_routes_to_prompt_builder(app):
    from school_test_engine.ui.pages.test_create import TestCreatePage
    win = _StubWindow()
    page = TestCreatePage(win)
    page._open_prompt_builder()
    assert win.navigated_to == "prompt_builder"


def test_datei_card_routes_to_import(app):
    from school_test_engine.ui.pages.test_create import TestCreatePage
    win = _StubWindow()
    page = TestCreatePage(win)
    page._open_import()
    assert win.navigated_to == "import"

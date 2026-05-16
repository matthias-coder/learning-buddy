"""ExamCard layout: actions live in an overflow menu so the card stays compact
and labels never clip at narrow widths."""
from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMenu, QPushButton


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _event(**overrides):
    base = {
        "event_id": 1,
        "subject": "Mathe",
        "kind": "klassenarbeit",
        "topics": ["Lineare Gleichungen"],
        "days_until": 3,
        "linked_assessment_id": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _menu_actions(card) -> list[str]:
    btn = next(b for b in card.findChildren(QPushButton) if b.text() == "…")
    menu = btn.menu()
    assert isinstance(menu, QMenu)
    return [a.text() for a in menu.actions() if a.text()]


def test_unlinked_event_menu_has_all_four_actions(app):
    from school_test_engine.ui.widgets.exam_card import ExamCard
    card = ExamCard(_event())
    actions = _menu_actions(card)
    assert actions == [
        "Test erstellen",
        "Note eintragen",
        "Lernplan erstellen",
        "Termin bearbeiten",
    ], actions


def test_linked_event_menu_omits_practice_and_grade(app):
    from school_test_engine.ui.widgets.exam_card import ExamCard
    card = ExamCard(_event(linked_assessment_id=42))
    actions = _menu_actions(card)
    assert actions == ["Lernplan erstellen", "Termin bearbeiten"], actions


def test_card_is_compact(app):
    """Without an action row, the card's preferred height should be well below
    the old 200px minimum."""
    from school_test_engine.ui.widgets.exam_card import ExamCard
    card = ExamCard(_event())
    card.setFixedWidth(340)
    card.adjustSize()
    app.processEvents()
    assert card.sizeHint().height() < 180, (
        f"card should be compact without the old action row, got {card.sizeHint().height()}"
    )

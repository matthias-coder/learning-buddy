"""ExamCard action-row: wraps to multiple lines on narrow widths instead of clipping."""
from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _event(**overrides):
    base = {
        "event_id": 1,
        "subject": "Mathe",
        "kind": "klassenarbeit",
        "topics": [],
        "days_until": 3,
        "linked_assessment_id": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_card_does_not_clip_action_buttons_at_narrow_width(app):
    from school_test_engine.ui.widgets.exam_card import ExamCard

    card = ExamCard(_event())
    card.setFixedWidth(280)
    card.adjustSize()
    card.show()
    app.processEvents()

    # Find all action buttons by their text labels.
    from PySide6.QtWidgets import QPushButton
    labels = {b.text() for b in card.findChildren(QPushButton)}
    assert {"Test bauen", "Note eintragen", "Lernplan PDF"}.issubset(labels), (
        f"missing action buttons: {labels}"
    )

    # FlowLayout reports heightForWidth — narrow width should ask for more height
    # than a wide width (i.e., wrapping happened).
    narrow_height = card.sizeHint().height()
    card.setFixedWidth(600)
    card.adjustSize()
    app.processEvents()
    wide_height = card.sizeHint().height()
    assert narrow_height >= wide_height, (
        f"narrow card should be taller (wrapped actions), got {narrow_height} vs wide {wide_height}"
    )

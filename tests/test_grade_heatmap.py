"""Phase 14 Track C: GradeHeatmap widget."""
from __future__ import annotations

import os
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_heatmap_constructs(app):
    from school_test_engine.ui.widgets.grade_heatmap import GradeHeatmap
    hm = GradeHeatmap()
    assert hm.minimumHeight() >= 220


def test_heatmap_paints_empty(app):
    from school_test_engine.ui.widgets.grade_heatmap import GradeHeatmap
    hm = GradeHeatmap()
    hm.resize(600, 220)
    pixmap = hm.grab()
    assert not pixmap.isNull()


def test_heatmap_set_data_paints(app):
    from school_test_engine.ui.widgets.grade_heatmap import GradeHeatmap
    hm = GradeHeatmap()
    hm.resize(600, 240)
    monday = date.today() - timedelta(days=date.today().weekday())
    weeks = [monday - timedelta(weeks=i) for i in reversed(range(8))]
    hm.set_data(
        weeks=weeks,
        rows=[
            ("Mathe", {weeks[7]: 2.0, weeks[5]: 3.0}),
            ("Englisch", {weeks[6]: 2.5}),
        ],
    )
    pixmap = hm.grab()
    assert not pixmap.isNull()

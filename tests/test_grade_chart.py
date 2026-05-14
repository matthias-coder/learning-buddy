"""Phase 14 Track C: GradeChart QPainter widget."""
from __future__ import annotations

import os
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_grade_chart_constructs_empty(app):
    from school_test_engine.ui.widgets.grade_chart import GradeChart
    chart = GradeChart()
    assert chart.minimumHeight() >= 200


def test_grade_chart_set_data_does_not_raise(app):
    from school_test_engine.ui.widgets.grade_chart import GradeChart
    chart = GradeChart()
    today = date.today()
    chart.set_data(
        schriftlich=[(today - timedelta(days=30), 2.0), (today, 2.5)],
        muendlich=[(today - timedelta(days=60), 2.5), (today - timedelta(days=10), 2.0)],
    )


def test_grade_chart_paints_without_exception(app):
    from school_test_engine.ui.widgets.grade_chart import GradeChart
    chart = GradeChart()
    chart.resize(QSize(400, 200))
    today = date.today()
    chart.set_data(
        schriftlich=[(today - timedelta(days=30), 2.0), (today, 2.5)],
        muendlich=[],
    )
    pixmap = chart.grab()
    assert not pixmap.isNull()


def test_grade_chart_placeholder_when_too_few_points(app):
    from school_test_engine.ui.widgets.grade_chart import GradeChart
    chart = GradeChart()
    chart.set_data(schriftlich=[], muendlich=[])
    pixmap = chart.grab()
    assert not pixmap.isNull()

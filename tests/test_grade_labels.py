import pytest

from school_test_engine.grading.grade_labels import (
    GRADE_OPTIONS,
    clamp_grade,
    grade_label,
    label_to_value,
)


def test_options_exclude_1_plus_and_6_minus():
    labels = [l for l, _ in GRADE_OPTIONS]
    assert len(labels) == 16
    assert "1+" not in labels and "6−" not in labels
    assert labels[0] == "1" and labels[-1] == "6"


@pytest.mark.parametrize("label,value", [
    ("1", 1.0), ("1−", 1.25), ("2+", 1.75), ("2", 2.0), ("2−", 2.25),
    ("3+", 2.75), ("4", 4.0), ("5−", 5.25), ("6+", 5.75), ("6", 6.0),
])
def test_label_value_roundtrip(label, value):
    assert label_to_value(label) == value
    assert grade_label(value) == label


def test_legacy_half_steps():
    assert grade_label(2.5) == "2–3"
    assert grade_label(5.5) == "5–6"
    assert label_to_value("2–3") == 2.5


def test_clamp():
    assert clamp_grade(7) == 6.0
    assert clamp_grade(0.2) == 1.0


def test_grade_pill_shows_label():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from school_test_engine.ui.widgets.grade_pill import GradePill
    assert GradePill(1.75).text() == "2+"
    assert GradePill(2.0).text() == "2"
    assert GradePill(2.5).text() == "2–3"

"""Phase 15: SUBJECTS_ALL is extended to cover Clemens' Realschule subjects."""
from __future__ import annotations

from school_test_engine.ui._subjects import SUBJECTS_ALL


def test_includes_main_subjects():
    for s in ["Mathe", "Englisch", "Deutsch"]:
        assert s in SUBJECTS_ALL


def test_includes_natural_sciences():
    for s in ["Bio", "Physik", "Chemie"]:
        assert s in SUBJECTS_ALL


def test_includes_humanities_and_others():
    for s in ["Geschichte", "Geographie", "Politik und Wirtschaft", "Religion", "Musik"]:
        assert s in SUBJECTS_ALL


def test_eleven_subjects_total():
    assert len(SUBJECTS_ALL) == 11

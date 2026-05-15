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


def test_every_subject_has_a_pill_variant():
    """Every subject in SUBJECTS_ALL maps to a known pill variant —
    no fallback-to-default behavior."""
    from school_test_engine.ui._subjects import _SUBJECT_VARIANT, SUBJECTS_ALL
    known_variants = {"tea", "clay", "paper", "rose", "honey", "sky"}
    for subject in SUBJECTS_ALL:
        assert subject in _SUBJECT_VARIANT, f"{subject!r} missing from _SUBJECT_VARIANT"
        assert _SUBJECT_VARIANT[subject] in known_variants


def test_existing_subject_variants_unchanged():
    """The 6 original subjects must keep their existing pill variants —
    no surprise visual regression."""
    from school_test_engine.ui._subjects import subject_variant
    assert subject_variant("Mathe") == "clay"
    assert subject_variant("Englisch") == "tea"
    assert subject_variant("Bio") == "tea"
    assert subject_variant("Physik") == "sky"
    assert subject_variant("Chemie") == "honey"
    assert subject_variant("Geschichte") == "paper"

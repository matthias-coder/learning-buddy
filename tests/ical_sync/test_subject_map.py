"""Phase 15: subject_map normalizes feed-side subject strings to app-side."""
from __future__ import annotations

from school_test_engine.ical_sync.subject_map import map_subject


def test_mathematik_maps_to_mathe():
    assert map_subject("Mathematik") == "Mathe"


def test_religion_variants_map_to_religion():
    assert map_subject("Religion - evangelisch") == "Religion"
    assert map_subject("Religion - katholisch") == "Religion"
    assert map_subject("Religion - ethisch") == "Religion"
    assert map_subject("Ethik") == "Religion"


def test_erdkunde_maps_to_geographie():
    assert map_subject("Erdkunde") == "Geographie"


def test_powi_maps_to_politik_und_wirtschaft():
    assert map_subject("PoWi") == "Politik und Wirtschaft"
    assert map_subject("Sozialkunde") == "Politik und Wirtschaft"


def test_unknown_subject_passthrough():
    assert map_subject("Englisch") == "Englisch"
    assert map_subject("Deutsch") == "Deutsch"
    assert map_subject("Musik") == "Musik"


def test_strips_whitespace():
    assert map_subject("  Mathematik  ") == "Mathe"

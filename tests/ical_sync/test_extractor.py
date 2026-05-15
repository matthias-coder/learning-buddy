"""Phase 15: extractor parses DESCRIPTION into (subject, kind) + applies subject_map."""
from __future__ import annotations

from school_test_engine.ical_sync.extractor import EventRecord, to_event_record
from school_test_engine.ical_sync.parser import RawVEvent


def _ev(description: str, uid: str = "x-klausur-1@h") -> RawVEvent:
    return RawVEvent(
        uid=uid, summary="", description=description,
        dtstart_date="2026-03-10", categories=(),
    )


def test_arbeit_in_mathematik_yields_klassenarbeit_mathe():
    rec = to_event_record(_ev("Arbeit in Mathematik R8b (082M07-R)"))
    assert rec is not None
    assert rec.kind == "klassenarbeit"
    assert rec.subject == "Mathe"
    assert rec.event_date == "2026-03-10"


def test_lernkontrolle_in_chemie_yields_test_chemie():
    rec = to_event_record(_ev("Lernkontrolle in Chemie R8b (082CH02-R)"))
    assert rec is not None
    assert rec.kind == "test"
    assert rec.subject == "Chemie"


def test_klausur_yields_klausur_kind():
    rec = to_event_record(_ev("Klausur in Mathematik Q1 (Q1M01-G)"))
    assert rec is not None
    assert rec.kind == "klausur"


def test_religion_evangelisch_is_mapped_to_religion():
    rec = to_event_record(_ev("Lernkontrolle in Religion - evangelisch (REV8_GcRab01-)"))
    assert rec is not None
    assert rec.subject == "Religion"


def test_unknown_description_format_returns_none():
    rec = to_event_record(_ev("Some unrelated text"))
    assert rec is None


def test_empty_description_returns_none():
    rec = to_event_record(_ev(""))
    assert rec is None


def test_record_keeps_full_uid():
    rec = to_event_record(_ev(
        "Arbeit in Mathematik R8b (082M07-R)",
        uid="20010101T000001-klausur-9084-14627-2026-03-10@6115.start.schulportal.hessen.de",
    ))
    assert rec is not None
    assert rec.external_uid.endswith("@6115.start.schulportal.hessen.de")


def test_free_text_between_class_designator_and_code_does_not_bleed_into_subject():
    """Regression for line-folded DESCRIPTION where free-text follows R8b
    before the parenthetical course code. The regex must consume the free
    text into the optional class-designator group, not into subject."""
    desc = (
        "Arbeit in Geographie R8b mit besonders langem Hinweis-Text "
        "der ueber die Standard-Zeilenlaenge hinausgeht und gefoldet wird (082GEO02-R)"
    )
    rec = to_event_record(_ev(desc))
    assert rec is not None
    assert rec.subject == "Geographie"
    assert rec.kind == "klassenarbeit"

import pytest

from school_test_engine.prompt_builder.assembler import assemble_prompt


def test_assemble_appends_form_fields():
    out = assemble_prompt(
        subject="Mathe",
        topics=["Lineare Gleichungen", "Quadratische Gleichungen"],
        count=10,
        distribution="auto",
        style_briefing=None,
    )
    assert "Fach: Mathe" in out
    assert "Thema: Lineare Gleichungen, Quadratische Gleichungen" in out
    assert "Anzahl Fragen: 10" in out


def test_assemble_auto_distribution_label():
    out = assemble_prompt(
        subject="Bio", topics=["Zellen"], count=5,
        distribution="auto", style_briefing=None,
    )
    assert "Verteilung: automatisch (ca. 40/40/20)" in out


def test_assemble_manual_distribution_label():
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=10,
        distribution="manuell:3-5-2", style_briefing=None,
    )
    assert "Verteilung: 3 leicht, 5 mittel, 2 schwer" in out


def test_assemble_includes_style_briefing():
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5, distribution="auto",
        style_briefing="Schreibstil: Du-Form, freundlich.",
    )
    assert "## Eigener Stil" in out
    assert "Schreibstil: Du-Form, freundlich." in out


def test_assemble_omits_style_section_when_none():
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5, distribution="auto",
        style_briefing=None,
    )
    assert "## Eigener Stil" not in out


def test_assemble_omits_style_section_when_empty():
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5, distribution="auto",
        style_briefing="   ",
    )
    assert "## Eigener Stil" not in out


def test_assemble_empty_topics_shows_placeholder():
    out = assemble_prompt(
        subject="Mathe", topics=[], count=5, distribution="auto",
        style_briefing=None,
    )
    assert "Thema: <bitte ergänzen>" in out


def test_assemble_inconsistent_manual_distribution_shows_marker():
    # caller is responsible for upfront validation, but the assembler
    # should still produce a string with a visible marker.
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=10,
        distribution="manuell:inkonsistent", style_briefing=None,
    )
    assert "Verteilung: <inkonsistent>" in out

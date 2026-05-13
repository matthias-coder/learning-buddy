import pytest

from school_test_engine.prompt_builder.assembler import assemble_prompt
from school_test_engine.prompt_builder.school_context import SchoolContext


def _full_ctx():
    return SchoolContext(
        grade=8, school_type="Realschule", bundesland="Hessen",
        school_name="Heinrich-Heine-RS", school_year="2025/26",
    )


def test_full_context_substitutes_all_tokens():
    out = assemble_prompt(
        subject="Mathe", topics=["Lineare Gleichungen"], count=10,
        distribution="auto", style_briefing=None,
        school_context=_full_ctx(),
    )
    assert "8. Klasse Realschule" in out
    assert "in **Hessen**" in out
    assert "Heinrich-Heine-RS" in out
    assert "Schuljahr 2025/26" in out
    # JSON schema lines
    assert '"grade": 8' in out
    assert '"school_type": "Realschule"' in out
    # No bare tokens left
    assert "{{grade}}" not in out
    assert "{{school_type}}" not in out
    assert "{{bundesland}}" not in out
    assert "{{school_name}}" not in out
    assert "{{school_year}}" not in out


def test_grade_and_school_type_null_show_markers():
    ctx = SchoolContext(grade=None, school_type=None,
                       bundesland="Hessen", school_name="X", school_year="2025/26")
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None, school_context=ctx,
    )
    assert "<Klasse>. Klasse <Schultyp>" in out
    # JSON schema also gets markers
    assert '"grade": <Klasse>' in out
    assert '"school_type": "<Schultyp>"' in out


def test_bundesland_null_strips_phrase():
    ctx = SchoolContext(grade=8, school_type="Realschule",
                       bundesland=None,
                       school_name="X", school_year="2025/26")
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None, school_context=ctx,
    )
    assert "in **<Bundesland>**" not in out
    assert "<Bundesland>" not in out
    # No leftover " in " with nothing after it
    assert " in  (" not in out
    assert "(Schule: X, Schuljahr 2025/26)" in out


def test_school_name_and_year_both_null_strip_phrase():
    ctx = SchoolContext(grade=8, school_type="Realschule",
                       bundesland="Hessen", school_name=None, school_year=None)
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None, school_context=ctx,
    )
    assert "(Schule:" not in out
    assert "Schuljahr" not in out
    assert "<Schule>" not in out
    assert "<Schuljahr>" not in out
    # Bundesland survives
    assert "in **Hessen**" in out


def test_partial_school_name_or_year_still_strips_both():
    """Phase 9 strips the whole parenthetical when EITHER name or year is NULL.
    Granular handling deferred to a later phase."""
    ctx = SchoolContext(grade=8, school_type="Realschule",
                       bundesland="Hessen", school_name="Heine-RS", school_year=None)
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None, school_context=ctx,
    )
    # School-name set but year not — entire paren-phrase still drops per spec
    assert "(Schule:" not in out


def test_school_context_none_treated_as_all_null():
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None,
        school_context=None,
    )
    assert "<Klasse>" in out
    assert "<Schultyp>" in out
    # All optional phrases stripped
    assert "(Schule:" not in out
    assert "<Bundesland>" not in out


def test_school_context_omitted_kwarg_treated_as_none():
    # Backwards-compatibility: callers that don't pass school_context still get a valid prompt
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None,
    )
    assert "<Klasse>" in out
    assert "<Schultyp>" in out

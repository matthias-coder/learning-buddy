from __future__ import annotations

from . import template
from .school_context import SchoolContext


def _apply_school_context(text: str, ctx: SchoolContext | None) -> str:
    if ctx is None:
        ctx = SchoolContext(None, None, None, None, None)

    # Phase A — Phrase-strip when whole groups are NULL.
    # (Strip BEFORE token-replace so we never leave " <Bundesland>" garbage.)
    if ctx.bundesland is None:
        text = text.replace(" in **{{bundesland}}**", "")
    if ctx.school_name is None or ctx.school_year is None:
        # Phase 9 deliberately strips the whole parenthetical when EITHER is NULL.
        # Granular handling deferred (see spec §7).
        text = text.replace(" (Schule: {{school_name}}, Schuljahr {{school_year}})", "")

    # Phase B — Token-replace, leftover NULLs become visible markers.
    substitutions = {
        "{{grade}}":       str(ctx.grade) if ctx.grade is not None else "<Klasse>",
        "{{school_type}}": ctx.school_type or "<Schultyp>",
        "{{bundesland}}":  ctx.bundesland or "<Bundesland>",
        "{{school_name}}": ctx.school_name or "<Schule>",
        "{{school_year}}": ctx.school_year or "<Schuljahr>",
    }
    for token, value in substitutions.items():
        text = text.replace(token, value)
    return text


def _distribution_label(distribution: str) -> str:
    if distribution == "auto":
        return "automatisch (ca. 40/40/20)"
    if not distribution.startswith("manuell:"):
        return "<inkonsistent>"
    payload = distribution.split(":", 1)[1]
    parts = payload.split("-")
    if len(parts) != 3:
        return "<inkonsistent>"
    try:
        leicht, mittel, schwer = (int(p) for p in parts)
    except ValueError:
        return "<inkonsistent>"
    return f"{leicht} leicht, {mittel} mittel, {schwer} schwer"


def assemble_prompt(
    subject: str,
    topics: list[str],
    count: int,
    distribution: str,
    style_briefing: str | None,
    school_context: SchoolContext | None = None,
) -> str:
    """Compose the final prompt text from form inputs, optional style briefing,
    and optional school context.

    The school context substitutes {{grade}}, {{school_type}}, {{bundesland}},
    {{school_name}}, {{school_year}} tokens in the base template (loaded from
    examples/PROMPT-FOR-AI.md). NULL fields show as <Marker> placeholders.
    NULL bundesland strips the " in <BL>" phrase; NULL school_name OR
    school_year strips the entire "(Schule: …, Schuljahr …)" phrase.
    """
    base = template.load_base_prompt()
    base = _apply_school_context(base, school_context)

    style_section = ""
    if style_briefing and style_briefing.strip():
        style_section = (
            "\n## Eigener Stil\n\n"
            + style_briefing.strip()
            + "\n"
        )

    topic_text = ", ".join(t.strip() for t in topics if t.strip()) or "<bitte ergänzen>"
    dist_label = _distribution_label(distribution)

    tail = (
        "\n---\n\n"
        f"Fach: {subject}\n"
        f"Thema: {topic_text}\n"
        f"Anzahl Fragen: {count}\n"
        f"Verteilung: {dist_label}\n"
    )
    return base.rstrip() + "\n" + style_section + tail

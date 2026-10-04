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

    # Grade / school type: never leave "<Klasse>"/"<Schultyp>" in the prompt.
    audience = "**{{grade}}. Klasse {{school_type}}**"
    if ctx.grade is None and ctx.school_type is None:
        text = text.replace("für die " + audience, "eine Schülerin oder einen Schüler")
    elif ctx.grade is None:
        text = text.replace(audience, "Schulart **{{school_type}}**")
    elif ctx.school_type is None:
        text = text.replace(audience, "**{{grade}}. Klasse**")
    if ctx.school_type is None:
        # Optional in the schema (defaults to Realschule) -> drop the line.
        text = text.replace('  "school_type": "{{school_type}}",\n', "")

    # Phase B — Token-replace. grade is required by the schema; neutral default 8.
    substitutions = {
        "{{grade}}":       str(ctx.grade) if ctx.grade is not None else "8",
        "{{school_type}}": ctx.school_type or "Realschule",
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
    examples/PROMPT-FOR-AI.md). NULL grade/school_type are phrased neutrally (no <Marker> left behind).
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

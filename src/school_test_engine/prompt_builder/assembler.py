from __future__ import annotations

from . import template


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
) -> str:
    """Compose the final prompt text from form inputs + optional style briefing.

    Args:
        subject: "Mathe" | "Englisch" | … (free text allowed)
        topics: List of topic strings (joined with ", " in output)
        count: Number of questions requested
        distribution: "auto" or "manuell:L-M-S" (e.g. "manuell:3-5-2")
        style_briefing: User's personal hint to the AI, or None to omit section.
    """
    base = template.load_base_prompt()

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

from __future__ import annotations

import re

from ..resources import examples_dir

_PROMPT_PATH = (
    examples_dir() / "PROMPT-FOR-AI.md"
)


# Minimal fallback if examples/PROMPT-FOR-AI.md is missing. Keeps the schema
# definition so generated tests remain importable. Update if the schema changes.
_BACKUP_TEMPLATE = """\
# Test-Fragen mit KI generieren — Prompt-Vorlage

## Aufgabe

Du erzeugst einen Übungs-Test für die **{{grade}}. Klasse {{school_type}}** in **{{bundesland}}** (Schule: {{school_name}}, Schuljahr {{school_year}}).
Antworte ausschließlich mit gültigem JSON im unten beschriebenen Format.

## Schema

```
{
  "schema_version": 1,
  "title": "<Titel>",
  "subject": "<Mathe|Englisch|Bio|Physik|Chemie|Geschichte>",
  "grade": {{grade}},
  "school_type": "{{school_type}}",
  "questions": [
    {
      "id": "q1",
      "type": "single_choice",
      "topic": "<Unterthema>",
      "difficulty": "leicht|mittel|schwer",
      "points": 2,
      "prompt": "<Aufgabe>",
      "choices": [{"id": "a", "text": "..."}],
      "correct": ["a"],
      "explanation": "<Lösung>"
    }
  ]
}
```

## Regeln

1. topic-Wert pro Test konsistent schreiben.
2. id pro Frage eindeutig: q1, q2, ...
3. correct verweist auf choices.id-Werte.
4. Schwierigkeitsmischung ca. 40% leicht, 40% mittel, 20% schwer.
5. Sprache: Deutsch (außer Fach Englisch).
"""


def _strip_section_to_separator(text: str, header_marker: str) -> str:
    """Removes a section starting with `header_marker` until the next `---` line
    (or end of file)."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        if not skipping and line.startswith(header_marker):
            skipping = True
            continue
        if skipping:
            if line.strip() == "---":
                skipping = False
                # consume the separator itself too — drop the orphan `---`
                continue
            continue
        out.append(line)
    return "".join(out)


def _strip_section_to_end(text: str, header_marker: str) -> str:
    """Removes a section starting with `header_marker` until end of file."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        if line.startswith(header_marker):
            break
        out.append(line)
    return "".join(out)


def load_base_prompt() -> str:
    """Load the prompt template, stripping the TODO and Anhängen sections.

    Reads `examples/PROMPT-FOR-AI.md` at runtime so Matthias can keep editing
    the markdown. Falls back to a small backup template if the file is missing
    or unparseable.
    """
    if not _PROMPT_PATH.exists():
        return _BACKUP_TEMPLATE
    try:
        raw = _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return _BACKUP_TEMPLATE
    cleaned = _strip_section_to_separator(raw, "## TODO MATTHIAS")
    cleaned = _strip_section_to_end(cleaned, "## Anhängen am Ende")
    # Collapse runs of 3+ blank lines that the stripping may produce
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip() + "\n"

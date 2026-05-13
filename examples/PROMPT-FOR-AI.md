# Test-Fragen mit KI generieren — Prompt-Vorlage

Diese Datei in Claude, ChatGPT oder Gemini einfügen, am Ende **Fach + Thema + Anzahl Fragen** ergänzen. Die KI gibt dir gültiges JSON zurück, das du direkt importieren kannst.

---

## Aufgabe

Du erzeugst einen Übungs-Test für die **{{grade}}. Klasse {{school_type}}** in **{{bundesland}}** (Schule: {{school_name}}, Schuljahr {{school_year}}). Antworte **ausschließlich mit gültigem JSON** im unten beschriebenen Format. Keine Erklärung, kein Code-Block-Fence, kein Markdown drumherum — nur das pure JSON.

## Schema

```json
{
  "schema_version": 1,
  "title": "<kurzer Titel des Tests>",
  "subject": "<Mathe|Englisch|Bio|Physik|Chemie|Geschichte>",
  "grade": {{grade}},
  "school_type": "{{school_type}}",
  "description": "<1 Satz, optional>",
  "time_limit_minutes": <Zahl, optional>,
  "questions": [
    {
      "id": "q1",
      "type": "single_choice",
      "topic": "<feines Unterthema, z.B. 'Lineare Gleichungen — Umformen'>",
      "difficulty": "leicht|mittel|schwer",
      "points": <positive Zahl>,
      "prompt": "<die Aufgabenstellung>",
      "prompt_math": "<optional: LaTeX-Formel, z.B. 'x^2 - 5x + 6 = 0'>",
      "choices": [
        { "id": "a", "text": "<Antwortoption>" },
        { "id": "b", "text": "..." },
        { "id": "c", "text": "..." },
        { "id": "d", "text": "..." }
      ],
      "correct": ["b"],
      "explanation": "<kurze Lösung / Begründung>"
    },
    {
      "id": "q2",
      "type": "multi_choice",
      "topic": "...",
      "difficulty": "mittel",
      "points": 4,
      "prompt": "...",
      "choices": [ { "id": "a", "text": "..." }, ... ],
      "correct": ["a", "c"],
      "scoring": "partial",
      "explanation": "..."
    },
    {
      "id": "q3",
      "type": "short_answer",
      "topic": "...",
      "difficulty": "leicht",
      "points": 2,
      "prompt": "...",
      "accepted_answers": ["<Antwort1>", "<Antwort2 (Variante)>"],
      "case_sensitive": false,
      "trim_whitespace": true,
      "explanation": "..."
    }
  ]
}
```

## Regeln

1. **`topic` konsistent**: Innerhalb eines Tests immer **identisch schreiben** (z.B. immer `"Quadratische Gleichungen"`, nicht mal `"Quadrat. Gleichungen"`). Dieses Feld wird für die Lücken-Analyse genutzt.
2. **`id` pro Frage eindeutig**: `q1`, `q2`, …
3. **`choices.id`**: Buchstaben `a`, `b`, `c`, `d` (innerhalb einer Frage eindeutig).
4. **`correct`** verweist auf die `choices.id`-Werte. Bei `single_choice` genau 1 Eintrag, bei `multi_choice` mind. 1.
5. **`points`**: leichte Fragen 1–2 Punkte, mittlere 2–3, schwere 4–5.
6. **`accepted_answers`** bei short_answer: alle plausiblen Schreibweisen aufnehmen (z.B. `["19", "x=19", "x = 19"]`).
7. **Schwierigkeitsmischung**: ca. 40% leicht, 40% mittel, 20% schwer.
8. **Sprache**: Deutsch — außer bei Fach `Englisch`, dort die Aufgabenstellung gemischt (Aufgabe auf Englisch, Hinweise wenn nötig auf Deutsch).
9. **Mathe**: Wenn eine Formel sauber dargestellt werden soll, das LaTeX in `prompt_math` (z.B. `"\\frac{x+3}{2} = 7"`), die textuelle Erklärung in `prompt`.
10. **Keine externen Bilder**, alles textuell beschreibbar.

---

## TODO MATTHIAS — Eigener Stil

Hier kannst du eigene Hinweise an die KI ergänzen, damit Fragen besser zu Clemens und seiner Schule passen. Beispiele:

- _"Schreibstil: Du-Form, freundlich, keine Fremdwörter ohne Erklärung."_
- _"Mathe: Lehrer XYZ legt Wert auf saubere Äquivalenzumformungen — bei mittleren/schweren Fragen die Schritte in 'explanation' nennen."_
- _"Englisch: Vokabular auf Niveau A2/B1 halten."_
- _"Geschichte: Schwerpunkt auf das Schulbuch ABC (Kapitel Industrialisierung)."_

Trage hier dein eigenes Stil-Briefing ein:

```
<dein Stil-Briefing hier>
```

---

## Anhängen am Ende des Prompts

```
Fach: <z.B. Mathe>
Thema: <z.B. Quadratische Gleichungen — Mitternachtsformel>
Anzahl Fragen: <z.B. 10>
Verteilung (optional): <z.B. 3 leicht, 5 mittel, 2 schwer>
```

Dann auf "Senden". Die Antwort als `.json`-Datei speichern (z.B. `mathe-mitternachtsformel.json`) und über den **Import**-Button in der App laden.

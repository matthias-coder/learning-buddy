# Phase 9 — Schul-Kontext & personalisierte Test-Erstellung (Design Spec)

**Status:** Draft, awaiting user approval
**Datum:** 2026-05-13
**Vorgänger-Phase:** 8 (Test bauen)
**Nachfolger-Kandidaten:** Daily-5 / Spaced Repetition, Foto-OCR, Multi-Device-Sync, Schuljahres-aware Aggregate

## 1. Zweck & Motivation

Heute sind "8. Klasse" und "Realschule" an zwei Stellen hartcodiert: im Einleitungssatz von `examples/PROMPT-FOR-AI.md` und im JSON-Schema (`"grade": 8`, `"school_type": "Realschule"`). Das bedeutet:

- Wenn Clemens nächstes Jahr in die 9. Klasse kommt, generiert die App weiter Tests für die 8. Klasse — der Schwierigkeitsgrad passt nicht mehr.
- Wenn ein Geschwisterkind oder Cousin (Gymnasium, andere Klassenstufe) ein Profil bekommt, ist der Test ebenfalls falsch geeicht.
- Bundesland-spezifische Lehrplan-Nuancen werden gar nicht angesprochen.

Phase 9 schließt die Lücke, indem fünf Profil-Felder den Schul-Kontext personifizieren und der Prompt-Assembler sie in ein Template substituiert.

**Zielnutzer:** Matthias (pflegt das Profil), Clemens (sieht den personalisierten Prompt).

**Bewusst nicht in Phase 9** *(future work)*:
- Foto-OCR vom Schulplan-Aushang (User-Entscheidung: zurückgestellt)
- Direkte API-Calls zu Claude/OpenAI (User-Entscheidung: zurückgestellt)
- Schuljahres-aware Phase-7-Aggregate (z. B. Zeugnis-Schätzung nur für aktuelles Schuljahr) — separate spätere Phase
- Daily-5 / Spaced Repetition
- Multi-Device-Sync

## 2. Datenmodell — Migration 008

Fünf neue nullable Spalten auf der bestehenden `users`-Tabelle. Keine neue Tabelle, kein FK-Geflecht.

```sql
-- Phase 9: Schul-Kontext pro User
ALTER TABLE users ADD COLUMN grade INTEGER;        -- 5..13, oder NULL wenn ungesetzt
ALTER TABLE users ADD COLUMN school_type TEXT;     -- 'Hauptschule' | 'Realschule' | 'Gymnasium' | freier Text
ALTER TABLE users ADD COLUMN bundesland TEXT;      -- 16 BL + freier Text
ALTER TABLE users ADD COLUMN school_name TEXT;     -- frei (z.B. "Heinrich-Heine-Realschule")
ALTER TABLE users ADD COLUMN school_year TEXT;     -- "YYYY/YY" z.B. "2025/26"
```

**Begründungen:**
- Alle Felder nullable, kein Backfill nötig. Bestehender User Clemens bleibt mit NULL — die UI macht das sichtbar und die Hart-Validierung (siehe Akzeptanzkriterien §9 #4) drängt zum Ausfüllen.
- `grade INTEGER` statt `TEXT`, damit Zahlen-Vergleiche in zukünftigen Features (Auto-Upgrade beim Schuljahres-Wechsel) trivial sind.
- `school_type` als TEXT (nicht ENUM/CHECK), damit auch "Andere…"-Werte gespeichert werden können.

**Migrations-Falle**: SQLite verbietet `ALTER TABLE ADD COLUMN` mit FK + non-NULL-Default. Alle 5 Spalten sind nullable → kein Problem.

## 3. Code-Struktur

### 3.1 Neues Datamodell-Modul

`src/school_test_engine/prompt_builder/school_context.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from ..ui._layouts import row_get

BUNDESLAENDER = [
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg",
    "Bremen", "Hamburg", "Hessen", "Mecklenburg-Vorpommern",
    "Niedersachsen", "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland",
    "Sachsen", "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen",
]

SCHOOL_TYPES = ["Hauptschule", "Realschule", "Gymnasium"]


@dataclass(frozen=True)
class SchoolContext:
    grade: int | None
    school_type: str | None
    bundesland: str | None
    school_name: str | None
    school_year: str | None

    @classmethod
    def from_user_row(cls, row: Any | None) -> "SchoolContext":
        if row is None:
            return cls(None, None, None, None, None)
        return cls(
            grade=_coerce_int(row_get(row, "grade")),
            school_type=row_get(row, "school_type"),
            bundesland=row_get(row, "bundesland"),
            school_name=row_get(row, "school_name"),
            school_year=row_get(row, "school_year"),
        )

    def is_minimally_complete(self) -> bool:
        """True if grade and school_type are both set (the hard-required pair)."""
        return self.grade is not None and bool(self.school_type)


def _coerce_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
```

### 3.2 Repository-Erweiterung

`storage/users_repo.py` — `update_user` bekommt fünf neue Sentinel-Parameter (gleiches Muster wie `ai_style_briefing` in Phase 8):

```python
def update_user(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    name: str | None = None,
    avatar: str | None = None,
    avatar_image=_SENTINEL,
    birthday=_SENTINEL,
    ai_style_briefing=_SENTINEL,
    grade=_SENTINEL,
    school_type=_SENTINEL,
    bundesland=_SENTINEL,
    school_name=_SENTINEL,
    school_year=_SENTINEL,
    sort_order: int | None = None,
) -> None:
```

`create_user` bleibt unverändert — neue Profile starten mit NULL, User editiert nach Anlage.

### 3.3 Assembler-Erweiterung

`prompt_builder/assembler.py` — `assemble_prompt` bekommt einen neuen Parameter `school_context`:

```python
def assemble_prompt(
    subject: str,
    topics: list[str],
    count: int,
    distribution: str,
    style_briefing: str | None,
    school_context: SchoolContext | None = None,
) -> str:
```

Substitution-Phasen (im Code in dieser Reihenfolge):

1. **Token-Replace**: alle `{{grade}}`, `{{school_type}}`, `{{bundesland}}`, `{{school_name}}`, `{{school_year}}` werden durch User-Werte ersetzt; bei NULL durch sichtbare Marker `<Klasse>`, `<Schultyp>`, etc.

2. **Phrase-Stripping bei NULL-Gruppen**:
   - Sub-Pattern `" in {{bundesland}}"` (mit führendem Space) wird komplett entfernt wenn `bundesland is None`
   - Sub-Pattern `" (Schule: {{school_name}}, Schuljahr {{school_year}})"` wird komplett entfernt wenn beide NULL sind
   - Wenn nur eines der beiden gesetzt ist: trotzdem komplett strippen — wir vermeiden inkonsistente Halb-Sätze. Future improvement: granular handhaben.

Die Reihenfolge (Strip vor Token-Replace) ist wichtig: Wenn `bundesland=None`, sollen wir nicht erst `{{bundesland}}` durch `<Bundesland>` ersetzen und dann die Phrase strippen — wir strippen direkt bei NULL.

Implementierungsskizze:

```python
def _apply_school_context(text: str, ctx: SchoolContext | None) -> str:
    if ctx is None:
        ctx = SchoolContext(None, None, None, None, None)

    # Phase A: Phrase-Strip bei NULL-Gruppen
    if ctx.bundesland is None:
        text = text.replace(" in {{bundesland}}", "")
    if ctx.school_name is None and ctx.school_year is None:
        text = text.replace(" (Schule: {{school_name}}, Schuljahr {{school_year}})", "")

    # Phase B: Token-Replace mit Markern für übrig gebliebene NULLs
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
```

Diese Funktion wird in `assemble_prompt` vor dem Append der Tail-Sektion auf den Base-Text angewendet.

### 3.4 Markdown-Template-Änderungen

`examples/PROMPT-FOR-AI.md` wird einmalig angepasst:

**Aufgabe-Sektion (war hardcoded "8. Klasse Realschule"):**
```
Du erzeugst einen Übungs-Test für die **{{grade}}. Klasse {{school_type}}** in **{{bundesland}}** (Schule: {{school_name}}, Schuljahr {{school_year}}). Antworte ausschließlich mit gültigem JSON…
```

**JSON-Schema-Sektion (war hardcoded `"grade": 8` / `"school_type": "Realschule"`):**
```json
"grade": {{grade}},
"school_type": "{{school_type}}",
```

(Beide Token-Vorkommen werden zur Laufzeit substituiert.)

### 3.5 UI — Profile-Manager-Erweiterung

Im `_ProfileEditDialog` kommt eine neue Sektion **"Schul-Kontext"** zwischen dem bestehenden Birthday-Block und dem Stil-Briefing-Block (Phase 8). Aufbau:

```python
# Schul-Kontext (Phase 9)
ctx_label = QLabel("Schul-Kontext")
ctx_label.setStyleSheet("color: #4a4538; font-weight: 500; padding-top: 8px;")
outer.addWidget(ctx_label)

ctx_form = QFormLayout()
ctx_form.setSpacing(8)

# Grade
self.grade_combo = QComboBox()
self.grade_combo.addItem("—", None)   # NULL-Option
for g in range(5, 14):
    self.grade_combo.addItem(f"Klasse {g}", g)
ctx_form.addRow("Klassenstufe:", self.grade_combo)

# School type
self.school_type_combo = QComboBox()
self.school_type_combo.addItem("—", None)
for st in SCHOOL_TYPES:
    self.school_type_combo.addItem(st, st)
self.school_type_combo.addItem("Andere…", "__OTHER__")
self.school_type_combo.activated.connect(self._on_school_type_activated)
ctx_form.addRow("Schultyp:", self.school_type_combo)

# Bundesland
self.bundesland_combo = QComboBox()
self.bundesland_combo.addItem("—", None)
for bl in BUNDESLAENDER:
    self.bundesland_combo.addItem(bl, bl)
self.bundesland_combo.addItem("Andere…", "__OTHER__")
self.bundesland_combo.activated.connect(self._on_bundesland_activated)
ctx_form.addRow("Bundesland:", self.bundesland_combo)

# School name
self.school_name_edit = QLineEdit()
self.school_name_edit.setPlaceholderText("z. B. Heinrich-Heine-Realschule")
ctx_form.addRow("Schul-Name:", self.school_name_edit)

# School year
self.school_year_edit = QLineEdit()
self.school_year_edit.setPlaceholderText("2025/26")
ctx_form.addRow("Schuljahr:", self.school_year_edit)

outer.addLayout(ctx_form)
```

**"Andere…"-Handler** (für Schultyp und Bundesland gleich):

```python
def _on_school_type_activated(self, idx: int):
    if self.school_type_combo.itemData(idx) != "__OTHER__":
        return
    text, ok = QInputDialog.getText(
        self, "Schultyp eingeben", "Eigener Schultyp:",
    )
    if ok and text.strip():
        # Add custom value, select it
        custom = text.strip()
        # Insert before "Andere…" (which is at last position)
        last_idx = self.school_type_combo.count() - 1
        self.school_type_combo.insertItem(last_idx, custom, custom)
        self.school_type_combo.setCurrentIndex(last_idx)
    else:
        # User cancelled — revert to first ("—")
        self.school_type_combo.setCurrentIndex(0)
```

**`ProfileValues` dataclass** erweitert sich um 5 neue Felder. **`values()`** liest aus den Combos via `currentData()` und aus den LineEdits.

**`ProfileManagerPage._edit`** reicht alle 5 Felder durch zu `users_repo.update_user` (mit Sentinel-Disambiguierung: `None` heißt "Set NULL", weglassen heißt "behalten" — aber hier setzen wir immer, daher direkt None übergeben).

### 3.6 PromptBuilderPage-Integration

- `PromptBuilderPage.show_for()` lädt zusätzlich zu `ai_style_briefing` auch den `SchoolContext` aus dem User-Row
- Neue Preview-Zeile **über** dem bestehenden Stil-Briefing-Row:
  ```
  Schul-Kontext: 8. Klasse Realschule · Hessen · Schuljahr 2025/26   [Profil bearbeiten]
  ```
  Layout: QLabel (links) mit dem zusammengefassten Kontext + Edit-Button (rechts).
- Bei `ctx.is_minimally_complete() == False`: Label wird rot eingefärbt und zeigt: `⚠ Schul-Kontext unvollständig — fülle Klasse und Schultyp im Profil aus`
- `_rebuild_prompt()` ruft `assemble_prompt(..., school_context=ctx)` auf
- **Hart-Validierung**: Wenn `ctx.is_minimally_complete()` False zurückgibt, wird der Copy-Button greyed-out (zusätzlich zur bestehenden Distribution-Validierung). Status-Label am Copy-Button-Bereich erklärt: `Schul-Kontext unvollständig`.

### 3.7 Tests

#### Unit (TDD)
- `test_migration_008.py`: 5 Tests (jede Spalte existiert + ist nullable)
- `test_school_context.py`:
  - `from_user_row(None)` → alle None
  - `from_user_row` mit vollständigem Row
  - `from_user_row` mit partial Row
  - `is_minimally_complete()` True/False-Logik
  - `_coerce_int` mit Edge-Cases (None, "abc", 8, "8")
- `test_users_repo_school_context.py` (oder bestehende test_users_repo.py erweitern):
  - 5 neue Felder können gesetzt werden (set, clear-with-None, omit-leaves)
- `test_prompt_assembler_school_context.py`:
  - Vollständiger Context → "8. Klasse Realschule" + "in Hessen" + "(Schule: …, Schuljahr …)" alles drin
  - `grade=None, school_type=None` → "<Klasse>. Klasse <Schultyp>" sichtbar als Marker
  - `bundesland=None` → "in <Bundesland>"-Phrase wird gestrippt
  - `school_name=None, school_year=None` → "(Schule: …, Schuljahr …)"-Phrase wird gestrippt
  - Schema-Block-Substitution: `"grade": 8` und `"school_type": "Realschule"` im Output

#### Smoke (UI)
- ProfileManagerEditDialog: Felder rendern, "Andere…" öffnet InputDialog, Werte speichern via update_user
- PromptBuilderPage: Kontext-Preview rendert, Hart-Validierung disabled Copy-Button bei incomplete

#### Manuell (Phase-9-Abschluss)
- Clemens-Profil auf "8 · Realschule · Hessen · Heinrich-Heine · 2025/26" setzen
- PromptBuilderPage öffnen → Output enthält alle 4 Werte
- Profil auf "Klasse=NULL" setzen → Copy disabled, rote Warnung in Preview

## 4. Edge Cases

| Fall | Verhalten |
|------|-----------|
| Bestehender User Clemens hat alle 5 Felder NULL | Profile-Edit-Dialog zeigt "—" in Combos, leere LineEdits. Prompt-Output zeigt `<Klasse>`/`<Schultyp>`-Marker. Copy-Button disabled. |
| User wählt "Andere…" und cancelt InputDialog | Combo springt zurück auf "—" (NULL) |
| Schultyp = "Andere…" mit freiem Text "Berufsschule" | Wird wörtlich in Prompt eingesetzt + im Combo gemerkt |
| Schuljahr-Format-Validation | Keine Validierung — User-Verantwortung. Text wird wörtlich in Prompt eingesetzt. |
| `grade` als String "8" in DB statt int | `SchoolContext._coerce_int` coerced sauber |
| Profile-Wechsel während PromptBuilderPage offen | `user_changed`-Signal → Page reloadet inkl. neuem Kontext |
| User löscht Profil | Cascade greift wie bisher; keine neuen FK-Ketten |
| Markdown-Template hat noch alte hardcoded "8. Klasse" Stelle die NICHT als Token markiert ist | Substitution greift nicht; KI sieht "8" wörtlich — daher: Template einmalig sauber auf alle Tokens anpassen, Tests verifizieren |

## 5. Akzeptanzkriterien

Phase 9 ist fertig wenn:

1. Migration 008 läuft sauber, 5 neue Spalten existieren auf `users`.
2. Profile-Edit-Dialog hat funktionierende Schul-Kontext-Sektion (Klasse-Combo 5–13, Schultyp-Combo mit 3 vordefinierten + "Andere…", Bundesland-Combo mit 16 BL + "Andere…", Schul-Name LineEdit, Schuljahr LineEdit).
3. "Andere…"-Klick öffnet QInputDialog, Wert wird gespeichert + im Combo gemerkt.
4. `users_repo.update_user` persistiert alle 5 Felder; round-trip via `get_user` liefert die Werte.
5. `examples/PROMPT-FOR-AI.md` wurde mit `{{token}}`-Placeholdern aktualisiert (Aufgabe-Satz + JSON-Schema-Block).
6. `assemble_prompt` substituiert alle Tokens; NULL-Felder werden durch `<Marker>` ersetzt; NULL-Gruppen (Bundesland, Schule+Schuljahr) werden komplett aus der Phrase entfernt.
7. PromptBuilderPage zeigt Kontext-Preview-Zeile mit Edit-Link.
8. **Hart-Validierung**: Copy-Button greyed-out wenn `grade` oder `school_type` NULL.
9. Alle bestehenden Tests grün (152/152), neue Unit-Tests grün.
10. Manueller End-to-End: Clemens-Profil ausfüllen → Prompt enthält alle Werte → Kopieren funktioniert → JSON-Antwort von Claude hat richtige grade/school_type-Werte.

## 6. Nicht-Ziele

- Foto-OCR vom Schulplan-Aushang
- Direkte API-Calls zu Claude/OpenAI
- Schuljahres-aware Phase-7-Aggregate (Zeugnis-Schätzung nur aktuelles Schuljahr)
- Auto-Upgrade der Klassenstufe beim Schuljahres-Wechsel (manuell vom User pflegen)
- Pro-Fach-Lehrer-Notizen (separate Phase)
- Daily-5 / Spaced Repetition
- Multi-Device-Sync

## 7. Risiken

- **Markdown-Drift**: Wenn jemand `PROMPT-FOR-AI.md` umstrukturiert (z. B. den Aufgabe-Satz umformuliert), bricht die Phrase-Strip-Logik. Mitigation: Tests verifizieren genau die erwarteten Sub-Patterns; bei Mismatch greift kein Strip, aber Tokens werden trotzdem ersetzt.
- **Halb-leerer Kontext**: Wenn `school_name` gesetzt aber `school_year` NULL ist (oder umgekehrt), strippen wir trotzdem die ganze Klammer. Akzeptiert für Phase 9; granular handhaben käme als Optimierung später.
- **Combo-Editier-Lock-In**: Mit `setEditable(False)` kann der User keine freien Werte tippen — er muss "Andere…" klicken. Etwas mehr UX-Reibung, aber verhindert Phase-8-Subject-Switch-Bugs.
- **Sortierung der Bundesländer**: Alphabetisch ist die einzig sinnvolle Reihenfolge bei 16 Optionen. Sonst Inkonsistenz.

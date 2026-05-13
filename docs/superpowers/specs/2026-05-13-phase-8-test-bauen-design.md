# Phase 8 — Test bauen (Design Spec)

**Status:** Draft, awaiting user approval
**Datum:** 2026-05-13
**Vorgänger-Phase:** 7 (Schul-Cockpit)
**Nachfolger-Kandidaten:** Phase 9 (Daily-5 / Spaced Repetition), Phase 10 (Foto-Import / OCR)

## 1. Zweck & Motivation

Phase 7 schloss den Schleifenkreis um echte Schul-Klassenarbeiten. Was noch fehlt: **die Schritte vor dem Üben sind manuell**. Heute muss Matthias:

1. `examples/PROMPT-FOR-AI.md` öffnen
2. Inhalt in Claude/GPT/Gemini einfügen
3. Fach/Thema/Anzahl unten ergänzen
4. Stil-Briefing-Platzhalter ausfüllen
5. JSON-Antwort als Datei speichern
6. Über Import-Wizard in die App laden

Phase 8 verkürzt das auf **drei Schritte aus der App heraus**: Formular ausfüllen → Prompt-Text kopieren → bei KI einfügen → JSON zurück → Import.

**Killer-Verbindung zu Phase 7:** Die ExamCard auf dem Hauptmenü hat die Topics einer kommenden Klassenarbeit. Ein "✨ Test bauen"-Button füllt das Generator-Formular mit diesen Topics vor — Clemens muss nicht mehr abschreiben.

**Zielnutzer:** Sowohl Matthias (erstellt die Tests) als auch Clemens (im KA-Vorbereitungs-Flow).

**Bewusst nicht in Phase 8** *(future work)*:
- Direkte API-Calls zu Claude/OpenAI (Keys, Kosten, Risk)
- Daily-5 / Spaced Repetition (eigene Phase)
- Prompt-Historie als Liste (nur "letzter pro Fach")
- Pro-Fach-Stil-Briefing (nur Profil-global)
- Foto-Import von Schulbuch / Schulplan (Phase 9 oder 10)

## 2. Datenmodell — Migration 007

Zwei kleine Erweiterungen, kein neues Domänen-Objekt:

```sql
-- Phase 8: User-spezifischer KI-Stil-Hinweis
ALTER TABLE users ADD COLUMN ai_style_briefing TEXT;

-- Phase 8: "Letzter Prompt pro Fach"-Vorschlag-Speicher
CREATE TABLE IF NOT EXISTS prompt_drafts (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject     TEXT    NOT NULL,
    last_topic  TEXT,
    last_count  INTEGER NOT NULL DEFAULT 10,
    last_dist   TEXT    NOT NULL DEFAULT 'auto',   -- 'auto' | 'manuell:L-M-S' z.B. 'manuell:3-5-2'
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, subject)
);
```

**Begründungen:**
- `ai_style_briefing` als nullable Spalte auf `users` statt eigene Tabelle: 1:1-Beziehung, kein Bedarf für Mehrfach-Versionen.
- `prompt_drafts` als eigene Tabelle (nicht JSON-Spalte auf `users`), weil:
  - composite primary key sauberer als JSON-Mutationen
  - klare CASCADE-Semantik bei User-Löschung
  - upsert per `INSERT OR REPLACE` trivial

**Migrations-Falle (wie Phase 6 zeigte):** SQLite erlaubt `ALTER TABLE ADD COLUMN` mit FK + non-NULL-Default nicht. `ai_style_briefing` ist nullable → kein Problem.

## 3. Code-Struktur

### 3.1 Neues Domain-Package `prompt_builder/`

Parallel zu `cockpit/`, `study/`, `grading/`, `importer/`.

- `prompt_builder/__init__.py` (leer)
- `prompt_builder/template.py` — lädt `examples/PROMPT-FOR-AI.md`, strippt zwei Sektionen, exponiert `load_base_prompt() -> str`
- `prompt_builder/assembler.py` — `assemble_prompt(subject, topics, count, distribution, style_briefing) -> str` baut den finalen Prompt-Text

**`template.py` Verhalten:**
- Liest `examples/PROMPT-FOR-AI.md` relativ zur Projektwurzel
- Strippt die Sektion `## TODO MATTHIAS — Eigener Stil` (von `## TODO MATTHIAS` bis zum nächsten `---`-Separator)
- Strippt die Sektion `## Anhängen am Ende des Prompts` (bis Datei-Ende)
- Fallback: wenn Datei nicht existiert oder Parsing fehlschlägt → eingebettetes Backup-Template (Kopie des aktuellen Markdown-Inhalts in einer Modul-Konstanten)

**`assembler.py` Verhalten:**
```python
def assemble_prompt(
    subject: str,
    topics: list[str],
    count: int,
    distribution: str,         # 'auto' or 'manuell:3-5-2'
    style_briefing: str | None,
) -> str
```
- Holt `BASE_PROMPT` aus `template.py`
- Wenn `style_briefing`: hängt nach den Regeln eine `## Eigener Stil`-Sektion an
- Hängt am Ende an: `Fach: {subject}\nThema: {topics joined ", "}\nAnzahl Fragen: {count}\nVerteilung: {dist_label}\n`
- `dist_label` für `'auto'` → "automatisch (ca. 40/40/20)"; für `'manuell:3-5-2'` → "3 leicht, 5 mittel, 2 schwer"
- Returns: vollständiger Prompt-Text als String

### 3.2 Neues Repository

- `storage/prompt_drafts_repo.py`
  - `upsert(conn, user_id, subject, *, last_topic, last_count, last_dist)` — INSERT OR REPLACE
  - `get(conn, user_id, subject) -> sqlite3.Row | None`
  - `list_for_user(conn, user_id) -> list[Row]` (nicht in Phase 8 verwendet, aber convenient)

### 3.3 Erweiterungen bestehender Module

**`storage/users_repo.py`** — `update_user` bekommt einen neuen Parameter:
```python
def update_user(
    conn, user_id, *, name=None, avatar=None,
    avatar_image=_SENTINEL, birthday=_SENTINEL,
    ai_style_briefing=_SENTINEL,   # NEW
    sort_order=None,
) -> None
```
Sentinel-Pattern konsistent mit bestehenden Feldern.

**`storage/__init__.py`** — falls Repos dort re-exported sind (z. B. wie in `from school_test_engine.storage import users_repo`), folgt `prompt_drafts_repo` demselben Muster.

### 3.4 Neue Page — `ui/pages/prompt_builder.py`

Struktur:
```
PromptBuilderPage(QWidget)
├── Header (← Zurück + Eyebrow + Title + [📋 Kopieren])
├── Form-Bereich
│   ├── QHBoxLayout: Fach-Combo + Anzahl-SpinBox
│   ├── QLabel "Themen (eine Zeile = ein Topic)"
│   ├── QPlainTextEdit (4 Zeilen sichtbar)
│   ├── QHBoxLayout: Verteilungs-Modus (Radio "auto" / "manuell" + 3 SpinBoxes)
│   ├── QLabel + Hinweis-Box "Stil aus Profil: …" + Edit-Link
├── QFrame "Generierter Prompt" (Separator)
└── QPlainTextEdit (read-only, big, scrollable, monospaced)
```

API:
```python
class PromptBuilderPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection)
    def reload(self) -> None
    def show_for(self, subject: str | None = None, topics: list[str] | None = None) -> None
```

**Live-Build:** Jedes editierbare Feld (Fach-Combo, Anzahl-SpinBox, Topics-PlainTextEdit, Verteilung-Radio, Manuell-SpinBoxes) emittiert `textChanged`/`valueChanged`/`toggled` → ruft `_rebuild_prompt()`, das `assemble_prompt(...)` aufruft und den Read-Only-Textarea aktualisiert. Performance-Hinweis: bei ~3 KB Prompt-Text kein Throttling nötig.

**Auto-Fill bei Page-Open:**
1. `reload()` oder `show_for()` liest `users.ai_style_briefing` und aktualisiert das Stil-Briefing-Preview
2. Wenn `show_for(subject, topics)` mit Argumenten aufgerufen: setzt Fach + Topics direkt aus Args
3. Sonst: nimmt aktuelle Fach-Combo-Selection (default `SUBJECTS_ALL[0]`), liest `prompt_drafts.get(user_id, subject)` → füllt Topic/Count/Dist
4. Bei Fach-Wechsel im Combo: lädt erneut `prompt_drafts.get(user_id, neues_subject)`

**Auto-Save:**
- Vor `Kopieren`-Klick: upsert in `prompt_drafts`
- Bei Page-Verlassen (`hideEvent`): upsert in `prompt_drafts`

**Copy-Button:**
```python
QApplication.clipboard().setText(self.output_view.toPlainText())
self._show_status("Kopiert ✓", duration_ms=2000)
```

### 3.5 ExamCard-Erweiterung (`widgets/exam_card.py`)

Bestehendes `practice_clicked = Signal(int)`-Signal wird in Phase 8 verkabelt.

**UI-Änderung im Bottom-Action-Bereich:**
Aktueller Code:
```python
if event_data.linked_assessment_id is None:
    grade_btn = ... "Note eintragen"
    actions.addWidget(grade_btn)
else:
    done = Pill("Note erfasst ✓", "tea")
    actions.addWidget(done)
```

Neu:
```python
if event_data.linked_assessment_id is None:
    practice_btn = QPushButton("✨ Test bauen")
    practice_btn.setObjectName("primary")
    practice_btn.clicked.connect(lambda: self.practice_clicked.emit(self.event_id))
    actions.addWidget(practice_btn)

    grade_btn = QPushButton("Note eintragen")
    grade_btn.setObjectName("text")
    grade_btn.clicked.connect(lambda: self.enter_grade_clicked.emit(self.event_id))
    actions.addWidget(grade_btn)
else:
    done = Pill("Note erfasst ✓", "tea")
    actions.addWidget(done)
```

Note-Button rutscht von `primary` auf `text`-Style, weil "Test bauen" jetzt die Primary-Action ist (im Vorbereitungs-Modus).

### 3.6 Profile-Manager-Erweiterung (`pages/profile_manager.py`)

Im Profile-Edit-Dialog kommt ein neues Form-Row:
- Label: "KI-Stil-Hinweis (optional)"
- Widget: `QPlainTextEdit`, maxHeight ~120px
- Placeholder: "z. B. „Schreibstil: Du-Form, freundlich.\nMathe: saubere Äquivalenzumformungen in der Erklärung.""
- Wird in `users_repo.update_user(..., ai_style_briefing=text or None)` gespeichert
- Beim Öffnen des Edit-Dialogs: wird aus `users.ai_style_briefing` gefüllt

### 3.7 MainWindow + Menu-Erweiterung

**`ui/main_window.py`:**
- Neuer Page-Slot: `self.prompt_builder_page = PromptBuilderPage(self, conn)`
- Hinzufügen zur Stack-Registration
- Neue Methode:
  ```python
  def show_prompt_builder(self, subject: str | None = None, topics: list[str] | None = None) -> None:
      self.prompt_builder_page.show_for(subject, topics)
      self.stack.setCurrentWidget(self.prompt_builder_page)
  ```

**`ui/pages/menu.py`:**
- Top-Bar bekommt **dritten** Action-Button: `📝 Test bauen` (links von Termine/Noten)
- Wenn ExamCard `practice_clicked` emittiert: `MenuPage._on_practice_clicked(event_id)` → liest Event, ruft `self.window.show_prompt_builder(subject=ev["subject"], topics=json.loads(ev["topics"]))`

## 4. UI-Detail: Verteilungs-Logik

Verteilungs-Modus = Radio mit zwei Optionen:

**Auto (Default):** Im Prompt erscheint `Verteilung: automatisch (ca. 40/40/20)`. Nutzt Regel #7 aus dem Markdown.

**Manuell:** Drei SpinBoxes (leicht, mittel, schwer) werden enabled, sonst greyed-out. Bei Eingabe:
- Live-Validierung: Summe muss `count`-Wert ergeben
- Wenn Summe ≠ count: Warn-Label "Summe 8 ≠ Anzahl 10 — passe an" rot eingefärbt + Copy-Button greyed-out + Prompt-Output zeigt `Verteilung: <inkonsistent>` statt einer konkreten Zahl
- Wenn Summe == count: Copy-Button aktiv, Prompt-Output zeigt `Verteilung: 3 leicht, 5 mittel, 2 schwer`

## 5. Prompt-Source-of-Truth — Template-Parsing

`prompt_builder/template.py` liest `examples/PROMPT-FOR-AI.md` und strippt zwei klar definierte Sektionen:

```python
def load_base_prompt() -> str:
    path = PROJECT_ROOT / "examples" / "PROMPT-FOR-AI.md"
    if not path.exists():
        return BACKUP_TEMPLATE
    raw = path.read_text(encoding="utf-8")
    # Strippe ## TODO MATTHIAS Sektion (bis zum nächsten '---')
    raw = _strip_section(raw, marker="## TODO MATTHIAS", until="---")
    # Strippe ## Anhängen am Ende Sektion (bis Datei-Ende)
    raw = _strip_section(raw, marker="## Anhängen am Ende", until=None)
    return raw.strip()
```

Tests stellen sicher:
- Stripping entfernt die TODO-Sektion
- Stripping entfernt die "Anhängen"-Sektion
- Restliche Sektionen (Aufgabe, Schema, Regeln) bleiben intakt
- Fallback funktioniert wenn Datei fehlt

## 6. Tests

### Unit (TDD-Pflicht)
- `test_migration_007.py`: 4 Tests (Spalte existiert, Tabelle existiert, FK CASCADE, Idempotenz)
- `test_prompt_drafts_repo.py`: upsert/get/list_for_user + UNIQUE-Constraint
- `test_users_repo_style_briefing.py` (oder erweitern): Sentinel-Pattern für `ai_style_briefing`
- `test_prompt_template.py`: Stripping korrekt, Fallback funktioniert
- `test_prompt_assembler.py`:
  - Mit/ohne Style-Briefing
  - Auto vs Manuell-Mode
  - Topics-Liste mit 1/3/0 Elementen
  - Edge: leerer Topic-String

### Smoke (UI)
- `prompt_builder_page` rendert
- Live-Build aktualisiert bei Feld-Änderung
- Copy-Button funktioniert (verifizierbar via `QApplication.clipboard().text()`)
- Auto-Fill funktioniert bei Fach-Wechsel

### Manuell (Phase-8-Abschluss)
- Mathe-Prompt bauen → kopieren → bei Claude.ai einfügen → JSON erhalten → speichern → Import-Wizard → Test in Library

## 7. Edge Cases

| Fall | Verhalten |
|------|-----------|
| `ai_style_briefing` IS NULL | Stil-Sektion wird komplett im Prompt ausgelassen |
| Manuell-Verteilung Summe ≠ Anzahl | Copy-Button disabled, Warn-Label rot, Output zeigt `Verteilung: <inkonsistent>` |
| Topics leer | Output zeigt `Thema: <bitte ergänzen>`; Copy-Button bleibt aktiv (User-Verantwortung) |
| `prompt_drafts` Row fehlt für (user, subject) | Form bleibt auf Defaults (Topic leer, Count 10, Dist auto) |
| `PROMPT-FOR-AI.md` fehlt | Fallback-Backup-Template aus `template.py` |
| User wechselt Profil bei offener Page | `user_changed`-Signal → Page lädt neue Style-Briefing + Drafts |
| User löscht Profil | CASCADE löscht `prompt_drafts` automatisch (FK ON DELETE CASCADE) |
| Sehr lange Topics-Liste (>10) | Funktioniert, Prompt wird länger; keine UI-Limit-Hardcoding |

## 8. Akzeptanzkriterien

Phase 8 ist fertig wenn:

1. Migration 007 läuft sauber auf bestehender DB.
2. Top-Bar des Hauptmenüs hat neuen 📝-Test-bauen-Button, der die PromptBuilderPage öffnet.
3. ExamCard zeigt **beide** Buttons (✨ Test bauen + Note eintragen) wenn keine Note verknüpft.
4. ✨-Test-bauen-Click öffnet PromptBuilderPage mit Fach + Topics der KA vorbefüllt.
5. Live-Build: Änderung in irgendeinem Feld aktualisiert Prompt-Output sofort.
6. Copy-Button kopiert den vollständigen Prompt in die System-Zwischenablage und zeigt "Kopiert ✓".
7. Profile-Manager hat funktionierendes `ai_style_briefing`-Feld; Wert erscheint im Prompt.
8. Auto-Fill: Schließen+Wiederöffnen für selbes Fach lädt zuletzt genutzte Topic/Count/Dist.
9. Cascade: User löschen entfernt zugehörige `prompt_drafts`-Rows.
10. Alle bestehenden 122 Tests bleiben grün; neue Unit-Tests grün; manueller Smoke-Test (Mathe → Claude → JSON → Import → Library) erfolgreich.

## 9. Nicht-Ziele

- Direkte API-Integration (Claude/OpenAI Keys)
- Daily-5 / Quick-Quiz / Spaced Repetition
- Prompt-Historie / Multi-Draft pro Fach
- Pro-Fach-Stil-Briefing
- Foto/OCR-Import
- Prompt-Versionierung
- Multi-Sprach-Prompts (englischsprachige Tests sind via "Englisch"-Fach schon abgedeckt)
- Markdown-Datei-Validierung (wir vertrauen unserem eigenen `PROMPT-FOR-AI.md`)

## 10. Risiken

- **Markdown-Drift**: Wenn Matthias `PROMPT-FOR-AI.md` umstrukturiert (z. B. die `## TODO MATTHIAS`-Überschrift umbenennt), bricht das Stripping. Mitigation: Tests verifizieren das Parsing; bei Failure greift Backup-Template (User merkt ggf. nichts).
- **Topic-Schreibweise-Drift**: Wenn KA-Topic "Funktionen" in einer KA und "Funktion" in einer anderen heißt, sehen die Prompts unterschiedlich aus. Phase 7 hat bereits die Risk gesehen — keine neue Risk in Phase 8.
- **Clipboard-Permission auf Linux**: Manche WMs erfordern explizite Permissions. Test: `QApplication.clipboard().setText(...)` funktioniert in der Praxis; falls Probleme, fallback ist "manuell mit Strg+A Strg+C selektieren".

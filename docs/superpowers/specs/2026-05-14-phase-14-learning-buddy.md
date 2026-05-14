# Phase 14 — Learning Buddy

**Status:** Design / Spec
**Datum:** 2026-05-14
**Vorgängerphase:** Phase 13 (Design-System Consolidation)
**Typ:** Feature-Phase mit vier unabhängigen Tracks (eine kleine Migration für `users.show_keyboard_hints`)

---

## 1. Motivation

Nach Abschluss von Phase 13 ist die App visuell konsistent und funktional vollständig — aber sie heißt noch „Übungstests", lebt im Codebase als „SchoolTestEngine", hat keine echte Identität nach außen. Außerdem fehlen drei Features, die Clemens (und Matthias) das tägliche Üben spürbar erleichtern würden:

1. **Tastaturnavigation** im Runner — aktuell muss man jede Antwort mit der Maus anklicken; bei einem Daily-5 oder längeren Test ist das langsam und unterbricht den Lese-Flow.
2. **Statistik-Visualisierung** — die Zeugnis-Schätzung als große Zahl ist nützlich, aber ein echter Notenverlauf-Chart pro Fach würde Trends sofort sichtbar machen. Die History-Page hat aktuell nur Sparklines, die zu klein sind für ernsthaftes Interpretieren.
3. **PDF-Export** — am Schreibtisch ohne Bildschirm üben (z. B. unterwegs auf Papier), den Lernplan ausdrucken oder einen Zeugnis-Report für Elterngespräch ausgeben — alles aktuell nicht möglich.

Diese Phase bündelt alle vier Tracks in einem Release: „Learning Buddy v1.0".

## 2. Ziel

Eine eigenständig identifizierbare App mit Namen, Tagline und drei neuen tragfähigen Features, die die tägliche Nutzung beschleunigen oder neue Anwendungsfälle (Drucken) ermöglichen.

## 3. Nicht-Ziele

- Kein Onboarding-Wizard (kommt eventuell Phase 15).
- Keine Animations / Transitions.
- Keine externen Chart-Libraries (`QPainter`-konsistent mit `widgets/sparkline.py`).
- Kein neues Datenmodell außer einem nullable BOOLEAN-Flag pro User.
- Kein Schul-Kalender-Sync.
- Kein Dark-Mode.
- Keine i18n (App bleibt deutsch).

## 4. Architektur-Übersicht

```
src/school_test_engine/
├── pdf_export/                   NEU — Package mit 3 Templates
│   ├── __init__.py
│   ├── _common.py                gemeinsame HTML-Helper (Header, CSS)
│   ├── test_sheet.py             Aufgabenblatt mit Lösungs-Seite
│   ├── study_plan.py             Lernplan vor KA
│   └── grade_report.py           Zeugnis-Report mit eingebettetem Chart
├── ui/
│   ├── widgets/
│   │   ├── grade_chart.py        NEU — QPainter-Notenverlauf-Linie
│   │   └── grade_heatmap.py      NEU — QPainter-Heatmap Fach×Wochen
│   ├── keyboard_shortcuts.py     NEU — zentrale Shortcut-Bindings
│   ├── pages/
│   │   ├── runner.py             MOD — keyboard hookup + cheat-sheet
│   │   ├── review.py             MOD — keyboard hookup (Übersicht)
│   │   ├── grades.py             MOD — embed grade_chart + Export-Button
│   │   ├── history.py            MOD — embed grade_heatmap
│   │   ├── menu.py               MOD — Wordmark replacement + Footer
│   │   └── library.py            MOD — PDF-Button pro Test-Card
│   └── ...
├── storage/migrations/
│   └── 010_phase14_keyboard_hints.sql   NEU — adds users.show_keyboard_hints
├── app.py                        MOD — setWindowTitle/AppName/OrgName
└── ...

assets/
├── wordmark-learning-buddy.svg   NEU — Wordmark mit „Learning Buddy" (Fraunces)
└── ... (logomark.svg bleibt)

install-desktop.sh                MOD — neuer Display-Name
```

## 5. Design-Sektionen

### 5.1 Track A — Rebranding

**App-Name:** Learning Buddy
**Tagline:** designed by Matthias

#### Stellen

| Datei / Stelle | Vorher | Nachher |
|---|---|---|
| `app.py` `QApplication.setApplicationName` | `"SchoolTestEngine"` | `"Learning Buddy"` |
| `app.py` `setApplicationDisplayName` | (nicht gesetzt) | `"Learning Buddy"` |
| `app.py` `setOrganizationName` | `"Kessler Family"` | `"Matthias Kessler"` |
| `MainWindow.setWindowTitle` | `"Übungstests"` | `"Learning Buddy"` |
| `pages/menu.py` Top-Bar Wordmark | SVG-`QSvgWidget` mit altem Wordmark | Text-`QLabel "Learning Buddy"` in Fraunces 14pt rechts neben Logomark |
| `pages/menu.py` Footer (NEU) | – | unten kleine `QLabel "designed by Matthias"`, paper-600 grey, 9pt |
| `profile_picker.py` Header-Eyebrow | `"die Kessler Familie"` | bleibt (familiengefärbt) |
| `install-desktop.sh` `.desktop` Name | `"Übungstests"` | `"Learning Buddy"` |
| `install-desktop.sh` `.desktop` GenericName | `"Lernprogramm"` (falls vorhanden) | `"Lernen für die Schule"` |

#### Logo

`assets/logomark.svg` (Kessler-Eichen + Kessel) bleibt erhalten — das ist visuell vom Namen entkoppelt. `assets/wordmark.svg` (falls vorhanden) wird in Top-Bar nicht mehr verwendet; die Wortmarke wird per `QLabel` mit Fraunces gerendert (verhindert Font-Embedding-Probleme in SVG).

### 5.2 Track B — Keyboard-Navigation

**Scope:** RunnerPage (Frage-Bildschirm) + ReviewPage (Übersicht vor Abgabe).

#### Shortcut-Mapping

| Taste | Wirkung | Implementierungs-Hinweis |
|---|---|---|
| `Tab` / `Shift+Tab` | cycelt durch Antwort-Optionen | Qt-Standard, RadioButton/CheckBox `setFocusPolicy(StrongFocus)` |
| `Space` | togglet fokussierte Option | Qt-Standard auf RadioButton/CheckBox; bei Short-Answer = keine Wirkung (Leerzeichen geht ins QLineEdit) |
| `←` / `→` | vorherige / nächste Frage | `QShortcut` auf RunnerPage; identisch zu „← Zurück" und „Weiter →" Buttons |
| `Enter` / `Return` | nächste Frage | gleich wie `→` |
| `M` | togglet Markierung (🚩) | gleich wie `mark_btn.click()` |
| `O` | öffnet Übersicht (Review-Page) | gleich wie `overview_btn.click()` |
| `Esc` | „Zurück zum Menü" mit Save-on-Exit | gleich wie `abort_btn.click()` |

#### Short-Answer-Spezialfall

Wenn die aktuelle Frage type=`short_answer` ist, wird der Fokus automatisch auf das QLineEdit gesetzt (per `_focus_input_widget()` Helper auf RunnerPage). Innerhalb des QLineEdit:
- `Enter` / `Return` verlässt das Feld und triggert „nächste Frage" — über `QShortcut(Qt.Key.Key_Return, runner_page, context=Qt.ApplicationShortcut)` greift das nicht (würde Submission abfangen), daher Lösung: das QLineEdit hat einen eigenen `returnPressed.connect(self._on_next)`-Handler.
- `←` / `→` als Buchstaben-Navigation im Textfeld bleiben Qt-Standard (Cursor bewegen). Für Frage-Navigation MUSS der User Tab raus oder die UI-Buttons nutzen. **Bewusste Entscheidung**: Texteingabe priorisiert.
- `Esc` greift weiterhin (verlässt Modus).

#### Cheat-Sheet

Am unteren Rand des RunnerPage (über den Action-Buttons) ein dezentes Label:

> `Tab Optionen · Space wählen · ←→ Fragen · M markieren · O Übersicht · Esc Menü`

Style: paper-500 grey, Inter 9pt, zentriert. **Per-User togglebar** über ein „Tastatur-Hinweise ausblenden"-Link rechts daneben.

#### Migration 010

```sql
ALTER TABLE users ADD COLUMN show_keyboard_hints INTEGER NOT NULL DEFAULT 1;
```

`users_repo.update_user` bekommt einen `show_keyboard_hints` Sentinel-Parameter (analog zu Phase 8/9 Pattern).

#### Neues Modul

`ui/keyboard_shortcuts.py` exportiert eine Funktion:

```python
def install_runner_shortcuts(
    page: QWidget,
    *,
    on_prev: Callable[[], None],
    on_next: Callable[[], None],
    on_mark: Callable[[], None],
    on_overview: Callable[[], None],
    on_abort: Callable[[], None],
) -> list[QShortcut]:
    """Install Phase-14 keyboard shortcuts on a runner-like page.
    Returns the list of created QShortcut instances (for cleanup/lifetime)."""
```

Tests via `QTest.keyClick(page, Qt.Key.Key_Right)` und Assertion dass der Callback gefeuert hat.

### 5.3 Track C — Charts

**Library:** Custom `QPainter`-Widgets, keine externe Dependency. Pattern konsistent mit existierendem `widgets/sparkline.py`.

#### Widget 1: `widgets/grade_chart.py` — `GradeChart`

Notenverlauf-Liniendiagramm.

```python
class GradeChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self._schriftlich: list[tuple[date, float]] = []
        self._muendlich: list[tuple[date, float]] = []

    def set_data(
        self,
        schriftlich: list[tuple[date, float]],
        muendlich: list[tuple[date, float]],
    ) -> None: ...

    def paintEvent(self, event): ...
```

**Visuelle Spec:**
- X-Achse: Datum, automatisch skaliert auf Daten-Range (mindestens 30 Tage, sonst Datenbereich).
- Y-Achse: Note **1 oben, 6 unten** (invertiert, wie im Zeugnis). Tick-Lines bei 1, 2, 3, 4, 5, 6, paper-300.
- X-Achsen-Labels: Monat-Kürzel (Jan, Feb, …) wenn Range > 90 Tage, sonst Tag.Monat.
- Zwei Linien:
  - schriftlich: clay-orange `#c26a3d`, durchgezogen
  - mündlich: tea-green `#658a47`, durchgezogen
  - Punkte (Kreis-Marker) 6px Radius an jedem Datenpunkt
  - Linie gepunktet (Qt.PenStyle.DotLine) wenn weniger als 2 Datenpunkte einer Kategorie vorhanden
- Wenn beide Kategorien <2 Datenpunkte: Placeholder-Label „Mehr Noten = aussagekräftiger Verlauf" zentriert.
- Legende oben rechts: kleine Kreise + Label (schriftlich · mündlich), Inter 9pt.
- Hover: **Out of scope für Phase 14** (Stretch-Goal — keine Tooltips).

#### Widget 2: `widgets/grade_heatmap.py` — `GradeHeatmap`

Wochen-Heatmap Fach×Zeit.

```python
class GradeHeatmap(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self._weeks: list[date] = []  # Monday of each week, sorted ascending
        self._rows: list[tuple[str, dict[date, float]]] = []  # (subject, {week_start: avg_grade})

    def set_data(
        self,
        weeks: list[date],
        rows: list[tuple[str, dict[date, float]]],
    ) -> None: ...

    def paintEvent(self, event): ...
```

**Visuelle Spec:**
- 8 Spalten = letzte 8 Kalenderwochen (Mo–So) ab `today`.
- Zeilen: alle Fächer mit mindestens einer Note in den letzten 8 Wochen, sortiert alphabetisch.
- Zelle: 40×40px, Innen-Padding 4px, rounded 4px.
- Zelle-Farbe: `note_color(grade)` aus `_subjects.py` (gleich wie GradePill), gemixt mit weiß zu ~70% Sättigung (also pastellig).
- Leere Zelle: paper-100 `#f4efe6`.
- Y-Achse-Labels (Fach): Inter 10pt, rechts ausgerichtet, 80px breit.
- X-Achse-Labels (Wochen): „KW XX", Inter 9pt, paper-600, zentriert über Spalten.
- Legende unten: `■ ≤2,0  ■ ≤3,0  ■ ≤4,0  ■ >4,0  □ keine Note`, Inter 9pt.

**SQL-Aggregation** (in `assessments_repo.py` neue Helper-Funktion):

```python
def heatmap_data(
    conn: sqlite3.Connection, user_id: int, weeks_back: int = 8,
) -> dict[str, dict[date, float]]:
    """Returns {subject: {week_monday: avg_grade}} for the last `weeks_back` weeks."""
```

Implementierung mit `strftime('%Y-%W', assessment_date)` Gruppierung. Performance-Test: bei < 200 Assessments soll Query unter 5ms laufen — kein Caching nötig.

#### Integration

- **Noten-Page** (`pages/grades.py`): Nach `_build_average_hero`, vor der Assessment-Liste, eine neue Section „Notenverlauf" mit Eyebrow + `GradeChart`. Daten kommen aus `assessments_repo.list_by_subject(conn, uid, self._current_subject)`, gefiltert nach `category`.
- **History-Page** (`pages/history.py`): Über der bestehenden Tabelle eine neue Section „Wochen-Übersicht" mit Eyebrow + `GradeHeatmap`. Daten aus `assessments_repo.heatmap_data(conn, uid)`.

### 5.4 Track D — PDF-Export

**Library:** `QPrinter` + `QTextDocument` mit HTML/CSS-Template (konsistent mit Phase 5 Result-Druck).

**Neues Package:** `pdf_export/`

#### Gemeinsames Modul: `pdf_export/_common.py`

```python
HTML_HEADER_TEMPLATE = """
<style>
  body { font-family: 'Inter', sans-serif; color: #1e1b15; }
  h1 { font-family: 'Fraunces', serif; font-size: 24pt; margin: 0; color: #13110c; }
  .eyebrow { font-size: 9pt; color: #6f6757; letter-spacing: 1.5pt; text-transform: uppercase; }
  .wordmark { font-family: 'Fraunces', serif; font-size: 12pt; color: #4a4538; }
  .footer { font-size: 8pt; color: #a89e89; }
  ...
</style>
"""

def render_to_pdf(html: str, output_path: str) -> bool:
    """Render an HTML string to a PDF file at output_path using QPrinter."""

def render_to_bytes(html: str) -> bytes:
    """Render an HTML string to PDF bytes (for tests + embedding)."""
```

#### Template 1: `pdf_export/test_sheet.py`

```python
def export_test_sheet(conn: sqlite3.Connection, test_id: int) -> str:
    """Render a test as a printable worksheet. Returns the HTML string.
    Two-section layout: questions on page 1+, solutions on a separate page."""
```

**Layout:**
- Seite 1 Header: Wordmark „Learning Buddy" + Fach + Datum + leere Linien für „Name: ___" und „Klasse: ___".
- Fragen nummeriert: Frage-Text + ggf. KaTeX (als HTML rendern), dann:
  - **single/multi:** je Antwort-Option ein `○`-Kreis + Option-Text.
  - **short_answer:** zwei Leerzeilen mit Linien zum Selbst-Eintragen.
- Page-break vor „Lösungen"-Sektion (`<div style="page-break-before: always;">`).
- Lösungs-Sektion: gleiche Frage-Nummern + korrekte Antwort + ggf. Erklärung (aus `questions.explanation`-Feld falls vorhanden, sonst nur die Antwort).

**Aufrufstelle:** Library-Page, jedes Test-Card bekommt zusätzlich zu „Starten →" und „…" einen kleinen „PDF"-Button (objectName="text"). Click öffnet `QFileDialog.getSaveFileName(...)` mit Default-Filename `learning-buddy-test-<subject>-<datum>.pdf` und ruft `render_to_pdf(...)`.

#### Template 2: `pdf_export/study_plan.py`

```python
def export_study_plan(conn: sqlite3.Connection, event_id: int) -> str:
    """Render a study plan PDF for an upcoming KA. Returns the HTML string."""
```

**Layout:**
- Header: Wordmark + „LERNPLAN" Eyebrow + KA-Fach + Datum + „in X Tagen".
- Themen aus `events.topics` als Liste, je Topic:
  - Topic-Name (linksbündig)
  - Mastery-Bar (●●○○○ via 5 Unicode-Punkte gefärbt) — aus `cockpit/gaps.py`-Logik oder direkt aus `attempt_questions`-Aggregation
  - „zuletzt N/M richtig" oder „noch nicht geübt" wenn 0 Versuche
- Empfehlungs-Sektion: Sortiert von schwächstem zu stärkstem Topic, mit kurzem Hinweis-Text.

**Aufrufstelle:** ExamCard auf Menu bekommt einen dritten Action-Button „Lernplan PDF" (objectName="text"), zusätzlich zu „Test bauen" und „Note eintragen". Aus EventEditPage in Edit-Mode auch erreichbar (Footer-Button neben „Löschen", text-style).

#### Template 3: `pdf_export/grade_report.py`

```python
def export_grade_report(conn: sqlite3.Connection, user_id: int) -> str:
    """Render a current grade report PDF. Returns the HTML string."""
```

**Layout:**
- Header: Wordmark + User-Name + Schule + „Klasse X · Schuljahr Y" (aus Schul-Kontext) + „Stand: <heute>".
- Pro Fach (alphabetisch):
  - Eyebrow `<FACH>`
  - Zeugnis-Schätzung als große Zahl (Fraunces 32pt)
  - Breakdown „schriftlich X,X · mündlich Y,Y"
  - Notenverlauf-Chart als embedded `<img>` (gerendert via `GradeChart.grab().toImage()` + base64-encode oder Temporary-File)
  - Tabelle aller Assessments: Datum | Art | Note | Notiz
- Footer: „designed by Matthias", paper-600.

**Aufrufstelle:** Noten-Page Top-Bar bekommt „Als PDF" Button (objectName="text") rechts neben „+ Note".

#### File-Save-Workflow

Zentrale Helper-Funktion in `pdf_export/_common.py`:

```python
def save_pdf_with_dialog(parent: QWidget, html: str, default_filename: str) -> bool:
    """Open QFileDialog.getSaveFileName, render PDF if user confirms.
    Returns True on success, False if user cancelled."""
```

Alle drei Aufrufstellen (Library, Menu/EventEdit, Noten) nutzen diesen Helper.

### 5.5 Tests + Akzeptanzkriterien

#### Neue Tests (geschätzt 20)

| Datei | Was wird getestet |
|---|---|
| `test_branding.py` | `QApplication.applicationName()` == „Learning Buddy"; `MainWindow.windowTitle()` enthält „Learning Buddy" |
| `test_keyboard_shortcuts.py` | `install_runner_shortcuts(...)` registriert 6 Shortcuts; `QTest.keyClick(page, Key_Right)` triggert `on_next` |
| `test_runner_keyboard.py` | RunnerPage Integration: `keyClick(Key_Right)` → Index +1 |
| `test_review_keyboard.py` | ReviewPage `keyClick(Key_O)` öffnet Übersicht (oder gleicher Effekt) |
| `test_grade_chart.py` | `GradeChart.set_data(...)` setzt internen State; `paintEvent` läuft ohne Exception; minimum size honored |
| `test_grade_heatmap.py` | analog + `heatmap_data(conn, uid)` SQL-Aggregation liefert korrekte Wochenstart-Daten |
| `test_assessments_heatmap_query.py` | `assessments_repo.heatmap_data` returns dict[subject][week_monday] = avg_grade |
| `test_pdf_test_sheet.py` | `export_test_sheet(conn, test_id)` returns HTML containing all questions; `render_to_bytes(html)` returns bytes starting with `%PDF-` |
| `test_pdf_study_plan.py` | analog für `export_study_plan(conn, event_id)` |
| `test_pdf_grade_report.py` | analog für `export_grade_report(conn, user_id)` |
| `test_migration_010.py` | Migration läuft und fügt Spalte `show_keyboard_hints` mit DEFAULT 1 hinzu |

#### Akzeptanzkriterien

1. ✅ App-Name in Window-Title, App-Metadata, .desktop-File ist „Learning Buddy".
2. ✅ Menu-Page Top-Bar zeigt „Learning Buddy" als Wordmark; Footer zeigt „designed by Matthias".
3. ✅ Logo (Eichen) unverändert.
4. ✅ RunnerPage reagiert auf alle 7 Shortcuts (Tab, Space, ←, →, Enter, M, O, Esc).
5. ✅ Cheat-Sheet ist sichtbar; togglebar via Setting; Setting persistiert in DB.
6. ✅ Noten-Page zeigt `GradeChart` unter GradeHero für aktuelles Fach.
7. ✅ History-Page zeigt `GradeHeatmap` über der Tabelle.
8. ✅ Library-Test-Cards haben „PDF"-Button, der ein druckfertiges Aufgabenblatt + Lösungs-Seite exportiert.
9. ✅ ExamCard und EventEditPage haben „Lernplan PDF"-Aktion, die Themen + Mastery + Empfehlung exportiert.
10. ✅ Noten-Page hat „Als PDF"-Button, der einen Zeugnis-Report mit eingebetteten Charts exportiert.
11. ✅ Migration 010 ist im migrator registriert und läuft idempotent.
12. ✅ Bestehende 256 Tests bleiben grün; ~20 neue Tests grün.

## 6. Risiken & Mitigation

| Risiko | Mitigation |
|---|---|
| `QPainter`-Chart-Code wird groß und fehleranfällig (Achsen-Skalierung, Label-Positionierung) | Test-First: vor `paintEvent` Implementierung den Achsen-Berechnungs-Helper (`_compute_x_range`, `_y_for_grade`) als reine Funktion testen. |
| Wordmark in SVG mit Fraunces-Font: Variable-Font lädt nicht zuverlässig in SVG | Wordmark als `QLabel` mit gesetztem Fraunces-Font und CSS-Color rendern. SVG nur für Logomark (geometrisch, font-frei). |
| `QShortcut` in QLineEdit-Kontext: `Enter` würde Submission abfangen und Cursor-Bewegung blockieren | Für Short-Answer-Fragen: globalen Enter-Shortcut deaktivieren wenn Fokus im QLineEdit ist (per `focusInEvent`/`focusOutEvent` auf dem Edit). Stattdessen `returnPressed.connect(...)` direkt am Edit. |
| PDF mit eingebettetem Chart-Image: `QPainter`-zu-`QImage`-Roundtrip in HTML einbetten ist sperrig | Chart wird via `widget.grab().save(temp_file, "PNG")` als temporäre PNG-Datei gespeichert und im HTML als `<img src="file://...">` referenziert. Nach `render_to_pdf` wird temp_file gelöscht. |
| Migration 010 trifft Test-Fixtures, die `users`-Tabelle manuell mocken | Test-Fixtures nutzen `run_migrations(conn)` durchgehend (Phase 6+ Pattern) — sollte automatisch funktionieren. |
| Tastatur-Cheat-Sheet wirkt überladen | Schlanker Single-Line-String, kompakte Trenner (` · `). Per-User togglebar reduziert Sichtbarkeit für Experten. |
| Heatmap-Performance bei >500 Assessments | Aktuell kein Caching. Wenn nötig: nachträgliche Optimierung via `attempts_repo` SQL-Index. |

## 7. Out of Scope für Phase 14

- Animationen, Chart-Tooltips, Hover-Effekte.
- Onboarding-Wizard für neue Profile (Phase 15?).
- CSV-Export-Verbesserung (Phase 5 reicht).
- Schul-Kalender-Sync (ical/Google).
- Dark-Mode.
- Custom Theming.
- Notification-System (KA-Reminder).
- Lernplan mit auto-generierten Aufgaben (entschieden in Brainstorm: redundant zu Test-Sheet-Export).

## 8. Nachfolge-Phasen (Ideen, nicht zugesagt)

- **Phase 15 — Onboarding-Wizard:** First-Run-Experience für neue Profile (falls Bedarf entsteht).
- **Phase 16 — Notifications & Reminders:** Desktop-Notifications wenn KA in <3 Tagen.
- **Phase 17 — Multi-Device-Sync:** Cloud-Backup der SQLite-DB (z. B. Dropbox-Folder).

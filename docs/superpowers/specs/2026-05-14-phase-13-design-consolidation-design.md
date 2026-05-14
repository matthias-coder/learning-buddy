# Phase 13 — Design-System Consolidation

**Status:** Design / Spec
**Datum:** 2026-05-14
**Vorgängerphase:** Phase 12 (UX Polish)
**Typ:** Pure UI-Refactoring (keine Datenmodell-Änderungen)

---

## 1. Motivation

Nach 12 abgeschlossenen Phasen ist die UI funktional vollständig, aber visuell inkonsistent. UX-Test mit 12 maximierten Screenshots zeigt drei Bruchstellen:

1. **Zwei verbleibende Modal-Dialogs** (`EventDialog`, `AssessmentDialog`) öffnen als separate OS-Fenster mit Default-Qt-Buttons (Cancel/Save mit befremdlichen OS-Icons) — sie passen visuell nicht zum Inline-Page-Pattern, das Phase 12 für `ProfileEditPage` etabliert hat.

2. **Emoji-Icons in UI-Chrome** rendern OS-abhängig (Linux Mint: blauer `👤`-Placeholder trotz `color: #...`-QSS — Color-Emoji ist nicht styling-bar). Top-Bar-Buttons (`📝 Test bauen`, `📅 Termine`, `📊 Noten`), Copy-Button (`📋 Kopieren`), Prompt-Header (`🪄 Generierter Prompt:`) — alle führen visuelle Unruhe ein, die nicht zur ruhigen paper-Ästhetik mit Fraunces-Display-Font passt.

3. **Inkonsistente Button-Styles**: auf der gleichen Seite stehen vier verschiedene Pillows nebeneinander (text-only, outline-pill, filled-orange-pill, mini-pill). Manche `QPushButton`-Instanzen haben keinen `objectName` und fallen auf Default-Qt-Style zurück.

**User-Feedback:** "alles aus einem Guss"; "triff eigene Überlegungen"

## 2. Ziel

Eine konsistente, monochrom-elegante Design-Sprache durchziehen:
- Alle Edit-Workflows als Inline-Pages (kein Modal mehr).
- UI-Chrome strikt text-only — Emoji nur in Content/Feedback (Streaks, Achievements, Status-Indikatoren).
- Jeder `QPushButton` hat genau einen von drei `objectName`s: `primary`, `text`, `danger`.
- Avatar-Placeholder als statisches SVG statt OS-Emoji.

## 3. Nicht-Ziele

- Keine Datenmodell- oder Repo-Änderungen.
- Keine neue Icon-Library (außer dem einen Avatar-SVG).
- Keine komplett-Redesigns der Forms — Field-Layouts bleiben.
- Keine Animations/Transitions.
- Kein Dark Mode.
- Kein lint-Test, der Button-objectName-Regel automatisch enforct (manuelles Audit reicht).

## 4. Architektur-Übersicht

```
src/school_test_engine/ui/
├── pages/
│   ├── event_edit.py           NEU — ersetzt dialogs/event_dialog.py
│   ├── assessment_edit.py      NEU — ersetzt dialogs/assessment_dialog.py
│   ├── events.py               MOD — Callsites umgestellt
│   ├── grades.py               MOD — Callsites umgestellt
│   ├── menu.py                 MOD — Callsites + Emoji-Strip + Button-Audit
│   ├── prompt_builder.py       MOD — Emoji-Strip + Button-Audit
│   ├── profile_edit.py         MOD — Button-Audit
│   └── ...                     MOD — Button-Audit pro Seite
├── widgets/
│   ├── avatar_badge.py         MOD — SVG-Rendering statt 👤
│   ├── profile_card.py         MOD — SVG-Rendering statt 👤
│   └── top_bar.py              MOD — Emoji-Strip
├── dialogs/
│   ├── event_dialog.py         GELÖSCHT
│   └── assessment_dialog.py    GELÖSCHT
└── main_window.py              MOD — show_event_edit / show_assessment_edit

assets/
└── avatar-placeholder.svg      NEU
```

## 5. Design-Sektionen

### 5.1 Modal-Dialogs → Inline-Pages

**Begründung:** Phase 12 hat `_ProfileEditDialog` → `ProfileEditPage` umgebaut und dabei das Inline-Page-Pattern etabliert. Phase 13 zieht es auf die letzten beiden Dialogs durch.

#### EventEditPage (`pages/event_edit.py`)

Aufbau analog zu `ProfileEditPage`:

```
┌──────────────────────────────────────────────────────────┐
│  ← Zurück         TERMIN BEARBEITEN          Speichern   │  (Header)
│                   Mathe Klassenarbeit                    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Fach          [ Mathe         ▼ ]                      │
│  Typ           ( ) Klassenarbeit  (•) Test  ( ) Hausauf. │
│  Datum         [ 2026-05-20 ]                            │
│  Themen        [ ────────────────────────────────────── ]│
│                [                                         ]│
│  Notiz         [ ────────────────────────────────────── ]│
│                                                          │
│  ────────────────────────────────────────────────────── │
│  Löschen                                                 │  (Footer, nur Edit)
└──────────────────────────────────────────────────────────┘
```

**API:**
```python
class EventEditPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection): ...

    def show_for(
        self,
        event_id: int | None,           # None = neu anlegen
        return_to: str = "events",      # "events" | "menu"
    ) -> None:
        """Lädt Daten und zeigt die Seite."""
```

**Buttons:**
- `← Zurück` — `objectName="text"`, navigiert zu `return_to`
- `Speichern` — `objectName="primary"`, ruft `events_repo.create/update`, navigiert zu `return_to`
- `Löschen` — `objectName="danger"`, ruft `events_repo.delete`, navigiert zu `return_to` (nur sichtbar wenn `event_id is not None`)

**Validierung:** Wie bisher in `EventDialog` (Datum + Fach required). Fehlermeldung als kleines Label unter dem Form.

#### AssessmentEditPage (`pages/assessment_edit.py`)

Aufbau analog. Headers: `NOTE EINTRAGEN` / `NOTE BEARBEITEN`.

**Form:** Note-Selector (3×2-Grid bleibt), Fach (Combo), Art (Radio: Klassenarbeit/Test/Sonstiges), Datum, Punkte (`max_points`-Spinner), Notiz (TextEdit).

**API:**
```python
def show_for(
    self,
    assessment_id: int | None,
    return_to: str = "grades",          # "grades" | "menu" | "events"
    prefill_subject: str | None = None,  # für "Note eintragen" aus Termin
    prefill_event_id: int | None = None,
) -> None: ...
```

#### MainWindow-Integration

```python
# in main_window.py
self.event_edit_page = EventEditPage(self, self.conn)
self.assessment_edit_page = AssessmentEditPage(self, self.conn)
self.stack.addWidget(self.event_edit_page)
self.stack.addWidget(self.assessment_edit_page)

def show_event_edit(self, event_id: int | None = None, return_to: str = "events") -> None:
    self.event_edit_page.show_for(event_id, return_to)
    self.stack.setCurrentWidget(self.event_edit_page)

def show_assessment_edit(
    self,
    assessment_id: int | None = None,
    return_to: str = "grades",
    prefill_subject: str | None = None,
    prefill_event_id: int | None = None,
) -> None:
    self.assessment_edit_page.show_for(
        assessment_id, return_to, prefill_subject, prefill_event_id
    )
    self.stack.setCurrentWidget(self.assessment_edit_page)
```

#### Callsite-Migration

| Datei | Vorher (Dialog) | Nachher (Inline-Page) |
|---|---|---|
| `pages/events.py:_add_event` | `EventDialog(...).exec()` | `self.window.show_event_edit(None, "events")` |
| `pages/events.py:_edit_event` | `EventDialog(event_id, ...).exec()` | `self.window.show_event_edit(event_id, "events")` |
| `pages/grades.py:_add_assessment` | `AssessmentDialog(...).exec()` | `self.window.show_assessment_edit(None, "grades")` |
| `pages/grades.py:_edit_assessment` | `AssessmentDialog(a_id, ...).exec()` | `self.window.show_assessment_edit(a_id, "grades")` |
| `pages/menu.py:_on_enter_grade` | `AssessmentDialog(prefill=...)` | `self.window.show_assessment_edit(None, "menu", prefill_subject=..., prefill_event_id=...)` |
| `pages/menu.py:_on_edit_event` | `EventDialog(event_id, ...)` | `self.window.show_event_edit(event_id, "menu")` |

#### Cleanup

- `src/school_test_engine/ui/dialogs/event_dialog.py` **gelöscht**
- `src/school_test_engine/ui/dialogs/assessment_dialog.py` **gelöscht**
- Falls `dialogs/__init__.py` Re-Exports hatte: Imports entfernen.
- `tests/test_event_dialog.py` und `tests/test_assessment_dialog.py` (falls vorhanden) **umgeschrieben** zu `test_event_edit_page.py` / `test_assessment_edit_page.py` — Test-Logik bleibt, nur die unter-Test-stehende Klasse ändert sich.

---

### 5.2 Emoji-Strip aus UI-Chrome

**Begründung:** Color-Emoji ist OS-abhängig und nicht styling-bar. Was unter macOS bunt-elegant aussieht, ist unter Linux Mint blockig blau oder gar nicht da. Auf einer paper-eleganten Oberfläche mit Fraunces-Display ist es immer visueller Lärm.

**Konvention:** Emoji nur dort, wo es **emotional/dekorativ** ist (Achievement-Feedback) — niemals in Buttons oder Section-Headern der UI-Chrome.

#### Entfernt aus

| Ort | Vorher | Nachher |
|---|---|---|
| `widgets/top_bar.py` (Buttons) | `📝 Test bauen` | `Test bauen` |
| `widgets/top_bar.py` | `📅 Termine` | `Termine` |
| `widgets/top_bar.py` | `📊 Noten` | `Noten` |
| `pages/menu.py` ExamCard CTA | `✨ Test bauen` | `Test bauen` |
| `pages/prompt_builder.py` Copy-Btn | `📋 Kopieren` | `Kopieren` |
| `pages/prompt_builder.py` Output-Eyebrow | `🪄 Generierter Prompt:` | `Generierter Prompt` (Eyebrow ohne Doppelpunkt — Convention im Codebase) |

#### Behält Emoji (bewusst!)

| Ort | Inhalt | Begründung |
|---|---|---|
| `pages/menu.py` Daily-5-Card | `🔥 3 Tage in Folge` | Achievement-Decoration, emotional |
| `pages/menu.py` Daily-5 done state | `✓ Heute geschafft` | Universelles Success-Symbol |
| `pages/result.py` (Test-Ergebnis) | `✓` richtig / `✗` falsch | Status-Indikator |
| Status-Labels nach Aktionen | `Kopiert ✓` | User-Feedback |
| `widgets/top_bar.py` Hamburger | `☰` | KEIN Emoji — Unicode-Symbol (U+2630), wird monochrom gerendert. Bleibt. |

#### Avatar-Placeholder als SVG

**Problem:** `AvatarBadge` und `ProfileCard` rendern aktuell `setText("👤")` als Fallback wenn kein Image gesetzt ist. Linux Mint rendert das als blauen Color-Emoji-Glyph, obwohl QSS `color: #6f6757` setzt — Color-Emoji ignoriert `color:`.

**Lösung:** Statisches SVG-Asset `assets/avatar-placeholder.svg`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <!-- Hintergrund-Kreis: paper-50 -->
  <circle cx="50" cy="50" r="50" fill="#f4efe6"/>
  <!-- Kopf: paper-400 -->
  <circle cx="50" cy="38" r="14" fill="#b3a98e"/>
  <!-- Schultern (abgerundetes Trapez): paper-400 -->
  <path d="M22 88 Q22 64 50 64 Q78 64 78 88 Z" fill="#b3a98e"/>
</svg>
```

**Rendering:** `AvatarBadge` und `ProfileCard` bekommen einen `QSvgRenderer`-Pfad als Fallback. Pseudocode:

```python
# in avatar_badge.py
from PySide6.QtSvg import QSvgRenderer

PLACEHOLDER_SVG = Path(__file__).resolve().parents[3].parent / "assets" / "avatar-placeholder.svg"

class AvatarBadge(QWidget):
    def __init__(self, ..., size: int = 64):
        ...
        if image_bytes:
            # bestehender Image-Pfad
            ...
        else:
            # SVG rendern in QPixmap
            renderer = QSvgRenderer(str(PLACEHOLDER_SVG))
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            self.image_label.setPixmap(pixmap)
```

Gleiche Anpassung in `widgets/profile_card.py`.

**Bestehender QSvgWidget-Import**: `pages/profile_picker.py` nutzt schon `QSvgWidget` (logomark.svg) → `PySide6.QtSvg` ist bereits verfügbar.

---

### 5.3 Button-Style-Audit (Theme C)

**Begründung:** Im QSS gibt es genau drei definierte Button-Styles (`#primary`, `#text`, `#danger`, alle mit `min-height: 44px` für Touch). Manche `QPushButton`-Instanzen haben keinen `setObjectName(...)` und fallen auf Default-Qt zurück → die berüchtigten "schmalen grauen Buttons" im UX-Test.

**Konvention (in Code-Comment in `ui/style.qss` festhalten):**

```
Button convention:
- "primary"  Haupt-Aktion einer Seite/Form (orange filled pillow, weiß text)
- "text"     Sekundäre Aktion / Navigation (transparent pillow, hover effect)
- "danger"   Destruktive Aktion (rose-tinted pillow)
Jeder QPushButton im Codebase MUSS einen dieser drei objectName haben.
```

**Audit-Methodik:**

1. `grep -nrE "QPushButton\(" src/school_test_engine/` → Liste aller Erzeugungen.
2. Für jede: 1-3 Zeilen weiter unten muss `setObjectName(` mit einem der drei Werte folgen.
3. Falls fehlt: Entscheidung treffen (welcher Style passt?), `setObjectName(...)` hinzufügen.

**Bekannte Stellen, die geprüft werden müssen** (ohne Anspruch auf Vollständigkeit — vollständige Liste entsteht beim Audit):

- `pages/profile_edit.py` — Foto-auswählen, Foto-entfernen, Geburtstag-löschen
- `pages/events.py` — `+ Termin`-Button, evtl. Filter-Buttons
- `pages/grades.py` — `+ Note`-Button
- `pages/library.py`, `pages/gaps.py`, `pages/history.py` — Filter, Aktion-Buttons
- `pages/exam.py` (Lauf-Modus) — Antwort-Buttons, „Weiter", „Abbrechen"
- `pages/result.py` — „Nochmal", „Zurück"
- `pages/menu.py` — DailyFiveCard-CTA, ExamCard-CTA, Edit-Buttons in Events/Grades-Karten

**Entscheidungs-Heuristik beim Audit:**

| Button-Zweck | objectName |
|---|---|
| Speichern, Erstellen, Starten, Übungstest bauen, „nochmal" | `primary` |
| Zurück, Bearbeiten, Cancel, Filter, „+ Neuer …" | `text` |
| Löschen, Verwerfen, „Profil entfernen" | `danger` |

`+ Neuer Termin` ist Streitfall: in Phase 7 als `text`-Pillow gemacht (Add-Action ist nicht THE primary action der Page). Bleibt `text`.

---

### 5.4 Tests

**Neue Tests:**
- `tests/test_event_edit_page.py` — Konstruktion, `show_for(None)` (neu-Anlegen-Modus), `show_for(id)` (Edit-Modus), Save → Repo-Aufruf, Delete → Repo-Aufruf, Routing zurück zu `return_to`.
- `tests/test_assessment_edit_page.py` — analog, plus Prefill-Pfade aus Menu.

**Geänderte Tests:**
- `tests/test_main_window.py` (falls existiert) — neue `show_event_edit`/`show_assessment_edit`-Methoden testen.

**Gelöschte Tests:**
- `tests/test_event_dialog.py` (ersetzt durch page-Test)
- `tests/test_assessment_dialog.py` (ersetzt durch page-Test)

**Smoke-Test:**
- Jede umgebaute Page konstruiert ohne Exception in `QT_QPA_PLATFORM=offscreen`.

**Avatar-SVG-Test:**
- `tests/test_avatar_badge.py` — falls existiert, prüfen dass ohne `image_bytes` der QPixmap nicht leer ist (statt vorher: text == "👤").

**Bestehende 241 Tests:** Alle müssen grün bleiben. Einige werden brechen wegen entfernter Emoji-Strings — gezielt anpassen (z.B. `assert btn.text() == "📝 Test bauen"` → `assert btn.text() == "Test bauen"`).

---

### 5.5 Migration & Rollout

Phase 13 ist eine atomische Refactoring-Phase ohne User-Daten-Migration. Nach Abschluss:

1. Alle Tests grün (geschätzt ~250).
2. Manueller Smoke-Test im echten Qt-Fenster (nicht offscreen): Event anlegen → speichern → bearbeiten → löschen, Note analog, Profile-Page mit Placeholder-Avatar.
3. Erneuter Screenshot-Test (siehe `ux-test/`-Folder) im maximierten Modus, alle 12 Pages durchklicken. Vergleich vorher/nachher dokumentiert in commit-message der Phase.

---

## 6. Akzeptanzkriterien

1. ✅ `EventEditPage` + `AssessmentEditPage` existieren im MainWindow-Stack und werden über `show_event_edit(...)` / `show_assessment_edit(...)` aufgerufen.
2. ✅ `dialogs/event_dialog.py` + `dialogs/assessment_dialog.py` sind **gelöscht**.
3. ✅ Alle Callsites in `pages/events.py`, `pages/grades.py`, `pages/menu.py` rufen die neuen Page-Methoden.
4. ✅ Alle Top-Bar-Buttons, ExamCard-CTAs, Copy-Buttons, Output-Header sind **text-only** (keine führenden Emojis).
5. ✅ Daily-5-Card behält `🔥 X Tage` und `✓ Heute geschafft` (Achievement-Decoration).
6. ✅ Result-Page behält `✓` / `✗` als Status-Indikator.
7. ✅ `assets/avatar-placeholder.svg` existiert; `AvatarBadge` + `ProfileCard` rendern es als Fallback statt `setText("👤")`.
8. ✅ Audit: Jeder `QPushButton(...)`-Aufruf im Codebase hat einen folgenden `setObjectName(...)` mit Wert aus `{primary, text, danger}`.
9. ✅ Button-Convention dokumentiert als Kommentar oben in `ui/style.qss`.
10. ✅ Alle bestehenden Tests bleiben grün, neue Tests grün, Gesamtzahl 250+ grün.

---

## 7. Risiken & Mitigation

| Risiko | Mitigation |
|---|---|
| Tests die `EventDialog`/`AssessmentDialog` importieren brechen | Umschreiben (nicht löschen) — Test-Logik bleibt, nur Klassen-Import ändert sich. |
| `QSvgRenderer` aus `PySide6.QtSvg` nicht verfügbar | Bereits via `QSvgWidget` in `profile_picker.py` genutzt → garantiert verfügbar. |
| Button-Audit findet 30+ Stellen — Scope ufert aus | Audit ist mechanisch (grep + add `setObjectName`). Pro Page ein Commit. Falls echt unrealistisch viel: priorisieren auf Top-Bar + neue Edit-Pages, Rest in Folge-Phase. |
| Inline-Pages haben kein "Dialog mit Esc-zu-Cancel" mehr | Bewusste Entscheidung: gleiche Nav-Semantik wie ProfileEditPage. `← Zurück` ist die Cancel-Aktion. |
| Emoji-Entfernung könnte zu kahl wirken | Hamburger `☰` bleibt als monochromes Unicode-Symbol; Achievement-Emojis (🔥 ✓) bleiben — die Wärme kommt vom Content, nicht vom Chrome. |
| User mag das Design am Ende nicht | Spec wird vor Implementation freigegeben. Falls nach Implementation Probleme: rollback ist `git revert` der Phase-13-Commits. |

---

## 8. Out of Scope für Phase 13

- Lint-Test für Button-objectName-Regel (manuelles Audit reicht für jetzt).
- Komplett-Redesign der Form-Layouts (Felder, Reihenfolge bleiben).
- Neue Icon-Library (nur das Avatar-SVG).
- Animationen, Transitions, Theming.
- Dark Mode.
- Touch-Gesten-Verbesserungen (Phase 11 hat 44pt-Touch-Targets erledigt).

---

## 9. Nachfolge-Phasen (Ideen, nicht zugesagt)

- **Phase 14 — Onboarding-Flow:** First-Run-Experience für neue Profile.
- **Phase 15 — Statistik-Visualisierungen:** Notenverlauf-Charts.
- **Phase 16 — Print/Export:** Tests/Lernpläne als PDF.

# Design — Globaler Zurück-Button + Noten-Nachtrag für vergangene KAs

**Datum:** 2026-05-18
**Status:** Spec, awaiting user review
**Phase-Nummerierung:** Phase 18 (zwei unabhängige Features, ein Spec, ein Plan)

## Kontext

Nach Phase 17 (Schulkalender + Ferien-Banner) sind zwei Lücken in Clemens' Alltagsfluss spürbar geworden:

1. **Keine sichtbare Rück-Navigation.** Pages haben heute ein `return_to`-Plumbing (event_edit, assessment_edit, profile_edit, profile_manager), aber kein sichtbares Zurück-Widget. Rück-Navigation passiert beim Speichern/Abbrechen oder über das Logo-Menü. Für einen Achtklässler erwartbar wäre ein vertrauter Browser-/Phone-Back-Button.
2. **Vergangene KAs aus dem iCal-Sync (Phase 17) bieten keinen direkten Pfad zur Notenerfassung.** Click auf eine vergangene KA im Schulkalender öffnet `event_edit` — das ist für *Metadaten-Edit* gedacht, nicht für Note-Eintragen. Die Notenerfassungs-Page (`AssessmentEditPage` mit `prefill_event_id`) existiert bereits, ist aber nur via Header-Button "Note hinzufügen" auffindbar, ohne KA-Kontext.

Beide Features sind technisch unabhängig, werden aber gemeinsam designt und implementiert, weil:
- Feature 2 hängt am Schulkalender-Vergangen-Tab. Nach dem Note-Eintragen will Clemens dorthin zurück. Ohne den Back-Button (Feature 1) wäre das ein weiterer hard-coded `return_to`-Sonderfall.
- Beide ändern dieselben Bereiche (`MainWindow`, `GlobalHeader`, `SchoolCalendarPage`).

## Scope

### In Scope

- Globaler Zurück-Button im `GlobalHeader`, links vom Logo, conditional sichtbar.
- History-Stack-basierte Navigations-Mechanik in `MainWindow` mit zentraler `_navigate(target, **kwargs)`-Methode. Alle 19 `show_*`-Methoden werden zu Wrappern.
- `Esc`-Tastatur-Shortcut für Back, nur aktiv wenn kein modaler Dialog offen ist.
- Erweiterung von `CalendarEntryCard`: für vergangene KAs ein Badge — "Note offen" oder die eingetragene Note (via existierendem `GradePill`).
- Neue Query `events_repo.list_past_klausuren_with_grade_status(conn, user_id, today)`.
- Click-Routing auf `SchoolCalendarPage`: vergangene KA → `show_assessment_edit(...)`, künftige KA → `show_event_edit(...)` (unverändert).
- Neues Widget `widgets/open_grades_banner.py` (analog `FerienBanner`), Slot auf `MenuPage` unter dem FerienBanner.
- Neuer Param `initial_tab: str | None` auf `SchoolCalendarPage.show_for(...)`.
- Disabling von Subject/Date in `AssessmentEditPage` wenn `prefill_event_id` gesetzt ist.

### Out of Scope

- Heuristik-Matching für historische unverknüpfte Noten (siehe ENT-DECIDED: strikte Verknüpfung via `assessments.scheduled_event_id`).
- Migrations-Flow für bestehende Noten ohne `scheduled_event_id`.
- Streamlined "Quick-Grade"-Inline-Dialog. Wir nutzen `AssessmentEditPage` mit Prefill.
- Multiple Noten pro KA (schriftlich + mündlich).
- Globale Tastatur-Shortcuts jenseits `Esc`.
- Animationen / Übergänge beim Page-Wechsel.
- DB-Migration. Keine Schema-Änderungen.

## ENT-DECIDED (Brainstorming-Antworten)

| # | Frage | Entscheidung |
|---|-------|--------------|
| Q2 | Verhalten des Zurück-Buttons | **A — History-Stack** (Browser-Back-Style) |
| Q3 | Discovery für „Note nachtragen" | **A + B-light** (Schulkalender primär, MenuPage als sanftes Echo) |
| Q4 | Was zählt als „vergangene KA ohne Note" | **A — Strikte Verknüpfung** via `scheduled_event_id` |

## Feature 1 — Globaler Zurück-Button

### Architektur

`MainWindow` führt einen Navigations-Dispatcher ein:

```python
self._history: list[tuple[str, dict]] = []  # [(target_name, kwargs), ...]
self._dispatch: dict[str, callable] = {
    "menu": self._render_menu,
    "library": self._render_library,
    # ... 19 Einträge
}

def _navigate(self, target: str, **kwargs) -> None:
    # Special: "menu" clears stack (root).
    # Special: stack-top dedup — wenn target == top, replace statt push.
    # Special: "runner" pusht NICHT (mid-test).
    # Push current head onto stack if applicable.
    self._dispatch[target](**kwargs)
    self._back_button.setVisible(len(self._history) > 0)

def _navigate_back(self) -> None:
    if not self._history:
        return
    target, kwargs = self._history.pop()
    self._dispatch[target](**kwargs)
    self._back_button.setVisible(len(self._history) > 0)
```

Alle 19 `show_*`-Methoden werden zu dünnen Wrappern:

```python
def show_grades(self) -> None:
    self._navigate("grades")

def show_assessment_edit(self, assessment_id=None, return_to="grades",
                         prefill_subject=None, prefill_event_id=None) -> None:
    self._navigate("assessment_edit",
                   assessment_id=assessment_id,
                   prefill_subject=prefill_subject,
                   prefill_event_id=prefill_event_id)
    # Der `return_to`-Param bleibt aus API-Kompatibilität erhalten,
    # wird intern aber ignoriert — der Stack regelt das.
```

### Widget — `widgets/back_button.py`

Neues `_BackButton`-Widget (`QFrame`, `objectName="backButton"`):
- Inhalt: SVG-Pfeil-Icon (`←`, 18px, `Color.PAPER_700`) + Text „Zurück" in `body_font(FontSize.SM, weight=Medium)`
- Spacing 6px zwischen Icon und Text
- Höhe: 40px (matched die Logo-Höhe für Hit-Target)
- Cursor: `PointingHandCursor`
- `mousePressEvent` → `window._navigate_back()`
- Signal `clicked` für Test-Beobachtung

### GlobalHeader-Integration

`GlobalHeader.__init__` fügt `_BackButton` als ersten Layout-Eintrag *vor* dem Logo ein. Beim Start `setVisible(False)`. `MainWindow` ruft `header.back_button.setVisible(...)` aus `_navigate`/`_navigate_back`.

### Edge Cases

| Page | Verhalten |
|------|-----------|
| `menu` | Root. `_navigate("menu")` clear't den Stack. Back-Button versteckt. |
| `profile_picker` | Vor-Login. `GlobalHeader` ist nicht sichtbar. |
| `runner` | Mid-Test heikel. Wird *nicht* auf Stack gepusht. Back-Button bleibt versteckt während Lauf. Pause-Button im Runner ist der explizite Pfad raus. |
| `results` | Push als normale Page. Back führt zurück zu Vorgängerseite (library/daily). |
| `assessment_edit` / `event_edit` | Speichern/Abbrechen löst weiterhin `_return_to`-Logik aus, die intern jetzt `_navigate(...)` oder `_navigate_back()` aufruft. Externe API unverändert. |

### Stack-Hygiene

- **Top-Dedup:** Wenn `_navigate(target)` mit `target == stack[-1].name` aufgerufen wird, replace statt push. Verhindert Loops bei wiederholtem Klick auf denselben Menüpunkt.
- **Root-Reset:** `_navigate("menu")` clear't den Stack komplett. Menu ist immer fresh start.

### Tastatur

`QShortcut(QKeySequence("Esc"), self)` mit Context `Qt.ShortcutContext.ApplicationShortcut`. Vor dem Trigger: Guard `QApplication.activeModalWidget() is None` und `self._back_button.isVisible()`. Sonst no-op.

### Tests

Neue Datei `tests/ui/test_navigation_stack.py`, ~6 Tests:
1. `_navigate("grades")` pusht aktuelles Top auf Stack, rendert grades.
2. `_navigate_back()` pop't und rendert das vorherige Top.
3. `back_button.isVisible()` bindet exakt an `len(_history) > 0`.
4. `_navigate("menu")` clear't Stack komplett.
5. `_navigate("runner")` pusht NICHT (Stack-Länge unverändert).
6. `Esc`-Shortcut triggert `_navigate_back()`, aber nur wenn Button sichtbar.

Plus Spot-Check: bestehende Tests, die `window.show_*` aufrufen oder mocken, bleiben grün — Aliase delegieren transparent.

## Feature 2 — Noten-Nachtrag für vergangene KAs

### Query

Neue Funktion in `events_repo.py`:

```python
def list_past_klausuren_with_grade_status(
    conn: sqlite3.Connection,
    user_id: int,
    today: date,
) -> list[sqlite3.Row]:
    """LEFT JOIN scheduled_events ↔ assessments, filter:
       - kind IN ('klausur', 'klassenarbeit', 'test')
       - end_date < today (heutige KA noch nicht „vergangen")
       - user_id = ?
       ORDER BY end_date DESC.
       Returns rows with: id, subject, end_date, kind,
                          assessment_id (nullable), grade (nullable)."""
```

Diese Query ist Single Source of Truth für **(a)** Badge-Zustand auf den Karten im Schulkalender Vergangen-Tab, **(b)** Banner-Counter auf MenuPage.

### Badge auf `CalendarEntryCard`

Heute hat die Card rechts einen `Pill` mit Subject-Variant. Erweiterung:

```python
def __init__(self, entry: CalendarEntry, *, grade_status: GradeStatus | None = None):
    # grade_status nur für past-klausur-Cards gesetzt;
    # für künftige oder ferien/frei/event = None.
    # Falls grade_status.has_grade → GradePill (existing widget)
    # Falls grade_status und nicht has_grade → "Note offen"-Pill (HONEY_400 bg)
```

Layout: Note-Pill **rechts neben dem Subject-Pill** in derselben Zeile, in einer `FlowLayout`-Hülle (existiert in `widgets/flow_layout.py`), damit bei schmaler Card-Breite ein Wrap auf eine zweite Zeile erfolgt statt Truncation.

Click-Cursor `PointingHandCursor` (heute schon für klausur-Cards), Click-Signal unverändert. Routing-Logik liegt nicht in der Card, sondern in `SchoolCalendarPage._on_card_click`.

### Click-Routing in `SchoolCalendarPage`

Heute in `school_calendar.py:213-214`:

```python
if hasattr(self.window, "show_event_edit"):
    self.window.show_event_edit(event_id, return_to="school_calendar")
```

Wird zu:

```python
def _on_card_click(self, entry: CalendarEntry) -> None:
    if entry.kind != "klausur":
        return  # ferien/frei/event: keine Click-Aktion (heute schon so)
    is_past = entry.end_date < self._today
    if is_past:
        # entry.entry_id für source="klausur" entspricht scheduled_events.id
        assessment = assessments_repo.find_by_event(self.conn, entry.entry_id)
        if assessment:
            self.window.show_assessment_edit(assessment_id=assessment["id"])
        else:
            self.window.show_assessment_edit(prefill_event_id=entry.entry_id)
    else:
        self.window.show_event_edit(event_id=entry.entry_id)
```

Hinweis: `entry.entry_id` ist der primärschlüssel der `scheduled_events`-Zeile für `source="klausur"`. Bei `source="calendar"` (ferien/frei/event) ist es die `calendar_events.id`, aber für diese Kinds gibt es kein Click-Routing.

Der `return_to`-String entfällt — der History-Stack aus Feature 1 erledigt das.

### Banner-Widget — `widgets/open_grades_banner.py`

Analog `widgets/ferien_banner.py` (Phase 17). Card mit:
- 4px `Color.HONEY_400`-Strip oben (statt Tea wie bei Ferien)
- Icon 📝 (oder SVG-Note-Pen, dezent)
- Label mit deutscher Pluralisierung:
  - `N == 1`: „1 offene Note"
  - `N > 1`: `f"{N} offene Noten"`
  - `N == 0`: Widget komplett `setVisible(False)`
- Optional Subtitle „Tippe für Schulkalender"
- Cursor `PointingHandCursor`
- Click → `window._navigate("school_calendar", initial_tab="vergangen")` via injected `get_window` callable (analog FerienBanner für Test-Isolation)

### MenuPage-Integration

Slot direkt **unter** dem FerienBanner (also: Greeting → FerienBanner → OpenGradesBanner → `_dynamic_container`). `_refresh_open_grades_banner()` wird am Ende von `reload()` aufgerufen, parallel zu `_refresh_ferien_banner()`. Trigger zum Refresh: dieselben wie FerienBanner — `events_synced` und `user_changed`.

Anzahl wird via `events_repo.list_past_klausuren_with_grade_status(...)` ermittelt, dann Count über `row["assessment_id"] is None`.

### Tab-Preselect in `SchoolCalendarPage`

`show_for(self, initial_tab: str | None = None)` neu. Wenn gesetzt, wird der entsprechende `subjectTab`-Button (`QButtonGroup`) programmatisch via `setChecked(True)` aktiviert *bevor* `_reload()` läuft. `_navigate("school_calendar", initial_tab="vergangen")` reicht den Wert durch via `_dispatch["school_calendar"](initial_tab="vergangen")`.

Mapping zwischen Tab-Wert und Button kommt aus dem existierenden internen `_TABS`-Dict in `SchoolCalendarPage`.

### `AssessmentEditPage` — Subject/Date-Disabling

Wenn `prefill_event_id` gesetzt UND `assessment_id is None`:
- Subject-RadioButtons werden disabled, der vorausgewählte Wert bleibt sichtbar.
- Date-Picker wird disabled, der vorausgewählte Wert bleibt sichtbar.

Damit ist visuell klar: hier wird die Note *zu dieser KA* eingetragen, nicht eine freistehende Note erfasst. Bei `assessment_id` gesetzt (Edit-Mode bestehender Note): alles bleibt enabled wie heute.

### Edge Cases

| Fall | Verhalten |
|------|-----------|
| Vergangene KA mit Note, Note wird gelöscht | Banner-Count steigt um 1, Card-Badge wechselt zu „Note offen" |
| Vergangene KA wird im Event-Edit storniert (kind wechselt weg von klausur) | Fällt aus dem Count, Badge verschwindet |
| Heutige KA (end_date == today) | Zählt **nicht** als vergangen — erst ab dem Tag danach |
| iCal-Sync löscht KA, für die schon eine Note existiert | Note bleibt in der `assessments`-Tabelle erhalten (`scheduled_event_id` wird zur orphan-Referenz oder NULL, je nach FK-Constraint im aktuellen Schema). Die KA erscheint nicht mehr im Schulkalender. Banner-Count bleibt konsistent, weil die Query gegen vorhandene `scheduled_events` joined. Verifikation im Plan-Task: aktuelle FK-Definition prüfen, ggf. anpassen. |
| KA mit Note → Click → Edit-Mode → Note auf neuen Wert geändert | Banner unverändert (immer noch verknüpft), Card zeigt neue Note |

### Tests

Neue/erweiterte Tests, ~12 insgesamt:

- `tests/storage/test_events_repo.py` (erweitert): `list_past_klausuren_with_grade_status` mit 4 Szenarien — mit Note / ohne Note / nicht-Klausur-Kind / Zukunft.
- `tests/ui/test_calendar_entry_card_widget.py` (erweitert): Badge-Varianten „Note offen" und „Note 2,5"; künftige KAs zeigen keinen Badge.
- `tests/ui/test_open_grades_banner_widget.py` (neu): N=0 versteckt, N=1 vs N=2 korrekte Pluralisierung, Click-Signal emit zum richtigen Target.
- `tests/ui/test_school_calendar_page.py` (erweitert): Click-Routing für past-mit-Note, past-ohne-Note, future-klausur; `initial_tab="vergangen"`-Preselect.
- `tests/integration/test_grade_nachtrag_flow.py` (neu, E2E): vergangene KA in Vergangen-Tab → Click → `assessment_edit` prefill → Note speichern → Back via Stack → Badge wechselt → Banner-Count dekrementiert.

## Implementierungs-Reihenfolge

1. **Phase A — Navigation-Refactor:** `_navigate`/`_history`/`_dispatch` in `MainWindow`, alle `show_*` zu Wrappern. Kein sichtbarer Effekt. Bestehende Tests grün, neue Stack-Tests grün → Foundation steht.
2. **Phase B — `_BackButton` + Esc:** Widget gebaut, im `GlobalHeader` integriert, Esc-Shortcut, Visibility-Binding.
3. **Phase C — Query + Card-Badge + Click-Routing:** `list_past_klausuren_with_grade_status`, Badge-Varianten in `CalendarEntryCard`, neues Click-Routing in `SchoolCalendarPage`. Subject/Date-Disable in `AssessmentEditPage`.
4. **Phase D — Menu-Banner + Tab-Preselect:** `OpenGradesBanner`, Slot auf `MenuPage`, `initial_tab`-Param auf `SchoolCalendarPage.show_for(...)`.

Jede Phase ist eigenständig commit-fähig und hinterlässt die Suite grün — geeignet für Subagent-driven-development.

## Risiken & Mitigationen

| Risiko | Mitigation |
|--------|------------|
| `_navigate`-Refactor bricht Test-Erwartungen, die `window.show_*` aufrufen oder mocken | Aliase bleiben erhalten — bestehende Aufrufer funktionieren transparent weiter. Suite-Lauf nach Phase A. |
| `Esc`-Shortcut konfligiert mit Esc in QMessageBox/QDialog | `QShortcut`-Context `ApplicationShortcut` + Guard `QApplication.activeModalWidget() is None`. |
| Banner-Refresh löst N+1-Queries aus | Banner-Counter teilt sich Query mit Schulkalender-Vergangen-Tab. Eine Query, mehrere Konsumenten. |
| Click auf KA mit Note öffnet Edit-Mode — Versehentliches Löschen | `AssessmentEditPage` hat bereits einen geschützten Löschen-Button mit Bestätigung. Out-of-scope to refine here. |
| Disabling von Subject/Date in `AssessmentEditPage` bei Prefill bricht Save-Logik | Disabled-Widgets werden weiterhin via `.text()`/`.isChecked()` ausgelesen — kein Funktional-Bruch, separat getestet. |
| `kind`-Wert für „past klausur" — `is_klausur_event` aus Phase 17 deckt das ab, aber Tests in Phase 18 verlassen sich darauf | Wir verwenden `events_repo.list_past_klausuren_with_grade_status` als zentralen Filter — dort die Liste der zulässigen Kinds expliziert. |

## Akzeptanztest (manuell, am Ende)

1. Aus Menu → Schulkalender → Vergangen-Tab → zurück. Back-Button sichtbar oben links, führt zu Menu.
2. iCal-Sync mit Mini-Fixture inkl. ≥1 vergangener KA. MenuPage zeigt „1 offene Note"-Banner.
3. Banner-Klick → Schulkalender Vergangen-Tab. KA-Card zeigt „Note offen"-Pill.
4. KA-Klick → `AssessmentEditPage` mit Subject + Date prefilled (disabled). Note 2,5 wählen, speichern.
5. Back-Button → zurück zu Schulkalender Vergangen-Tab. Karte zeigt nun `GradePill` „2,5". Back → MenuPage, Banner verschwunden.
6. Erneut Karte klicken (mit existierender Note) → `AssessmentEditPage` im Edit-Mode der bestehenden Note. Löschen → Banner kommt zurück.
7. `Esc`-Taste in tieferer Page-Hierarchie → Zurück. In offenem `QMessageBox` → schließt nur die MessageBox, navigiert nicht.

## Follow-up-Kandidaten (NICHT in dieser Phase)

- Heuristik-Matching für historische unverknüpfte Noten.
- Multiple Noten pro KA (schriftlich + mündlich).
- „Quick-Grade"-Inline-Dialog ohne Page-Wechsel.
- Globale Tastatur-Shortcuts jenseits `Esc` (z.B. Alt+Left als Back-Alternative).
- Animation/Übergänge beim Page-Wechsel.
- Migration einmaliger Bulk-Verknüpfung historischer Noten ↔ Events.

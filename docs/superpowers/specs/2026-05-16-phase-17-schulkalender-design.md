# Phase 17 — Schulkalender + Ferien-Banner

**Status:** Design / Spec
**Datum:** 2026-05-16
**Vorgängerphase:** Phase 16 (Fehlerheft) + Manual-Test-Polish
**Typ:** Feature-Phase mit Migration, neuem Domain-Paket, einer UI-Page + Banner-Widget

---

## 1. Motivation

Phase 15 hat den iCal-Sync vom Schulportal Hessen eingeführt — aber nur **Klausuren** landen in der DB (UID-Filter `-klausur-`). Alles andere im Feed (Ferien, bewegliche Feiertage, Wettbewerbe, Schul-Events) wird geparst und verworfen.

Damit fehlt Clemens eine zentrale Sicht auf das Schuljahr: Wann sind die nächsten Ferien? Welche Wettbewerbe stehen an? Welche schulfreien Einzeltage hat die Schule gelegt? Diese Infos liegen schon im iCal-Feed, sind nur nicht persistiert oder dargestellt.

Phase 17 macht aus dem Feed einen **vollständigen Schulkalender** — Agenda-Liste mit filterbaren Event-Kategorien — und ergänzt einen **Ferien-Countdown-Banner** im Hauptmenü.

## 2. Ziel

Clemens hat über das Logo-Menü eine eigene Schulkalender-Page, die KAs, Ferien, freie Einzeltage und Schul-Events chronologisch listet. Vier Event-Typ-Filter und ein Zeitraum-Filter (Ab heute / Alle / Vergangen) sind toggleable und werden **per User persistiert**.

Auf dem Hauptmenü zeigt ein schlanker Banner-Card permanent den Countdown zu den nächsten Ferien — oder, wenn gerade Ferien sind, die verbleibenden Ferientage. Klick auf den Banner führt zur Kalender-Page.

## 3. Nicht-Ziele

- **Kein manueller Eintrag** von Kalender-Einträgen. Quelle ist ausschließlich der iCal-Feed (Phase 15). Manuelle Ferien-Anlage wäre Phase 18.
- **Kein Monats-Grid** (klassisches 7×6-Layout). Nur Agenda-Liste. Grid-View wäre eigene Phase.
- **Kein Subject-Filter** für KAs. Die KA-Filter-Achse ist auf Event-Typ beschränkt.
- **Kein Push-Notification-System.** Keine „Morgen Ferien!"-Benachrichtigung.
- **Kein Filter-Reset-Button.** Vier Klicks reichen.
- **Kein Hinzufügen-Button** im Kalender. Nur sync-driven.
- **Kein Modal-Popup beim App-Start.** Banner-im-Menü ist die gewählte Form (siehe Brainstorming).
- **Keine Aggregation über Profile.** Pro User eigener Filter-State, eigene Feed-URL (Phase 15-Status quo).
- **Bewegliche Feiertage triggern KEINEN Banner.** Nur `kind='ferien'` mit Multi-Day-Range zählt für den Countdown. Single-Day-Frei-Events erscheinen nur in der Kalender-Liste.

## 4. Architektur-Übersicht

```
src/school_test_engine/
├── ical_sync/                            MOD
│   ├── parser.py                         MOD — RawVEvent.dtend_date + is_multi_day
│   ├── classifier.py                     MOD — classify() statt is_klausur_event()
│   └── service.py                        MOD — zweiter Schreibpfad (calendar_events)
├── storage/
│   ├── migrations/012_phase17_calendar.sql   NEU
│   ├── calendar_events_repo.py           NEU
│   └── users_repo.py                     MOD — 5 neue Kwargs (4 Type-Flags + 1 Timeframe)
├── school_calendar/                      NEU — Domain-Paket
│   ├── __init__.py
│   ├── models.py                         CalendarEntry Frozen-Dataclass
│   ├── filters.py                        CalendarFilters Frozen-Dataclass
│   └── service.py                        list_entries, group_by_month, ferien_banner_state
├── ui/
│   ├── pages/school_calendar.py          NEU — SchoolCalendarPage
│   ├── pages/menu.py                     MOD — Banner-Slot integrieren
│   ├── widgets/calendar_entry_card.py    NEU
│   ├── widgets/ferien_banner.py          NEU
│   ├── widgets/global_header.py          MOD — „Schulkalender"-Eintrag im Logo-Menü
│   └── main_window.py                    MOD — show_school_calendar()
```

**Datenfluss:**

```
iCal-Feed (Phase 15)
   ↓
parser.parse_events()
   → RawVEvent inkl. dtend_date
   ↓
classifier.classify(event) → "klausur" | "ferien" | "frei" | "event" | None
   ↓
service.sync_feed() — split:
   "klausur" → scheduled_events    (Phase 7-Pfad, unverändert)
   "ferien" / "frei" / "event" → calendar_events  (NEU)
   None → skip
   ↓
SchoolCalendarPage.reload()
   → school_calendar.service.list_entries(conn, uid, today, filters)
       → liest scheduled_events (Klausuren) + calendar_events
       → merged, gefiltert, chronologisch sortiert
   → SchoolCalendarPage rendert Monats-Sektionen + CalendarEntryCards

MenuPage.reload() / on events_synced
   → school_calendar.service.ferien_banner_state(conn, uid, today)
       → query calendar_events WHERE kind='ferien' AND end_date >= today
       → pickt active vacation oder next vacation
   → FerienBanner gerendert oder kollabiert
```

## 5. Datenmodell

### 5.1 Migration 012 — neue Tabelle + Filter-Spalten

```sql
-- Phase 17: Schulkalender — Ferien/Frei/Schul-Events + per-User-Filter-State

CREATE TABLE IF NOT EXISTS calendar_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            TEXT    NOT NULL
                    CHECK (kind IN ('ferien', 'frei', 'event')),
    title           TEXT    NOT NULL,
    start_date      TEXT    NOT NULL,        -- ISO YYYY-MM-DD (inklusiv)
    end_date        TEXT    NOT NULL,        -- ISO YYYY-MM-DD (inklusiv); = start_date bei Single-Day
    external_uid    TEXT,
    external_source TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_user_date
    ON calendar_events(user_id, start_date);

CREATE UNIQUE INDEX IF NOT EXISTS idx_calendar_events_external_uid
    ON calendar_events(user_id, external_uid)
    WHERE external_uid IS NOT NULL;

-- Filter-State auf users (analog show_keyboard_hints aus Phase 14)
ALTER TABLE users ADD COLUMN calendar_show_klausuren INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_show_ferien    INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_show_frei      INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_show_events    INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_timeframe      TEXT    NOT NULL DEFAULT 'future'
                                                       CHECK (calendar_timeframe IN ('future', 'all', 'past'));
```

**Design-Entscheidungen:**

| Punkt | Wahl | Begründung |
|---|---|---|
| `end_date` NOT NULL | Single-Day = `start_date` = `end_date` | Vereinfacht Queries (kein `COALESCE`). Bytes-Overhead vernachlässigbar bei ~200 Events/Jahr. |
| `kind` 3-Wert-Enum | `'ferien'` / `'frei'` / `'event'` | Trennung für Filter UND Banner-Logik (`kind='ferien'` + Multi-Day = Banner-Kandidat). |
| Kein `subject`-Feld | NULL ist nicht sauber abbildbar; AGs sind noch hypothetisch | Bei Bedarf später per `ALTER TABLE ADD COLUMN subject TEXT` — keine Lock-in. |
| Filter auf `users` (5 Spalten) | Nicht JSON-Blob | Konsistenz mit Phase 14 (`show_keyboard_hints`) und Phase 9 (`school_context_*`). Klare Typen + CHECK-Constraint. |
| `timeframe` als CHECK-Enum | 3 Strings, nicht INT | Lesbarer in Queries und Debug-SQL als Magic Numbers. |

### 5.2 Domain-Modelle

**`CalendarEntry` (`school_calendar/models.py`):**

```python
@dataclass(frozen=True)
class CalendarEntry:
    source: Literal["klausur", "calendar"]    # KA aus scheduled_events vs. calendar_events
    kind: Literal["klausur", "ferien", "frei", "event"]
    title: str
    start_date: date
    end_date: date
    subject: str | None       # nur bei kind="klausur"
    entry_id: int             # Row-ID in der Quelltabelle

    @property
    def is_multi_day(self) -> bool:
        return self.end_date > self.start_date

    @classmethod
    def from_klausur_row(cls, row) -> "CalendarEntry": ...
    @classmethod
    def from_calendar_row(cls, row) -> "CalendarEntry": ...
```

**`CalendarFilters` (`school_calendar/filters.py`):**

```python
@dataclass(frozen=True)
class CalendarFilters:
    show_klausuren: bool
    show_ferien: bool
    show_frei: bool
    show_events: bool
    timeframe: Literal["future", "all", "past"]

    @classmethod
    def defaults(cls) -> "CalendarFilters":
        return cls(True, True, True, True, "future")

    @classmethod
    def from_user_row(cls, row) -> "CalendarFilters": ...

    def with_kind_set(self, kind: str, value: bool) -> "CalendarFilters": ...
    def with_timeframe(self, tf: str) -> "CalendarFilters": ...
    def active_kinds(self) -> set[str]: ...    # {"klausur","ferien","frei","event"} ∩ aktiv
```

## 6. iCal-Ingest-Erweiterung

### 6.1 Parser

`RawVEvent` kriegt das Feld `dtend_date`. Subtile Falle: `DTEND` bei DATE-only-Events ist **exklusiv** (Tag nach dem letzten). Wir normalisieren beim Parsen auf inklusiv durch `-timedelta(days=1)`.

```python
@dataclass(frozen=True)
class RawVEvent:
    uid: str
    summary: str
    description: str
    dtstart_date: str
    dtend_date: str                  # NEU
    categories: tuple[str, ...]

    @property
    def is_multi_day(self) -> bool:
        return self.dtend_date > self.dtstart_date
```

Parser-Logik für DTEND:
- Kein DTEND → `end_iso = dtstart_iso`
- DTEND ist DATETIME → `end_iso = dtend.dt.date().isoformat()` (gleicher Tag bei Time-Events)
- DTEND ist DATE-only → `end_iso = (dtend.dt - timedelta(days=1)).isoformat()`

### 6.2 Classifier

Aus `is_klausur_event(event) → bool` wird:

```python
EventKind = Literal["klausur", "ferien", "frei", "event"]

def classify(event: RawVEvent) -> EventKind | None:
    if "-klausur-" in event.uid:
        return "klausur"

    cats_lower = {c.lower() for c in event.categories}

    if "ferien" in cats_lower or "feiertag" in cats_lower:
        return "ferien" if event.is_multi_day else "frei"

    if "arbeiten" in cats_lower:
        # CATEGORIES:Arbeiten OHNE -klausur- = Wettbewerb, Olympiade etc.
        return "event"

    # Konservativ: unbekannte Kategorien → skip (verhindert Unterrichtsstunden-Flut)
    return None


def is_klausur_event(event: RawVEvent) -> bool:
    """Backwards-Compat-Wrapper für bestehende Phase-15-Tests."""
    return classify(event) == "klausur"
```

**Bewusst konservativ:** Unbekannte Categories werden geskippt statt als generischer „event" eingesammelt. Falls Real-World-Sync zeigt dass relevante Events fehlen, wird die Whitelist im Classifier erweitert. (Erste Annahme — beim ersten echten Sync gegen den echten Hessen-Feed verifizieren.)

### 6.3 Service

`service.sync_feed` kriegt zweiten Write-Pfad:

```python
for raw in raw_events:
    kind = classify(raw)
    if kind is None:
        skipped += 1
        continue

    if kind == "klausur":
        _ingest_klausur(conn, user_id, raw, ...)    # Phase 15-Pfad, unverändert
    else:
        _ingest_calendar(conn, user_id, raw, kind)
```

`_ingest_calendar` macht UPSERT-via-`external_uid` gegen `calendar_events`:
- Match per `external_uid` (zweiter UNIQUE-Index in `calendar_events`).
- `_has_calendar_changes(existing, new)` vergleicht `kind`, `title`, `start_date`, `end_date`.
- Bei Diff → UPDATE.
- Events die im Feed verschwinden → DELETE (kein Preserve-Filter wie bei KAs mit Assessments).

`SyncResult` erweitert um:

```python
@dataclass(frozen=True)
class SyncResult:
    added: int           # KAs added (status quo)
    updated: int         # KAs updated
    deleted: int         # KAs deleted
    cal_added: int       # NEU
    cal_updated: int     # NEU
    cal_deleted: int     # NEU
    skipped: int
    error: str | None
    synced_at: datetime
```

Status-Label-Format auf der Events-Page: `"vor 2h · 3 neu, 1 geändert · 12 Kalender-Einträge"`.

## 7. Storage-Layer

### 7.1 `calendar_events_repo.py`

```python
def create(conn, *, user_id, kind, title, start_date, end_date,
           external_uid=None, external_source=None) -> int
def update_by_external_uid(conn, *, user_id, external_uid, kind, title,
                            start_date, end_date) -> bool
def delete_by_external_uid(conn, user_id, external_uid) -> bool
def list_external_uids(conn, user_id) -> set[str]

def list_for_user(conn, user_id, *, today=None, timeframe="future",
                   kinds=None) -> list[sqlite3.Row]
    # SQL filtert kind IN ? UND timeframe-Predikat:
    #   future:   end_date >= today
    #   past:     end_date < today
    #   all:      kein Datumsfilter
    # ORDER BY start_date ASC

def find_active_vacation(conn, user_id, today) -> sqlite3.Row | None
    # WHERE kind='ferien' AND start_date <= today AND end_date >= today
    # ORDER BY start_date DESC LIMIT 1

def find_next_vacation(conn, user_id, today) -> sqlite3.Row | None
    # WHERE kind='ferien' AND start_date > today
    # ORDER BY start_date ASC LIMIT 1
```

### 7.2 `events_repo.list_for_calendar` — neue Read-Methode

```python
def list_for_calendar(conn, user_id: int) -> list[sqlite3.Row]:
    """Alle KAs für die Kalender-Sicht — ORDER BY event_date ASC."""
    # SELECT id, subject, kind, event_date, topics, note
    # FROM scheduled_events WHERE user_id = ? ORDER BY event_date ASC
```

Kein Timeframe-Filter im SQL — die Service-Schicht filtert (Klausuren-Zeilen müssen für den Merge mit calendar_events durch denselben Timeframe-Filter laufen).

### 7.3 `users_repo.update_user` — 5 neue Kwargs

```python
def update_user(
    conn,
    user_id: int,
    *,
    # ... bestehende Kwargs ...
    calendar_show_klausuren: int | None = None,
    calendar_show_ferien: int | None = None,
    calendar_show_frei: int | None = None,
    calendar_show_events: int | None = None,
    calendar_timeframe: str | None = None,
) -> None:
    ...
```

Pattern: `None` = keine Änderung (wie `show_keyboard_hints` aus Phase 14, weil NOT NULL DEFAULT — kein `_SENTINEL` nötig).

## 8. Domain-Service-Layer

### 8.1 `school_calendar/service.py`

```python
def list_entries(conn, user_id: int, today: date,
                 filters: CalendarFilters) -> list[CalendarEntry]:
    """Merged Klausuren + calendar_events, gefiltert + chronologisch sortiert."""
    entries: list[CalendarEntry] = []
    active = filters.active_kinds()

    if "klausur" in active:
        for row in events_repo.list_for_calendar(conn, user_id):
            entries.append(CalendarEntry.from_klausur_row(row))

    cal_kinds = active - {"klausur"}
    if cal_kinds:
        for row in calendar_events_repo.list_for_user(
            conn, user_id,
            today=today, timeframe=filters.timeframe, kinds=cal_kinds,
        ):
            entries.append(CalendarEntry.from_calendar_row(row))

    entries = _apply_timeframe(entries, today, filters.timeframe)
    entries.sort(key=lambda e: (e.start_date, e.kind))
    return entries


def group_by_month(entries: list[CalendarEntry]) -> list[tuple[str, list[CalendarEntry]]]:
    """Liste [(label='JULI 2026', [entries]), ...] in Reihenfolge."""
    ...


def ferien_banner_state(conn, user_id: int, today: date) -> FerienBannerState:
    active = calendar_events_repo.find_active_vacation(conn, user_id, today)
    if active is not None:
        remaining = (date.fromisoformat(active["end_date"]) - today).days
        return _build_in_vacation(active, remaining)

    upcoming = calendar_events_repo.find_next_vacation(conn, user_id, today)
    if upcoming is not None:
        days_until = (date.fromisoformat(upcoming["start_date"]) - today).days
        return _build_countdown(upcoming, days_until)

    return FerienBannerState(mode="hidden", label="", days=None,
                              target_date=None, vacation_title=None)
```

### 8.2 `FerienBannerState`

```python
@dataclass(frozen=True)
class FerienBannerState:
    mode: Literal["hidden", "countdown", "in_vacation"]
    label: str
    days: int | None
    target_date: date | None
    vacation_title: str | None
```

Label-Varianten:
- `mode="countdown"`, days=23 → `"Noch 23 Tage bis Herbstferien — 17.10.2026"`
- `mode="countdown"`, days=1 → `"Morgen geht's los: Herbstferien starten!"`
- `mode="in_vacation"`, days=5 → `"Noch 5 Tage Sommerferien — genieß sie! 🌞"`
- `mode="in_vacation"`, days=0 → `"Letzter Ferientag — morgen geht's wieder los."`
- `mode="hidden"` → Banner wird nicht gerendert (`setVisible(False)`)

## 9. UI-Layer

### 9.1 `SchoolCalendarPage`

**Layout-Struktur (top-to-bottom):**

```
[Eyebrow] SCHULKALENDER
[Title] Alle Termine                                        (Fraunces)
Klassenarbeiten, Ferien, freie Tage und Schul-Events.       (paper-500 9pt)

[✓ KAs] [✓ Ferien] [✓ Frei] [✓ Events]                   ← Filter-Chips
[Ab heute] [Alle] [Vergangen]                             ← Zeitraum-Tabs

MAI 2026                                                  (eyebrow + 1px-HRule)
[15.05.]   Geographie Klassenarbeit               [KA]
[28.05.]   Pädagogischer Tag                      [Frei]

JULI 2026
[07.07.–16.08.]   Sommerferien                    [Ferien]
```

**Komponenten:**

- **Header:** `EyebrowLabel("SCHULKALENDER")` + Fraunces-Title + Subtitel-Text.
- **Filter-Chips:** 4× `QPushButton` mit `setCheckable(True)` + `setObjectName("filterChip")`. Neuer QSS-Block für `filterChip[checked="true"|"false"]`-Variants.
- **Zeitraum-Tabs:** 3× `QPushButton` mit `setCheckable(True)` + `setObjectName("subjectTab")` (wiederverwendet Phase-7-QSS). In einer `QButtonGroup` mit `setExclusive(True)`.
- **Scroll-Area:** `QScrollArea` mit `widgetResizable=True`.
- **Monats-Sektionen:** `EyebrowLabel("JULI 2026")` + dünne 1px-HRule + Card-Container.

### 9.2 `CalendarEntryCard`

```python
class CalendarEntryCard(QFrame):
    """Schlanke Card: Date-Badge + Title-Column + Kind-Pill."""
    clicked = Signal(int)    # emittiert nur bei klickbaren Cards (KAs)

    def __init__(self, entry: CalendarEntry, parent=None):
        super().__init__(parent)
        self.setObjectName("calendarEntryCard")
        # 4-spaltig: [DateBadge] [TitleColumn] [stretch] [KindPill]
        ...
```

- **Date-Badge** links: `QLabel` mit `objectName="dateBadge"`. Single-Day: `"15.05."`. Multi-Day: `"07.07.–16.08."`. Cross-Year: Jahr inkludieren.
- **Title-Spalte (Mitte):**
  - Zeile 1: `title` (10pt Inter-Medium) — bei KAs: `"{Fach} {kind-label}"` (z.B. „Geographie Klassenarbeit"); bei calendar_events: `title`-Feld.
  - Zeile 2 (optional): `subtitle` — bei KAs `topics` joined mit „·" wenn vorhanden, sonst weggelassen. Synced KAs ohne Topic-Edit haben kein Subtitle. Bei calendar_events kein Subtitle.
- **Kind-Pill rechts:** wiederverwendet `Pill`-Widget mit Variant pro Kind:
  - `klausur` → `clay` (Orange-Rot, hohe Salience)
  - `ferien` → `tea` (Grün)
  - `frei` → `honey` (warm)
  - `event` → `sky` (neutral)

**Klick-Verhalten:**
- `kind="klausur"` → `clicked` Signal emittiert → MainWindow öffnet `event_edit`.
- Andere Kinds → kein Klick-Handling, `setCursor` bleibt default.

### 9.3 `FerienBanner`

Schlanke Card im Hauptmenü direkt unter der Begrüßung. Layout:

```
┌──────────────────────────────────────────────────────┐
│ ▍ 🌴  Noch 23 Tage bis Herbstferien                 │
│      Beginn: 17.10.2026                             │
└──────────────────────────────────────────────────────┘
```

- 4px tea-200-Akzent-Strip links als visueller Indikator.
- Emoji im Body-Text (🌴 für Countdown, 🌞 für In-Vacation) — bewusste Ausnahme vom Phase-13-„Emoji-Strip"-Pattern (analog zum 🔥 in DailyCard). Linux-Mint-Color-Emoji-Falle: Emojis sind reiner String, keine Button-Glyphen — bleibt sichtbar.
- `setCursor(Qt.PointingHandCursor)`, Klick → `window.show_school_calendar()`.

### 9.4 MenuPage-Integration

Banner-Slot direkt unter `_greeting_label`:

```python
self._ferien_banner_slot = QVBoxLayout()
layout.addLayout(self._ferien_banner_slot)
```

`_refresh_ferien_banner()` wird in `reload()` aufgerufen:
1. Alten Banner mit `setParent(None)` + `deleteLater()` entfernen (Phase-16-Manual-Test-Polish-Lesson).
2. `ferien_banner_state(conn, uid, today)` abfragen.
3. Wenn `mode="hidden"` → nicht rendern, fertig.
4. Sonst `FerienBanner(state)` instanziieren und einfügen.

Refresh-Trigger:
- `user_changed` → `reload()` → `_refresh_ferien_banner()`
- `events_synced` (Phase 15-Signal) → `reload()` → `_refresh_ferien_banner()`

### 9.5 Logo-Menü (`widgets/global_header.py`)

Neuer Eintrag „Schulkalender" zwischen „Fehlerheft" und dem Profil-Wechsel-Separator. Trigger:

```python
def _on_school_calendar_clicked(self):
    win = self.window()
    if hasattr(win, "show_school_calendar"):
        win.show_school_calendar()
```

### 9.6 MainWindow

```python
def show_school_calendar(self) -> None:
    if self._school_calendar_page is None:
        self._school_calendar_page = SchoolCalendarPage(self, user_id=self.active_user_id)
        self._stack.addWidget(self._school_calendar_page)
        self.user_changed.connect(self._school_calendar_page._on_user_changed)
        self.events_synced.connect(self._school_calendar_page.reload)
    self._school_calendar_page.reload()
    self._stack.setCurrentWidget(self._school_calendar_page)
```

## 10. Filter-Persistenz-Flow

**Initial-Load:**

```python
def reload(self) -> None:
    self._loading = True
    try:
        with get_connection() as conn:
            user_row = users_repo.get_by_id(conn, self._user_id)
            self._filters = CalendarFilters.from_user_row(user_row)
            self._apply_filters_to_ui()       # Chip- und Tab-States setzen
            entries = list_entries(conn, self._user_id, date.today(), self._filters)
    finally:
        self._loading = False
    self._render_entries(entries)
```

**Toggle-Handlers:**

```python
def _on_chip_toggled(self, kind: str, checked: bool) -> None:
    if self._loading:
        return
    self._filters = self._filters.with_kind_set(kind, checked)
    self._persist_filters(self._filters)
    self._reload_list_only()

def _on_timeframe_changed(self, tf: str) -> None:
    if self._loading:
        return
    self._filters = self._filters.with_timeframe(tf)
    self._persist_filters(self._filters)
    self._reload_list_only()
```

**Reentrancy-Guard:**
`self._loading`-Flag schützt vor Endlos-Speicher-Loop wenn `_apply_filters_to_ui` Chip-States programmatisch setzt. Pattern aus Phase 8 (Subject-Switch) und Phase 9 (ComboBox-Trigger) erprobt.

**Empty-States:**
- `filters.active_kinds() == set()` → „Alle Filter sind ausgeschaltet — klick oben eine Kategorie an, um Termine zu sehen."
- `entries == []` → „Keine Termine im gewählten Zeitraum."

## 11. Test-Strategie

**~50 neue Tests, 14 neue / erweiterte Files:**

| Bucket | File | Tests |
|---|---|---|
| Migration | `tests/test_migration_012.py` | 4 |
| Parser | `tests/ical_sync/test_parser.py` (extend) | +3 |
| Classifier | `tests/ical_sync/test_classifier.py` (rewrite) | 8 |
| Service-Sync | `tests/ical_sync/test_service.py` (extend) | +6 |
| calendar_events_repo | `tests/storage/test_calendar_events_repo.py` | 7 |
| school_calendar.service | `tests/school_calendar/test_service.py` | 6 |
| Filters | `tests/school_calendar/test_filters.py` | 4 |
| users_repo Calendar-Kwargs | `tests/storage/test_users_repo_calendar.py` | 3 |
| Ferien-Banner-Service | `tests/school_calendar/test_ferien_banner_service.py` | 6 |
| FerienBanner-Widget | `tests/ui/test_ferien_banner_widget.py` | 2 |
| SchoolCalendarPage | `tests/ui/test_school_calendar_page.py` | 5 |
| MenuPage-Banner-Slot | `tests/ui/test_menu_page_ferien_banner.py` | 3 |
| Logo-Menü-Entry | `tests/ui/test_global_header_calendar.py` | 1 |
| E2E-Smoketest | `tests/test_school_calendar_e2e.py` | 2 |

**Test-Suite-Wachstum: 410 → ~460.**

**Fixture-Erweiterung:** `tests/fixtures/schulkalender_mini.ics` kriegt zwei zusätzliche VEVENTs:
- Single-Day-`frei`: „Pädagogischer Tag" (CATEGORIES:Ferien, 1 Tag).
- Multi-Day-`ferien`: „Herbstferien" (CATEGORIES:Ferien, 12 Tage).

## 12. Akzeptanz-Kriterien

1. Sync gegen erweiterte Fixture: `scheduled_events` = 3 KAs, `calendar_events` = 1 Sommerferien + 1 Pädagogischer Tag + 1 Herbstferien + 1 Mathewettbewerb. `skipped = 0`.
2. SchoolCalendarPage öffnet aus Logo-Menü, zeigt alle 4 Kinds chronologisch in Monats-Sektionen.
3. Chip-Klick „Frei" deaktivieren → Pädagogischer Tag verschwindet, Filter persistiert über App-Neustart.
4. Tab „Vergangen" aktivieren → nur Sommerferien (Vergangenheit) ist sichtbar.
5. Hauptmenü zeigt Banner „Noch X Tage bis Herbstferien — 19.10.2026".
6. Klick auf Banner → SchoolCalendarPage öffnet sich.
7. Mit simuliertem `today` innerhalb Sommerferien → Banner „Noch X Tage Sommerferien — genieß sie! 🌞".
8. Phase-7-Cockpit-Funktionen unverändert: KA-Hero auf Menu, Termine-Page, Noten-Page, comparison_for_assessment.
9. Bestehende Phase-15-Tests (`is_klausur_event`-Wrapper) bleiben grün.
10. Test-Suite ~460/460 grün.

## 13. Risiken + offene Fragen

- **Real-World-Feed unbekannt:** Der konservative Classifier (Unbekannt → skip) könnte legitime Events ausschließen. Erste Annahme — beim ersten Sync gegen den echten Hessen-Feed nachschauen welche `CATEGORIES`-Strings real auftauchen und Whitelist erweitern.
- **Multi-Year-Multi-Vacation-Banner:** Wenn der Feed Sommerferien 2026 UND 2027 enthält, zeigt der Banner die nächste — also 2026 zuerst. Akzeptabel; kein Sonderfall nötig.
- **Subject in calendar_events:** Aktuell nicht gespeichert. Wenn AGs später mit Fach gefiltert werden sollen, `ALTER TABLE ADD COLUMN subject TEXT`.
- **iCal-Sync ohne Verbindung:** Wenn der User keinen Feed eingetragen hat (kein `ical_feed_url`), bleibt `calendar_events` leer → Page rendert Empty-State. Banner kollabiert. Akzeptabel.

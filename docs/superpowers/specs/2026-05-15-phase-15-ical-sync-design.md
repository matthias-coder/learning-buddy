# Phase 15 — iCal-Schulkalender-Sync

**Status:** Design / Spec
**Datum:** 2026-05-15
**Vorgängerphase:** Phase 14 (Learning Buddy) + Phase 14.1 (Polish-Fixes)
**Typ:** Feature-Phase mit einer Migration und einem neuen Domain-Paket

---

## 1. Motivation

Die Phase-7-`scheduled_events`-Tabelle ist das Lern-Cockpit der App: jede anstehende KA wird darin geführt, taucht in der Menü-Hero-Card mit Countdown auf, und an ihr hängen später die echten Schul-Noten. Bisher müssen Termine **manuell** eingetragen werden — Matthias oder Clemens öffnen die Termine-Page, klicken "+ Neuer Termin", füllen Fach/Typ/Datum aus.

Das Schulportal Hessen bietet pro Schüler einen **iCal-Feed mit allen Terminen** — Ferien, Konferenzen, AGs, und ganz wichtig: die offiziellen Klassenarbeiten und Lernkontrollen mit exaktem Datum und Fach. Der Feed ist authoritativ. Manuell abzutippen ist Redundanz, Fehlerquelle und Pflegeaufwand bei Verschiebungen.

Phase 15 macht den Feed zur Quelle: die App lädt, parst, filtert auf KAs und schreibt direkt in `scheduled_events`.

## 2. Ziel

Clemens' KAs werden automatisch und idempotent aus dem Schulportal-Feed synchronisiert. Verschobene KAs bleiben aktuell, stornierte verschwinden (sofern keine Note dranhängt), manuell ergänzte Topics/Notes überleben jeden Sync.

## 3. Nicht-Ziele

- Kein Import anderer Event-Typen (Ferien, Konferenzen, Wandertage) — `scheduled_events` bleibt **Lernanlässe only**.
- Keine Multi-Feed-Unterstützung pro Profil (genau eine URL).
- Kein Mapping-Wizard-UI — Subject-Mapping ist hardcoded + `SUBJECTS_ALL`-Erweiterung deckt die Realität ab.
- Kein Preview-Dialog vor Sync — Diff wird direkt angewendet, Toast meldet das Ergebnis.
- Kein Background-Polling während App läuft — Auto-Sync nur einmal pro Profil-Wechsel/App-Start, 24h Throttle.
- Keine externen HTTP-Libraries (Requests/httpx) — `urllib.request` reicht.
- Kein Auto-Sync-Toggle in der UI — URL gesetzt = Sync aktiv; URL leer = Sync inaktiv.

## 4. Architektur-Übersicht

```
src/school_test_engine/
├── ical_sync/                          NEU — Domain-Paket
│   ├── __init__.py
│   ├── fetcher.py                      HTTP-Download via urllib (10s timeout)
│   ├── parser.py                       icalendar-Lib wrappen → RawVEvent
│   ├── classifier.py                   is_klausur_event() — UID-Match
│   ├── subject_map.py                  "Mathematik"→"Mathe" etc.
│   ├── extractor.py                    RawVEvent → EventRecord
│   └── service.py                      sync_feed() — Orchestrator + Diff
├── storage/
│   ├── migrations/011_ical_sync.sql    NEU — Schema-Erweiterung
│   ├── events_repo.py                  MOD — list_with_external_uid, update_by_external_uid, create um external_uid/source
│   └── users_repo.py                   MOD — ical_feed_url, ical_last_sync_at, ical_last_sync_summary
├── ui/
│   ├── _subjects.py                    MOD — SUBJECTS_ALL erweitert
│   ├── sync_worker.py                  NEU — QThread-Wrapper für service.sync_feed
│   └── pages/
│       ├── profile_edit.py             MOD — iCal-URL-Feld in neuer Sektion
│       ├── events.py                   MOD — Sync-Button + Status-Zeile + Toast
│       └── menu.py                     MOD — reload-on-sync-Signal connect
└── ui/main_window.py                   MOD — App-Start-Sync-Hook + events_synced Signal
```

**Neue Dep:** `icalendar` (PyPI) in `pyproject.toml`.

**Datenfluss:**

```
URL (users.ical_feed_url)
  → fetcher.fetch_feed()      → bytes
  → parser.parse_events()     → list[RawVEvent]
  → classifier.is_klausur_event() filter
  → extractor.to_event_record() → list[EventRecord]
  → service._diff()           → (adds, updates, deletes)
  → service._apply()          → DB-Mutationen
  → SyncResult                → UI-Toast + Reload-Signal
```

## 5. Datenmodell

### 5.1 Migration 011 (`011_ical_sync.sql`)

```sql
-- users-Erweiterung
ALTER TABLE users ADD COLUMN ical_feed_url TEXT;
ALTER TABLE users ADD COLUMN ical_last_sync_at TEXT;
ALTER TABLE users ADD COLUMN ical_last_sync_summary TEXT;

-- scheduled_events-Erweiterung
ALTER TABLE scheduled_events ADD COLUMN external_uid TEXT;
ALTER TABLE scheduled_events ADD COLUMN external_source TEXT;

-- Partial UNIQUE-Index: erlaubt NULL für manuelle Einträge,
-- garantiert Eindeutigkeit pro User für UID-Match.
CREATE UNIQUE INDEX idx_events_external_uid
  ON scheduled_events(user_id, external_uid)
  WHERE external_uid IS NOT NULL;
```

`ical_last_sync_summary` enthält kompaktes JSON (`{"added":3,"updated":1,"deleted":0,"error":null}`), damit die Events-Page nach App-Neustart den letzten Sync-Status anzeigen kann — speziell wichtig für Fehler aus stillem Auto-Sync.

`external_source` ist nullable und enthält aktuell nur `'schulportal_hessen'` — Audit-Spalte für später, wenn weitere Quellen dazukommen.

### 5.2 SUBJECTS_ALL-Erweiterung (`ui/_subjects.py`)

**Vorher:** `["Mathe", "Englisch", "Bio", "Physik", "Chemie", "Geschichte"]`

**Nachher** (pädagogische Reihenfolge — Hauptfächer, NaWi, Gesellschaft, Sonstige):

```python
SUBJECTS_ALL = [
    "Mathe", "Englisch", "Deutsch",
    "Bio", "Physik", "Chemie",
    "Geschichte", "Geographie", "Politik und Wirtschaft",
    "Religion", "Musik",
]
```

**Subject-Pill-Varianten** werden über die 6 bestehenden Klassen (tea/clay/paper/rose/honey/sky) per deterministischem Modulo verteilt — keine neuen QSS-Klassen.

### 5.3 EventRecord-Dataclass (`ical_sync/extractor.py`)

```python
@dataclass(frozen=True)
class EventRecord:
    external_uid: str        # full iCal UID, e.g. "20010101T000001-klausur-9084-…"
    subject: str             # nach Mapping (z.B. "Mathe", nicht "Mathematik")
    kind: str                # 'klassenarbeit' | 'klausur' | 'test'
    event_date: str          # ISO YYYY-MM-DD
```

### 5.4 SyncResult-Dataclass (`ical_sync/service.py`)

```python
@dataclass(frozen=True)
class SyncResult:
    added: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0          # erkannt aber DESCRIPTION-Format-Mismatch
    error: str | None = None
    synced_at: str = ""       # ISO datetime
```

## 6. Pipeline-Module

### 6.1 `fetcher.py`

```python
class FeedFetchError(Exception):
    pass

def fetch_feed(url: str, timeout: float = 10.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "LearningBuddy/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise FeedFetchError(f"HTTP {resp.status}")
            return resp.read()
    except urllib.error.URLError as e:
        raise FeedFetchError(f"Netzwerk-Fehler: {e.reason}") from e
    except TimeoutError as e:
        raise FeedFetchError("Timeout — keine Antwort vom Server") from e
```

### 6.2 `parser.py`

Wrapt `icalendar.Calendar.from_ical()` und gibt **stdlib-only** Dataclasses zurück, damit der Rest der App nicht direkt von der Library abhängt.

```python
@dataclass(frozen=True)
class RawVEvent:
    uid: str
    summary: str
    description: str
    dtstart_date: str             # immer ISO YYYY-MM-DD, normalisiert
    categories: tuple[str, ...]

def parse_events(ics_bytes: bytes) -> list[RawVEvent]:
    cal = icalendar.Calendar.from_ical(ics_bytes)
    out: list[RawVEvent] = []
    for comp in cal.walk("VEVENT"):
        dtstart = comp.get("DTSTART")
        if dtstart is None:
            continue
        dt = dtstart.dt
        iso_date = dt.date().isoformat() if isinstance(dt, datetime) else dt.isoformat()
        out.append(RawVEvent(
            uid=str(comp.get("UID", "")),
            summary=str(comp.get("SUMMARY", "")),
            description=str(comp.get("DESCRIPTION", "")),
            dtstart_date=iso_date,
            categories=_categories(comp),
        ))
    return out
```

### 6.3 `classifier.py`

Eine Funktion, ein Marker:

```python
_KLAUSUR_MARKER = "-klausur-"

def is_klausur_event(event: RawVEvent) -> bool:
    return _KLAUSUR_MARKER in event.uid
```

Erkenntnis aus der Feed-Analyse: alle 12 Klassenarbeiten/Lernkontrollen für Clemens (R8b) haben diesen Marker im UID. Ferien, Konferenzen, Wandertage etc. nicht. Trotz `CATEGORIES:Arbeiten` enthält diese Kategorie auch Nicht-KAs (Kompass-AG, Mathematikwettbewerb, Probenwochenenden) — der UID-Marker ist die einzig zuverlässige Quelle.

### 6.4 `subject_map.py`

```python
DEFAULT_SUBJECT_MAP: dict[str, str] = {
    "Mathematik": "Mathe",
    "Religion - evangelisch": "Religion",
    "Religion - katholisch": "Religion",
    "Religion - ethisch": "Religion",
    "Ethik": "Religion",
    "Erdkunde": "Geographie",
    "PoWi": "Politik und Wirtschaft",
    "Sozialkunde": "Politik und Wirtschaft",
}

def map_subject(raw: str) -> str:
    return DEFAULT_SUBJECT_MAP.get(raw.strip(), raw.strip())
```

Unbekannte Fächer werden as-is durchgereicht — `SUBJECTS_ALL` ist editierbar, neue Werte landen einfach in der DB.

### 6.5 `extractor.py`

```python
_DESC_PATTERN = re.compile(
    r"^(?P<kind_label>Arbeit|Lernkontrolle|Klausur)\s+in\s+"
    r"(?P<subject>.+?)"
    r"(?:\s+R\d+[a-z]?)?"
    r"\s*\([^)]+\)\s*$"
)

_KIND_MAP = {
    "Arbeit": "klassenarbeit",
    "Lernkontrolle": "test",
    "Klausur": "klausur",
}

def to_event_record(event: RawVEvent) -> EventRecord | None:
    m = _DESC_PATTERN.match(event.description.strip())
    if m is None:
        return None              # DESCRIPTION-Mismatch → skip + skipped++
    return EventRecord(
        external_uid=event.uid,
        subject=map_subject(m.group("subject").strip()),
        kind=_KIND_MAP[m.group("kind_label")],
        event_date=event.dtstart_date,
    )
```

**Designentscheidung:** kein SUMMARY-Fallback (YAGNI). Beim Auftreten von DESCRIPTION-Mismatch in echten Daten wird's später erweitert.

### 6.6 `service.py` — Diff & Apply

```python
def sync_feed(conn: sqlite3.Connection, user_id: int) -> SyncResult:
    user = users_repo.get(conn, user_id)
    if not user or not user["ical_feed_url"]:
        return SyncResult(error="Keine Feed-URL hinterlegt")
    try:
        raw_bytes = fetcher.fetch_feed(user["ical_feed_url"])
        events = parser.parse_events(raw_bytes)
    except (FeedFetchError, ValueError) as e:
        return _persist_error(conn, user_id, str(e))
    klausuren = [e for e in events if classifier.is_klausur_event(e)]
    records: list[EventRecord] = []
    skipped = 0
    for v in klausuren:
        rec = extractor.to_event_record(v)
        if rec is None:
            skipped += 1
        else:
            records.append(rec)
    adds, updates, deletes = _diff(conn, user_id, records)
    _apply(conn, user_id, adds, updates, deletes)
    return _persist_summary(conn, user_id, len(adds), len(updates), len(deletes), skipped)
```

**`_diff()`** matched per `external_uid`:

```python
def _diff(conn, user_id, feed_records):
    feed_by_uid = {r.external_uid: r for r in feed_records}
    db_rows = events_repo.list_with_external_uid(conn, user_id)
    db_by_uid = {r["external_uid"]: r for r in db_rows}

    adds = [r for uid, r in feed_by_uid.items() if uid not in db_by_uid]
    updates = [
        (r, db_by_uid[r.external_uid])
        for uid, r in feed_by_uid.items()
        if uid in db_by_uid and _has_changes(r, db_by_uid[uid])
    ]
    delete_candidates = [
        row for uid, row in db_by_uid.items() if uid not in feed_by_uid
    ]
    deletes = [
        row for row in delete_candidates
        if not assessments_repo.exists_for_event(conn, row["id"])
    ]
    return adds, updates, deletes

def _has_changes(rec, db_row) -> bool:
    return (
        rec.event_date != db_row["event_date"]
        or rec.subject != db_row["subject"]
        or rec.kind != db_row["kind"]
    )
```

**Drei Eigenschaften:**
1. Match per UID, nicht Datum+Subject → verschobene KAs werden erkannt, nicht doppelt eingetragen
2. `_has_changes` vergleicht nur Feed-kontrollierte Felder — `topics` + `note` bleiben unangetastet
3. Delete-Filter prüft Assessments — keine Note-Waisen

**`_apply()`** ist straightforward:

```python
def _apply(conn, user_id, adds, updates, deletes):
    for rec in adds:
        events_repo.create(
            conn, user_id,
            subject=rec.subject, kind=rec.kind, event_date=rec.event_date,
            external_uid=rec.external_uid,
            external_source="schulportal_hessen",
        )
    for rec, _ in updates:
        events_repo.update_by_external_uid(
            conn, user_id, rec.external_uid,
            subject=rec.subject, kind=rec.kind, event_date=rec.event_date,
        )
    for row in deletes:
        events_repo.delete(conn, row["id"])
```

### 6.7 Repo-Erweiterungen (`events_repo.py`)

Drei neue Funktionen, plus optionale Parameter auf `create()`:

```python
def create(..., external_uid: str | None = None, external_source: str | None = None) -> int: ...
def list_with_external_uid(conn, user_id) -> list[sqlite3.Row]: ...
def update_by_external_uid(conn, user_id, external_uid, *, subject, kind, event_date) -> None: ...
```

In `users_repo.update_user` kommen drei neue Sentinel-Parameter: `ical_feed_url`, `ical_last_sync_at`, `ical_last_sync_summary`.

## 7. UI-Berührungspunkte

### 7.1 Profile-Edit-Page

Neue Sektion **„Schulkalender"** nach dem Schul-Kontext-Block (Phase 9):

```
─── Schulkalender ───────────────────────────────

iCal-Feed-URL:  [QPlainTextEdit, word-wrap, max 4 Zeilen ]

                Findest du im Schulportal unter
                "Kalender → Export → iCal".
─────────────────────────────────────────────────
```

- `QPlainTextEdit` statt `QLineEdit` (URL ist ~250 Zeichen mit Token)
- Helper-Text in `paper-300` grau drunter
- Validierung beim Speichern: muss mit `https://` anfangen oder leer sein

### 7.2 Events-Page (`pages/events.py`)

Header-Erweiterung über der bestehenden Termin-Liste:

```
┌─ TERMINE ────────────────────────────────────────────────────┐
│  Termine                                                      │
│                                                               │
│  [+ Neuer Termin]   [↻ Synchronisieren]                       │
│                                                               │
│  Zuletzt synchronisiert: vor 2 Stunden · 12 KAs               │
│                                                               │
│  ─────────────────────────────────────────────────────────    │
│  (Liste wie bisher)                                           │
└───────────────────────────────────────────────────────────────┘
```

**Status-Label-Zustände:**

| Zustand | Text |
|---|---|
| Keine URL hinterlegt | „Schulkalender nicht verknüpft · [→ einrichten]" (Link zur Profile-Edit) |
| Frisch synchronisiert (0/0/0) | „Zuletzt synchronisiert: vor X · 12 KAs · bereits aktuell" |
| Mit Diff | „Zuletzt synchronisiert: vor X · 12 KAs · 3 neu, 1 verschoben" |
| Aktiv synchronisiert | „Synchronisiere…" + Button greyed |
| Fehler | Rote Schrift: „Letzter Sync fehlgeschlagen: <reason>" |

Sync-Toast (Inline, 4s ein-/ausgeblendet) zeigt das Resultat des aktuellen Sync — überlagert nicht das persistente Status-Label.

### 7.3 SyncWorker (`ui/sync_worker.py`)

```python
class SyncWorker(QObject):
    finished = Signal(object)  # SyncResult

    def __init__(self, db_path: str, user_id: int):
        super().__init__()
        self.db_path = db_path
        self.user_id = user_id

    def run(self) -> None:
        # Eigene Connection im Worker-Thread (SQLite ist nicht thread-shared)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            result = ical_sync.service.sync_feed(conn, self.user_id)
        finally:
            conn.close()
        self.finished.emit(result)
```

**Caller-Pattern** in `EventsPage._start_sync()`:

```python
def _start_sync(self) -> None:
    if self._sync_thread is not None:
        return    # Guard: nur ein Sync gleichzeitig
    self._sync_thread = QThread()
    self._sync_worker = SyncWorker(self._db_path, self.user_id)
    self._sync_worker.moveToThread(self._sync_thread)
    self._sync_thread.started.connect(self._sync_worker.run)
    self._sync_worker.finished.connect(self._on_sync_done)
    self._sync_worker.finished.connect(self._sync_thread.quit)
    self._sync_thread.finished.connect(self._sync_thread.deleteLater)
    self._sync_thread.start()
    self._show_syncing_state()
```

**Dependency-Injection für Tests:** `EventsPage(conn, user_id, *, sync_runner=None)` — wenn `sync_runner` gesetzt, wird der synchron statt im QThread aufgerufen.

### 7.4 App-Start-Hook in `MainWindow`

```python
def _on_user_changed(self, user_id: int) -> None:
    # ... bestehender Code ...
    self._maybe_trigger_background_sync(user_id)

def _maybe_trigger_background_sync(self, user_id: int) -> None:
    user = users_repo.get(self.db_conn, user_id)
    if not user or not user["ical_feed_url"]:
        return
    if _is_recent_sync(user["ical_last_sync_at"], hours=24):
        return
    self._start_sync(silent=True)
```

**`silent=True`** unterdrückt den Inline-Status-Wechsel auf der Events-Page (falls nicht offen) und zeigt nur einen kurzen Toast in der Top-Bar wenn neue KAs reinkamen (`"3 neue KAs aus Schulkalender"`). Bei 0 Adds: stumm.

### 7.5 events_synced-Signal

`MainWindow` bekommt ein neues `events_synced = Signal()`, das nach erfolgreichem Sync emittiert wird. Drei Pages connecten ihre `reload()`-Methoden:

- `EventsPage.reload()`
- `MenuPage.reload()` (KA-Hero-Card neu rendern)
- `GradesPage.reload()` (KA-Liste pro Fach)

Lose Kopplung — keine Page weiß von den anderen.

## 8. Error-Handling

| Fehler | Wo | Toast | Persistent in `ical_last_sync_summary` |
|---|---|---|---|
| Keine URL | service early-return | (n/a) | nicht persistiert |
| Netzwerk / DNS | fetcher | „Netzwerk-Fehler: …" | `{"error":"Netzwerk-Fehler: …"}` |
| Timeout >10s | fetcher | „Timeout — keine Antwort" | analog |
| HTTP 401/403 | fetcher | „Token abgelaufen oder ungültig" | analog |
| Kein gültiger iCal | parser | „Feed-Format nicht erkannt" | analog |
| 0 KAs aus Feed | service | (kein Fehler — `SyncResult(0,0,0)`) | normal persistiert |
| DESCRIPTION-Mismatch | extractor | (kein Fehler — `skipped++`) | im Summary mitgezählt |

## 9. Edge Cases

**User-Wechsel während laufendem Sync.** Worker hat `user_id` eingefroren, schreibt korrekt für den ursprünglichen User. `_on_sync_done` prüft `if self.user_id != worker.user_id: return` — UI-Update wird verworfen, DB bleibt konsistent.

**App-Close während Sync.** `closeEvent` ruft `self._sync_thread.quit(); self._sync_thread.wait(2000)`. Bei Timeout (>2s) Hard-Stop; SQLite ist WAL-crash-safe.

**Manueller + Auto-Sync-Race.** `_start_sync()` guard auf `self._sync_thread is not None` — Button-Klick wird stumm geschluckt wenn Auto-Sync schon läuft. Button wird in dem Zustand greyed out.

**Idempotenz.** Service ist bei jedem Aufruf idempotent. Bei Crash zwischen `_diff` und `_apply` wird der nächste Sync den verbleibenden Diff sauber abarbeiten.

## 10. Test-Strategie

**+25 neue Tests** (283 → ~308). Aufteilung:

### 10.1 Parser-Tests (`tests/ical_sync/test_parser.py`, ~6 Tests)

Fixture: `tests/fixtures/schulkalender_mini.ics` (~80 Zeilen handgepflegt, von echtem Feed abgeleitet) mit:
- 1 echte KA-Event
- 1 Ferien-Event
- 1 Wandertag (CATEGORIES:Veranstaltung)
- 1 multi-line DESCRIPTION (line-folded)
- 1 DTSTART;VALUE=DATE
- 1 DTSTART;TZID=Europe/Berlin

Tests:
- `test_parse_returns_all_vevents()` — Anzahl stimmt
- `test_parse_extracts_uid_and_summary()`
- `test_parse_dtstart_date_only_returns_iso_date()`
- `test_parse_dtstart_with_tz_returns_iso_date()`
- `test_parse_handles_multiline_description()` — iCal line-folding
- `test_parse_invalid_bytes_raises_value_error()`

### 10.2 Classifier-Tests (~2 Tests)

- `test_klausur_uid_returns_true()`
- `test_ferien_uid_returns_false()`

### 10.3 Extractor-Tests (~5 Tests)

- `test_description_pattern_arbeit_in_mathematik()` → kind=klassenarbeit, subject=Mathe
- `test_description_pattern_lernkontrolle_in_chemie()` → kind=test, subject=Chemie
- `test_description_pattern_religion_evangelisch()` → subject=Religion
- `test_description_pattern_unknown_format_returns_none()`
- `test_subject_mapping_unchanged_passthrough()` → "Englisch" → "Englisch"

### 10.4 Service-Tests (`tests/ical_sync/test_service.py`, ~7 Tests, in-memory DB)

- `test_sync_inserts_new_klausuren()`
- `test_sync_is_idempotent()` — 2× sync, 2. Mal 0 adds/updates/deletes
- `test_sync_updates_changed_date_keeps_topics()`
- `test_sync_deletes_removed_event_without_note()`
- `test_sync_keeps_removed_event_with_note()`
- `test_sync_returns_error_on_network_failure()` — Mock-Fetcher raises FeedFetchError
- `test_sync_skips_non_klausur_events()`

### 10.5 Schema/Subjects-Tests (~2 Tests)

- `test_subjects_all_includes_new_fields()`
- `test_migration_011_adds_columns()` — Schema-Check via PRAGMA table_info

### 10.6 UI-Sync-Tests (`tests/test_events_page_sync.py`, ~3 Tests)

Via injizierbarem `sync_runner` (Dependency Injection statt QThread):

- `test_sync_button_calls_runner()`
- `test_sync_button_disabled_during_run()`
- `test_sync_result_toast_shows_counts()`

**Threading-Tests bewusst weggelassen** — `SyncWorker` ist Glue-Code, sein Verhalten ist über die Service-Tests + manuelles Smoke-Testing abgedeckt.

## 11. Migration und Rollout

1. Migration 011 läuft automatisch beim nächsten App-Start (additive Spalten, kein Daten-Verlust-Risiko).
2. Bestehende Profile haben `ical_feed_url=NULL` → kein Auto-Sync, kein Verhaltensunterschied.
3. Matthias trägt für Clemens-Profil die URL ein → erster manueller Sync via Button → 12 KAs erscheinen.
4. Manuelle Termine, die zufällig zu importierten KAs passen, bleiben als getrennte Einträge (kein Auto-Merge — User kann manuell aufräumen).

## 12. Aufwand-Schätzung

Aus Feature-Komplexität und Phase-7-Referenz (ähnlicher Scope): **~12-15 Tasks**, davon:
- 1 Spec-Commit, 1 Plan-Commit
- 1 Migration + 1 SUBJECTS_ALL-Erweiterung
- 5 Pipeline-Module (fetcher, parser, classifier, subject_map, extractor)
- 1 Service mit Diff/Apply
- 1 Repo-Erweiterung (events_repo + users_repo)
- 1 SyncWorker
- 2 UI-Pages (profile_edit, events) + 1 Signal in MainWindow
- 1 Acceptance/Cleanup

Test-Suite: 283 → ~308 grün.

## 13. Offene Punkte / Out-of-Scope für später

- **Subject-Mapping-Override per User**: Aktuell hardcoded — falls Clemens' Schule mal ungewöhnliche Subject-Strings nutzt, müsste man eine User-spezifische Map-Tabelle anlegen. YAGNI bis Beweis des Gegenteils.
- **Mehrere Feeds pro Profil**: Falls Clemens mal zur Oberstufe wechselt und es mehrere parallele Kalender gibt. YAGNI.
- **Anderes iCal-Format**: Schulportal-Hessen-Format ist die einzige Quelle. Bei anderem Anbieter müsste der UID-Marker konfigurierbar werden.
- **Background-Sync während App läuft**: Throttle 24h reicht; Profil-Wechsel triggert frischen Sync. Falls jemand die App tagelang offen lässt, kommen neue KAs erst nach Restart.

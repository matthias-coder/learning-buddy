# Phase 10 — Daily-5 (Design Spec)

**Status:** Draft, awaiting user approval
**Datum:** 2026-05-14
**Vorgänger-Phase:** 9 (Schul-Kontext)
**Nachfolger-Kandidaten:** Phase 11 (Spaced Repetition als Algorithmus-Erweiterung), Foto-OCR, Direct AI-API-Calls, Karteikarten-Modus

## 1. Zweck & Motivation

Clemens hat heute zwei Wege zu üben: a) regulär in der Library einen Test auswählen, b) per Phase-5-Study-Mode aus einem schwachen Topic einen synthetischen Test bauen. Beides ist deliberat — er muss aktiv "lass-mich-üben"-entscheiden.

Phase 10 ergänzt einen niederschwelligen **täglichen Lern-Rhythmus**: jeden Tag steht eine vorbereitete 5-Fragen-Session bereit, automatisch zusammengestellt aus seinen schwächsten Topics. Eine Daily-5-Card auf dem Hauptmenü signalisiert "es gibt was zu tun" und nach Abschluss "✓ heute geschafft". Ein dezenter Streak-Counter belohnt Konsistenz ohne Drama.

**Zielnutzer:** Clemens. UX muss in < 30 Sekunden vom Hauptmenü zu Lernen-Beginn führen.

**Bewusst nicht in Phase 10** *(future work)*:
- **Spaced Repetition Algorithmus** — entscheidet welche Fragen wann wieder dran sind, mit eskalierenden Intervallen. Phase 11.
- Dedup über Tage hinweg ("gestern schon gefragt"). Phase 10 zieht jeden Tag frisch; mehrfaches Auftauchen ist OK.
- Streak-Recovery / Streak-Freezes
- Badges / Trophies / Levels
- Push-Notifications / Erinnerungen
- Geräte-übergreifende Streaks

## 2. Datenmodell — Migration 009

Eine kleine neue Tabelle, keine Schema-Änderungen auf Bestand:

```sql
-- Phase 10: Daily-5 Session-Tracking
CREATE TABLE IF NOT EXISTS daily_sessions (
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_date TEXT    NOT NULL,                          -- ISO YYYY-MM-DD (lokaler Tag)
    test_id      INTEGER REFERENCES tests(id) ON DELETE SET NULL,
    attempt_id   INTEGER REFERENCES attempts(id) ON DELETE SET NULL,
    started_at   TEXT    NOT NULL,
    completed_at TEXT,                                      -- NULL bis Runner-Abschluss
    PRIMARY KEY (user_id, session_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_user_date
    ON daily_sessions(user_id, session_date);
```

**Begründungen:**
- Composite PK `(user_id, session_date)` verhindert mehrere Sessions am gleichen Tag pro User.
- `test_id` referenziert den synthetischen Daily-5-Test (für Cleanup falls test gelöscht).
- `attempt_id` ist der Hook-Punkt für `finalize_if_daily` und auch der Resume-Anker für Save-and-Resume (Phase 2).
- `started_at` + `completed_at` als ISO-Strings (konsistent mit attempts).
- **Kein Streak-Speicher**: Streak wird On-Demand aus `daily_sessions` berechnet — keine Sync-Probleme.

**Migrations-Falle**: Pure CREATE TABLE — keine SQLite-ALTER-FK-Trap.

## 3. Code-Struktur

### 3.1 Neues Domain-Package `daily/`

Parallel zu `cockpit/`, `study/`, `prompt_builder/`. Drei kleine Module:

**`daily/builder.py`** exposes zwei Funktionen:

`has_enough_questions(conn, user_id) -> bool` — billiger Check ohne Build, nutzt `COUNT(DISTINCT q.id) WHERE q.test_id IN (user's tests) AND test.is_study = 0 >= 5`. Wird von MenuPage gerufen um State zu bestimmen ohne synthetic-Test zu erstellen.

`build_daily_test(conn, user_id, today) -> int | None`:
- Liest `topic_stats(user_id)` aus Phase 7's bestehendem Code
- Wenn user hat < 5 beantwortete Fragen total → return `None` (Card zeigt "Importiere zuerst Tests")
- Wählt 5 Fragen nach 2-2-1-Schema aus den 3 schwächsten Topics:
  - 2 zufällige Fragen aus dem schwächsten Topic
  - 2 aus dem zweitschwächsten
  - 1 aus dem drittschwächsten
  - Bei < 2 vorhandenen Fragen in einem Topic: nimm vorhandene, fülle aus dem nächsten Topic
- Wenn keine schwachen Topics (alle ≥ 80% mastery): 5 zufällige Fragen aus allen Tests des Users
- Erstellt synthetic Test:
  - `title = "Daily-5 — {today.strftime('%d.%m.%Y')}"`
  - `subject = "Daily-5"` (Marker, vermeidet KA-Subject-Match in Phase 7-Aggregaten)
  - `is_study = 1`
  - `notenschluessel = {1:[100,90], 2:[89,75], 3:[74,60], 4:[59,45], 5:[44,20], 6:[19,0]}`
  - `points_total = sum(q.points for q in chosen)`
- Kopiert Fragen-Objekte in neue `questions`-Rows mit `test_id = new_test_id` (Phase-5-Study-Pattern)
- Returns: `new_test_id`

**`daily/streak.py`** — `current_streak(conn, user_id, today: date) -> int`:
- Holt completed_at-Daten der letzten 365 Tage als Set
- Iteriert rückwärts von heute (oder gestern wenn heute nicht erledigt)
- Zählt aufeinanderfolgende Tage mit `completed_at != NULL`
- Stoppt beim ersten fehlenden Tag

**`daily/finalize.py`** — `finalize_if_daily(conn, attempt_id) -> bool`:
- Findet daily_sessions-Row mit `attempt_id = ?` und `completed_at IS NULL`
- Wenn vorhanden: setzt `completed_at = datetime('now')`, returns True
- Sonst: returns False (attempt war kein Daily-5)

### 3.2 Neues Repository `storage/daily_sessions_repo.py`

```python
def get_for_today(conn, user_id, today: str) -> sqlite3.Row | None
def start_session(conn, user_id, today: str, test_id: int, attempt_id: int, started_at: str) -> None
def complete_session(conn, user_id, today: str, completed_at: str) -> None
def list_recent_completed_dates(conn, user_id, since: str, until: str) -> list[str]
def find_by_attempt(conn, attempt_id: int) -> sqlite3.Row | None
```

Alle Operationen sind user-scoped. `start_session` macht INSERT (PK verhindert Doppel-Start am selben Tag).

### 3.3 Neues Widget `widgets/daily_card.py`

Hero-Card im Kessler-Stil (analog ExamCard aus Phase 7). Faktor-Funktion:

```python
def DailyCard(
    state: Literal["no_library", "due", "done"],
    streak: int,
    last_grade: int | None = None,
    parent=None,
) -> ClickableCard:
    ...
```

Vier Zustände (gleich wie Spec §3):
- **no_library**: dezent, Hinweis-Text "Importiere zuerst Tests" — nicht klickbar
- **due, streak=0**: "DAILY-5 · heute · 5 Fragen, ~5 Min", Button "Starten →"
- **due, streak≥1**: zusätzlich "🔥 X Tage in Folge" (oder "🔥 1. Tag")
- **done**: "✓ DAILY-5 · heute geschafft · 🔥 X Tage in Folge · Note: Y" — Card gedimmt

`practice_clicked = Signal()` emittiert beim Starten-Click.

### 3.4 MenuPage-Erweiterung

In `ui/pages/menu.py` wird die `DailyCard` in BEIDE Layout-Varianten unten angehängt:

- **KA-Hero-Layout** (wenn anstehende KAs): KA-Strip → kompakte 4-Tile-Reihe → **DailyCard**
- **Empty-State-Layout** (keine KAs): Empty-State-Frame → 2×2-Grid → **DailyCard**

Card-Aktion: `daily_card.practice_clicked → self.window.start_daily_five()`.

Reload-Logik in `MenuPage.reload()`:
- Bestimme State via `daily_sessions_repo.get_for_today` + `daily/builder.has_enough_questions(conn, uid)`
- Bestimme Streak via `daily.current_streak(conn, uid, today)`
- Bestimme last_grade aus dem zugehörigen Attempt (nur bei State "done")

### 3.5 MainWindow-Erweiterung

```python
def start_daily_five(self) -> None:
    today = date.today().isoformat()
    uid = self.active_user_id
    # If already done today, no-op (defensive)
    existing = daily_sessions_repo.get_for_today(self.conn, uid, today)
    if existing and existing["completed_at"]:
        return
    # Resume in-progress session if attempt exists
    if existing and existing["attempt_id"]:
        self.resume_attempt(existing["attempt_id"])
        return
    # Build new test + attempt + session row
    test_id = daily.builder.build_daily_test(self.conn, uid, date.today())
    if test_id is None:
        return  # not enough library — should not happen if card was clickable
    points = ...  # sum points_total from new test
    attempt_id = attempts_repo.start_attempt(self.conn, test_id, points, uid)
    daily_sessions_repo.start_session(
        self.conn, uid, today, test_id, attempt_id,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    self.runner_page.resume(attempt_id)  # Phase 2 resume-flow works since we have a started attempt
    self.stack.setCurrentWidget(self.runner_page)
```

Und hookt sich in den existing `show_results(attempt_id)` ein:

```python
def show_results(self, attempt_id: int) -> None:
    daily.finalize.finalize_if_daily(self.conn, attempt_id)   # NEW LINE
    self._return_to_history = (...)
    self.results_page.show_attempt(self.conn, attempt_id)
    self.stack.setCurrentWidget(self.results_page)
```

Nach Results-Verlassen → zurück zu MenuPage, deren `reload()` neu rendert und DailyCard auf State "done" springt.

### 3.6 Subject="Daily-5" Marker — Auswirkungen

Der Daily-5-Test hat `subject = "Daily-5"`. Konsequenzen für bestehende Features:

| Bereich | Verhalten |
|---------|-----------|
| Library | Daily-5-Tests erscheinen — User kann sie nochmal starten? **Nein** — wir filtern `WHERE is_study = 0` in Library (existing) |
| History | Daily-5-Attempts erscheinen mit Subject-Pill "Daily-5" — gewünscht |
| Phase 4 Gaps | Topic-Stats erhalten zusätzliche Rows mit `subject="Daily-5"`. **Kosmetisch**: Gaps-Filter "Alle Fächer" zeigt die korrekt, Subject-Pills "Daily-5" sichtbar. Akzeptiert für Phase 10. Granular-Filterung als Future. |
| Phase 7 Comparison | `comparison_for_assessment` filtert `WHERE t.subject = ?` mit KA-Subject (z.B. "Mathe") — `"Daily-5" != "Mathe"` → naturally excluded. **Kein Code-Change nötig in Phase 7.** |
| Phase 7 Aggregate | Same Logic. |

## 4. Frage-Auswahl-Algorithmus (daily/builder.py Detail)

```python
def _pick_questions_for_daily(conn, user_id, today: date) -> list[int]:
    """Return list of 5 question IDs, weighted toward weakest topics."""
    stats = topic_stats(conn, user_id)  # already sorted by mastery ASC
    
    # Filter to topics where user has ≥ 1 attempt
    weak_topics = [s for s in stats if (s['earned'] / s['possible']) < 0.80][:3]
    
    chosen: list[int] = []
    fallback_pool: list[int] = []
    
    quota = [2, 2, 1]  # 2-2-1 from top-3 weakest
    for idx, topic in enumerate(weak_topics):
        q_ids = _pick_random_questions_for_topic(conn, user_id, topic['topic'], n=quota[idx])
        chosen.extend(q_ids)
    
    # Fallback fill if any topic was short
    while len(chosen) < 5:
        fallback_pool = _pick_random_questions_global(conn, user_id, exclude=chosen, n=5-len(chosen))
        if not fallback_pool:
            break
        chosen.extend(fallback_pool)
    
    return chosen[:5]
```

Wenn `weak_topics` leer (User ist überall stark): nimm 5 zufällige aus dem globalen Pool.

Wenn `len(chosen) < 5` nach Fallback: User hat zu wenig Fragen — return empty → Card zeigt "Importiere zuerst Tests".

## 5. Streak-Berechnung

```python
def current_streak(conn, user_id, today: date) -> int:
    since = (today - timedelta(days=400)).isoformat()
    completed = set(daily_sessions_repo.list_recent_completed_dates(
        conn, user_id, since=since, until=today.isoformat(),
    ))
    
    streak = 0
    cursor = today
    if cursor.isoformat() not in completed:
        # If today not done yet, streak counts from yesterday
        cursor -= timedelta(days=1)
    while cursor.isoformat() in completed:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
```

**Display-Logik**:
- `streak == 0`: kein Streak-Text gezeigt
- `streak == 1`: "🔥 1. Tag"
- `streak ≥ 2`: "🔥 {streak} Tage in Folge"

## 6. Edge Cases

| Fall | Verhalten |
|------|-----------|
| User hat 0 Tests in Library | Card State "no_library" — nicht klickbar |
| User hat < 5 unique Fragen beantwortet | Card State "no_library" |
| User startet Session, schließt App | daily_sessions-Row hat `attempt_id` aber `completed_at = NULL`. Nächste Aufruf zeigt "Daily-5 fortsetzen" — Klick ruft `resume_attempt` |
| User wechselt Profil mitten in Session | Andere User sehen ihre eigene Session-Tabelle — nichts vermischt |
| Streak-Berechnung bei DST-Wechsel | Wir nutzen ISO-Date-Strings basierend auf `date.today()` (lokaler Tag) — keine Zeitzonen-Probleme |
| Daily-5 am 23:59 begonnen, 00:01 abgeschlossen | `session_date` ist der Start-Tag. Session bleibt am Tag verankert wo sie begann. Streak wird mit diesem Datum gezählt. |
| User macht KA-Übung 24h vor KA + Daily-5 — was zählt in Phase-7-Comparison? | Daily-5 hat subject="Daily-5", wird durch Subject-Filter ausgeschlossen. Nur die KA-Mathe-Übung zählt. ✓ |
| `daily_sessions.attempt_id` referenziert gelöschten attempt | `ON DELETE SET NULL` → attempt_id wird NULL. completed_at bleibt — Streak-Berechnung sieht es als "abgeschlossen am Tag X". |

## 7. Tests

### Unit (TDD)
- `test_migration_009.py`: Tabelle existiert, PK enforce, CASCADE bei User-Delete
- `test_daily_sessions_repo.py`: start_session / complete_session / get_for_today / list_recent_completed_dates / find_by_attempt
- `test_daily_streak.py`:
  - Empty: streak = 0
  - 1 Tag heute completed: streak = 1
  - 1 Tag gestern, heute nicht angefangen: streak = 1 (zählt von gestern)
  - 3 Tage in Folge: streak = 3
  - Lücke: streak resettet bei Lücke
- `test_daily_builder.py`:
  - User hat 0 Fragen → returns None
  - User hat genug Fragen, 3 schwache Topics → 2-2-1 verteilung
  - User stark in allen Topics → 5 random
  - Topic mit < 2 Fragen → Fallback aus nächstem Topic
- `test_daily_finalize.py`:
  - finalize_if_daily mit valider open-Session → completes
  - finalize_if_daily mit non-daily attempt → no-op
  - finalize_if_daily mit bereits-completed Session → no-op

### Smoke (UI)
- DailyCard rendert in allen 4 States
- MenuPage zeigt DailyCard sowohl bei KA-Hero als auch Empty-State-Layout
- start_daily_five Hook + show_results-Hook funktionieren

### Manuell (Phase-10-Abschluss)
- Library mit ≥ 5 Fragen vorbereiten
- DailyCard State "due" sichtbar
- Klicken → Runner mit 5 Fragen
- Beantworten → Results → zurück → DailyCard zeigt "✓ heute geschafft"
- Weiteres Klick auf Card → no-op (bereits done)
- Test-Datum mocken (z.B. via SQL UPDATE auf session_date) → Streak inkrementiert über Tage

## 8. Akzeptanzkriterien

1. Migration 009 läuft sauber, `daily_sessions` existiert
2. DailyCard erscheint auf Hauptmenü in beiden Layout-Varianten
3. Card-Zustände wechseln korrekt: no_library → due → done
4. "Starten"-Klick → Runner mit 5 Fragen aus schwachen Topics (gewichtet 2-2-1)
5. Nach Test-Abschluss: DailyCard zeigt "✓ heute geschafft" inkl. erreichte Note
6. Streak-Counter zeigt korrekte Tagezahl, resettet bei Lücke
7. Daily-5-Test (subject="Daily-5") taucht NICHT in Phase-7-Comparison auf (Subject-Mismatch)
8. Daily-5-Attempts erscheinen normal in History mit "Daily-5"-Subject-Pill
9. Profil-Wechsel: Daily-Sessions sind user-isoliert
10. Alle 187 bestehenden Tests grün; neue Unit-Tests grün

## 9. Risiken

- **Pool zu klein bei Phase-10-Start**: Wenn Clemens erst wenige Tests importiert hat, ist Daily-5 unbrauchbar. Mitigation: State "no_library" mit klarem Hinweis-Text + Wait-Strategy bis genug Fragen da sind.
- **Gleiche Frage 2x dieselbe Woche**: Phase-10 hat keine Dedup-Logik. Mitigation: Phase 11 (Spaced Repetition) wird das adressieren. Akzeptiert für Phase 10.
- **Streak-Anreiz wirkt kontraproduktiv** wenn Clemens an einem Tag krank ist und einen ehrgeizigen Streak verliert: das war der Grund für die ursprüngliche "keine Gamification"-Entscheidung. **Matthias hat sich bewusst umentschieden** — wenn das Verhalten negativ wird, kann eine spätere Phase Streak-Freezes oder ganz-Disable einführen.
- **Topic-Schwäche-Signal überlappt mit Daily-5-Aktivität**: nach mehreren Daily-5-Sessions auf das gleiche schwache Topic wird dieses besser → topic_stats verbessern sich → andere Topics rücken auf Position 1. Das ist erwünschtes Verhalten (System lernt mit), nicht ein Risk.
- **Subject="Daily-5"-Marker pollutet topic_stats**: Phase-4-Gaps zeigt zusätzliche (topic, "Daily-5")-Rows. Akzeptiert für Phase 10. Kann später aggregiert werden indem Gaps subject="Daily-5" wegfiltert.

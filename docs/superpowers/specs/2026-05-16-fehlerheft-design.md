# Phase 16 — Fehlerheft

**Status:** Design / Spec
**Datum:** 2026-05-16
**Vorgängerphase:** Phase 15 (iCal-Sync) + zwei UX-Polish-Wellen
**Typ:** Feature-Phase ohne Migration, neues Domain-Paket + eine UI-Page

---

## 1. Motivation

Das Lücken-Dashboard (Phase 4) zeigt Clemens **welche Topics hapern**. Es zeigt aber nicht, **welche einzelnen Fragen** er konkret falsch beantwortet hat. Wenn Clemens vor einer KA gezielt seine bisherigen Fehler nochmal anschauen will, muss er heute durch die History blättern, einzelne Versuche öffnen und in den Results scrollen — umständlich, und es gibt keinen „diese Fragen nochmal üben"-Pfad.

Phase 16 macht aus den schon vorhandenen falschen Antworten ein gefiltertes, persistentes „Fehlerheft" — eine Liste der Fragen, die noch nicht sitzen, mit einem One-Click-Button für synthetische Wiederholungs-Tests.

## 2. Ziel

Clemens hat pro Fach jederzeit Zugriff auf seine offenen Fehler und kann sie mit einem Klick als Übungstest spielen. Eine Frage gilt als „erledigt" und verschwindet, wenn er sie **zweimal in Folge** richtig beantwortet hat — Zufallstreffer fliegen also nicht direkt raus.

## 3. Nicht-Ziele

- **Keine neue Tabelle, keine Migration.** Wahrheitsquelle bleibt `answers`.
- **Kein Karten-Modus** (Frage-zeigen / Antwort-aufdecken). Geübt wird im normalen Test-Runner. Karteikarten sind ein eigenes Feature (Backlog).
- **Kein manuelles „als gelernt markieren".** Eviction ist regelbasiert.
- **Keine Cross-Profile-Aggregation.** Jeder Profil-User hat sein eigenes Fehlerheft.
- **Kein Import aus externen Quellen.** Heft entsteht ausschließlich aus eigenen Test-Versuchen.
- **Kein eigener Notenschlüssel / keine eigene Subject-Marke.** Übungstests laufen unter dem echten Fach (`subject="Mathe"` usw.) mit `is_study=1` — gleiches Pattern wie Phase-5-Topic-Übungen.

## 4. Architektur-Übersicht

```
src/school_test_engine/
├── error_book/                          NEU — Domain-Paket
│   ├── __init__.py
│   ├── models.py                        ErrorBookEntry Frozen-Dataclass
│   ├── queries.py                       list_open_entries, count_open
│   └── builder.py                       build_practice_test, has_open_errors
├── ui/
│   ├── pages/
│   │   ├── error_book.py                NEU — ErrorBookPage
│   │   └── gaps.py                      MOD — Footer-Button „Fehler nochmal üben"
│   └── widgets/global_header.py         MOD — Logo-Menü-Eintrag „Fehlerheft"
└── ui/main_window.py                    MOD — show_error_book, start_error_book_practice
```

**Keine** neue Tabelle, **keine** Migration, **kein** Hook im Runner-Submit-Pfad. Die View ist ein reiner Lese-Layer über bestehende Daten.

**Datenfluss:**

```
Tests-Runner submit → answers (existing path, unverändert)
                          ↓
   ErrorBookPage.reload() → queries.list_open_entries(conn, uid, subject)
                          ↓
         SQL: kandidaten + answer-Reihe per Frage (inkl. ext_id-Kopien)
                          ↓
         Python: consecutive_correct ≥ 2 → filtere raus
                          ↓
         Sortiert: wrong_count DESC, last_wrong_at DESC
                          ↓
   Page rendert pro-Fach-Liste + Üben-Button
                          ↓
   Üben-Click → builder.build_practice_test(uid, subject, limit=10)
              → kopiert ≤10 Fragen in neuen is_study=1-Test
              → ext_id = "err:{root_qid}" auf jeder Kopie
              → MainWindow startet Attempt im Runner
```

## 5. Datenmodell

### 5.1 Keine Schema-Änderungen

Genutzt werden ausschließlich bestehende Spalten:
- `answers (question_id, attempt_id, is_correct)`
- `attempts (id, test_id, finished_at, completed)`
- `tests (id, user_id, subject, is_study)`
- `questions (id, test_id, ext_id, topic, prompt, payload, ...)`

### 5.2 Identitäts-Brücke: `questions.ext_id` mit `err:`-Präfix

Beim Bau eines synthetischen Übungs-Tests werden Fragen kopiert (gleiches Verfahren wie `daily/builder.py`). Damit Antworten auf die Kopie für die Eviction des Originals zählen, bekommt die Kopie:

```
questions.ext_id = f"err:{root_question_id}"
```

`root_question_id` ist die `id` der **ursprünglich** falsch beantworteten Frage. Wenn die Quell-Frage selbst schon eine Fehler-Kopie ist (ihr `ext_id` matched `err:\d+`), wird die Wurzel rausgeparst — die Kette bleibt flach (max. 1 Level Indirektion).

Daily-5 setzt `ext_id` schon heute auf `"dq1"`, `"dq2"`, etc. — `err:`-Präfix ist konfliktfrei.

### 5.3 ErrorBookEntry (Frozen-Dataclass)

```python
@dataclass(frozen=True)
class ErrorBookEntry:
    question_id: int           # root_question_id (nie Kopie-id)
    subject: str
    topic: str
    prompt_excerpt: str        # erste ~80 Zeichen von questions.prompt
    wrong_count: int           # Gesamtzahl falscher Antworten (alle Versuche)
    last_wrong_at: str         # ISO datetime des jüngsten Fehlers
    consecutive_correct: int   # nur 0 oder 1 möglich — bei ≥2 wird der Eintrag in queries.list_open_entries vorher rausgefiltert
```

`consecutive_correct >= 2` → Eintrag wird in `queries.list_open_entries` vorher rausgefiltert und erscheint nicht in der Liste.

## 6. Query-Logik

### 6.1 Eligibility

Eine Frage ist Kandidat, wenn:

```sql
EXISTS (
    SELECT 1
    FROM answers a
    JOIN attempts att ON att.id = a.attempt_id
    JOIN tests t ON t.id = att.test_id
    WHERE a.question_id = :root_qid
      AND a.is_correct = 0
      AND att.completed = 1
      AND t.is_study = 0
      AND t.user_id = :user_id
)
```

Nur reguläre, abgeschlossene Tests zählen für die Eligibility. Wiederholungs-Übungen (`is_study=1`) bringen also keine **neuen** Einträge ins Heft.

### 6.2 Antwort-Reihe pro Frage (inkl. Kopien)

Für jeden Kandidaten `q` werden alle Antworten geladen — über zwei Pfade UNIONisiert:

```sql
-- direkter Pfad
SELECT a.is_correct, att.finished_at
FROM answers a
JOIN attempts att ON att.id = a.attempt_id
WHERE a.question_id = :root_qid AND att.completed = 1

UNION ALL

-- Kopie-Pfad
SELECT a.is_correct, att.finished_at
FROM answers a
JOIN attempts att ON att.id = a.attempt_id
JOIN questions q ON q.id = a.question_id
WHERE q.ext_id = 'err:' || :root_qid AND att.completed = 1

ORDER BY finished_at DESC
```

### 6.3 Eviction in Python

```python
def _is_resolved(answers_desc: list[Row]) -> bool:
    """True wenn die letzten 2 Antworten beide korrekt waren."""
    if len(answers_desc) < 2:
        return False
    return answers_desc[0].is_correct == 1 and answers_desc[1].is_correct == 1


def _consecutive_correct(answers_desc: list[Row]) -> int:
    """Zählt korrekte Antworten vom Neusten rückwärts bis zum ersten Fehler."""
    n = 0
    for a in answers_desc:
        if a.is_correct == 1:
            n += 1
        else:
            break
    return n
```

`list_open_entries` ruft beides auf, filtert resolved heraus, returnt sortiert nach `(-wrong_count, -last_wrong_at)`.

### 6.4 Subject-Filter und count_open

`list_open_entries(conn, user_id, subject=None)` — wenn `subject` gesetzt, JOIN-Filter auf `t.subject = :subject` (über Origin-Frage, also `questions.test_id → tests.subject`).

`count_open(conn, user_id) -> dict[str, int]` — Dictionary von Fach zu Anzahl offener Einträge. Wird gerufen für die Subject-Pill-Counts auf der Page.

## 7. Builder: Synthetischer Übungs-Test

### 7.1 `build_practice_test(conn, user_id, subject, limit=10) -> int | None`

```python
def build_practice_test(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str,
    limit: int = 10,
) -> int | None:
    """Baut einen Fehler-Übungs-Test. Returns test_id oder None bei 0 offenen."""
    # 1. Resume-Check: gibt's einen offenen Attempt für eine Fehler-Übung
    #    im selben Fach? Dann diesen test_id zurückgeben (kein Rebuild).
    existing = _find_open_practice_test(conn, user_id, subject)
    if existing is not None:
        return existing

    # 2. Lade offene Einträge, schwerste zuerst
    entries = queries.list_open_entries(conn, user_id, subject=subject)
    if not entries:
        return None
    entries = entries[:limit]

    # 3. Hole Origin-Question-Rows
    qids = [e.question_id for e in entries]
    questions = _load_questions(conn, qids)
    # ordered nach entries-Reihenfolge

    # 4. INSERT INTO tests (subject, is_study=1, title, ...) (Daily-5-Pattern)
    test_id = _insert_test(conn, user_id, subject, ...)

    # 5. INSERT INTO questions — kopiert payload, setzt ext_id = "err:{root}"
    _copy_questions_with_err_ext_id(conn, test_id, questions, root_ids=qids)

    conn.commit()
    return test_id
```

**Test-Row-Felder:**
- `subject = subject` (echtes Fach, nicht „Fehlerheft")
- `is_study = 1`
- `title = f"Fehler-Übung – {subject} – {today.strftime('%d.%m.%Y')}"`
- `description = "Wiederholung von Fragen, die noch nicht sitzen."`
- `notenschluessel` = `REALSCHULE_DEFAULT_NOTENSCHLUESSEL` (gleiche Konstante wie Daily-5)
- `source_json = '{}'`
- `time_limit_min = NULL`
- `user_id, imported_at` wie üblich

**Question-Copy:**
- Alle Felder werden 1:1 übernommen (`type`, `topic`, `difficulty`, `points`, `prompt`, `prompt_math`, `payload`, `explanation`)
- `position` = neue Index-Reihenfolge (schwerste zuerst)
- `ext_id = f"err:{root_qid}"` (root nach Flattening)

### 7.2 Root-Flattening

Wenn die Quell-Frage selbst eine Kopie ist:

```python
def _root_question_id(q_row) -> int:
    m = re.match(r"^err:(\d+)$", q_row.ext_id or "")
    return int(m.group(1)) if m else int(q_row.id)
```

So bleibt die ext_id-Kette stets bei genau einem Hop, egal wie oft Clemens das gleiche Heft übt.

### 7.3 `has_open_errors(conn, user_id, subject=None) -> bool`

Convenience-Wrapper, der intern `count_open` ruft und das Total (bzw. den Fach-Wert) gegen 0 vergleicht. Dient als Predicate für den Üben-Button-Enable-State.

## 8. UI

### 8.1 ErrorBookPage (`ui/pages/error_book.py`)

Layout-Reihenfolge:

1. **Eyebrow:** `FEHLERHEFT`
2. **Title:** „Was nochmal hakt" (Fraunces-28pt-Normal, gleicher Stil wie Grades-Page)
3. **Subject-Pill-Row** mit FlowLayout (analog `grades.py`):
   - Alle 11 Fächer aus `SUBJECTS_ALL`
   - Label-Format: `"Mathe · 7"` (Fach-Name + Anzahl offener Einträge)
   - Fächer mit count=0 werden mit `setEnabled(False)` gedimmt
   - Aktives Fach: `setChecked(True)`
   - Default-Auswahl: erstes Fach mit count > 0; wenn keins, das erste Fach in `SUBJECTS_ALL`
4. **Scrollbarer Inhalt** — pro offener Frage eine Card (siehe 8.2)
5. **Page-Action im Global-Header:** `[Üben ({n})]` Primary-Button, `n` = Anzahl Fragen im aktiven Fach (kappt bei 10). Disabled wenn 0.

### 8.2 Frage-Card

```
┌─────────────────────────────────────────────────────────────┐
│ [Topic-Pill]      Prompt-Excerpt (erste ~80 Zeichen) …     │
│                                                              │
│ 3× falsch · zuletzt 12.05.2026             ●○ noch 1× richtig│
└─────────────────────────────────────────────────────────────┘
```

- Topic-Pill links oben (existing `Pill`-Widget, Subject-Variante)
- Prompt-Excerpt: `questions.prompt` per QLabel mit WordWrap, max 80 Zeichen, danach „…"
- Bottom-Row links: `f"{wrong_count}× falsch · zuletzt {fmt_date(last_wrong_at)}"`
- Bottom-Row rechts: Streak-Marker
  - `consecutive_correct = 0` → `○○ noch 2× richtig`
  - `consecutive_correct = 1` → `●○ noch 1× richtig`
- Card ist **nicht** klickbar — keine Detail-Ansicht in v1 (YAGNI, Übungen sind der Hauptzweck)

### 8.3 Empty-States

- **Insgesamt 0 Fehler im Profil:** zentrierte Card mit „Noch keine offenen Fehler — sauber." (paper-600, Fraunces-Italic). Keine Subject-Pills, keine Action-Button.
- **Aktives Fach hat 0 Fehler, aber andere Fächer haben welche:** muted-Hinweis „In diesem Fach gerade alles im Lot." Subject-Pills bleiben sichtbar.

### 8.4 Einstiegspunkte

- **Logo-Menü** (in `widgets/global_header.py`):
  ```
  Start
  ---
  Test erstellen
  Termine
  Noten
  Fehlerheft                       ← NEU
  ---
  Profil wechseln
  ```
- **Gaps-Page-Footer** (in `pages/gaps.py`): unter dem Topic-Bar-Block ein text-Button `Fehler nochmal üben →`. Click: `window.show_error_book()`. Zurück-Navigation läuft übers Logo-Menü — konsistent mit allen Top-Level-Nav-Pages seit Phase 13.

### 8.5 MainWindow-Integration

- `show_error_book()` — analog `show_grades`; Top-Level-Nav-Page, kein `return_to`. Setzt page-actions im global header auf den Üben-Button.
- `start_error_book_practice(subject: str)` — analog `start_daily_five`:
  1. `error_book.builder.build_practice_test(conn, uid, subject)` → test_id (oder None)
  2. Wenn None: `QMessageBox.information("Keine offenen Fehler in diesem Fach.")` und return
  3. `attempts_repo.start(conn, test_id, ...)` → attempt_id
  4. `show_runner(attempt_id)`

## 9. Verhalten / Edge-Cases

| Szenario | Verhalten |
|----------|-----------|
| Frage 1× falsch in regulärem Test | im Heft, streak=0 |
| Frage falsch → richtig | im Heft, streak=1 |
| Frage falsch → richtig → richtig | aus Heft raus (evicted) |
| Frage falsch → richtig → falsch | im Heft, streak=0 (gebrochen) |
| Frage nur in `is_study=1` falsch | NICHT im Heft (Eligibility-Filter) |
| Pausierter Attempt für Fehler-Übung exists | `build_practice_test` returnt diesen test_id ohne Rebuild |
| Test gelöscht | CASCADE → answers weg → Frage fällt natürlich raus |
| Profil-Wechsel | Heft ist user_id-gefiltert, automatisch isoliert |

## 10. Tests

Test-Suite wächst von 371 auf ca. 400. Aufteilung:

- `tests/error_book/test_queries.py` (~10 Tests, Pure-Query-Layer)
- `tests/error_book/test_builder.py` (~8 Tests, Synth-Test inkl. ext_id-Flattening + Resume-Pfad)
- `tests/ui/test_error_book_page.py` (~5 Tests, Offscreen-Qt)
- `tests/ui/test_gaps_page.py` (+2 Tests, Footer-Button)
- `tests/ui/test_global_header.py` (+1 Test, Logo-Menü-Eintrag)
- `tests/ui/test_main_window_navigation.py` (+2 Tests, Routing + start_error_book_practice)
- `tests/error_book/test_e2e.py` (1 Test, Full-Loop import→falsch→Übung→richtig→richtig→evicted)

## 11. Offene Fragen / Folge-Phasen

- **Karteikarten-Modus** als alternative Übungs-Modalität — eigene Feature-Phase, lehnt sich am Datenmodell des Fehlerhefts an.
- **„Lernziel"-Pfad:** „Bis zur Mathe-KA möchte ich 0 offene Fehler haben" — könnte später am Cockpit-KA-Hero ankoppeln (Countdown + offene Fehler im Fach).
- **PDF-Export des Fehlerhefts** — könnte gut als Lernzettel funktionieren; wäre eine kleine Erweiterung in `pdf_export/`.

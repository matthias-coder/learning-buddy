# Phase 7 — Schul-Cockpit (Design Spec)

**Status:** Draft, awaiting user approval
**Datum:** 2026-05-12
**Vorgänger-Phase:** 6D (Kessler-Branding & Logos)
**Nachfolger-Kandidaten:** Phase 8 (Test-Erstellung & KA-Vorbereitung), Phase 9 (Foto-Import / OCR)

## 1. Zweck & Motivation

Die App weiß bisher nur, was in **Übungstests** passiert ist (synthetische `attempts`). Sie weiß nicht, was in der **echten Schule** ansteht oder real abgelaufen ist. Phase 7 schließt diese Lücke und macht die App zum **Schul-Cockpit**:

- *Was kommt* → Kalender mit kommenden Klassenarbeiten (KAs)
- *Was war* → Echte erfasste Schul-Noten (schriftlich/mündlich)
- *Was hat's gebracht* → Vergleich der App-Übungs-Leistung vor einer KA mit der echten KA-Note

**Zielnutzer:** Clemens (8. Klasse Realschule). Eingabe-UX muss schnell und teenager-tauglich sein.

**Bewusst nicht in Phase 7** *(future work)*:
- Foto-Import vom Schulplan-Aushang (OCR + LLM) — Phase 9
- AI-Prompt-Generator und "Übungstest für diese KA"-Button — Phase 8
- Streaks / Badges / Gamification — vom Nutzer ausdrücklich abgelehnt
- Pro-Fach-Gewichtungs-Settings für Zeugnis — vorerst global 50/50

## 2. Domänen-Modell

Zwei neue Tabellen, parallel zum bestehenden `tests`/`attempts`-Modell. Wichtig: **Vokabular trennen** — `attempt` = App-Übungsversuch (synthetisch), `assessment` = echte Schul-Note (real). Niemals mischen.

### 2.1 `scheduled_events`

Geplante Schul-Termine. Eine Zeile pro KA/Klausur/Test.

```sql
CREATE TABLE scheduled_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject     TEXT    NOT NULL,
    kind        TEXT    NOT NULL CHECK (kind IN ('klassenarbeit','klausur','test','sonstiges')),
    event_date  TEXT    NOT NULL,                 -- ISO YYYY-MM-DD
    topics      TEXT    NOT NULL DEFAULT '[]',    -- JSON Array of strings
    note        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_scheduled_user_date ON scheduled_events(user_id, event_date);
```

### 2.2 `assessments`

Echte erfasste Schul-Noten. Eine Zeile pro Note (schriftliche KA, mündliche Halbjahres-Note, etc.).

```sql
CREATE TABLE assessments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject             TEXT    NOT NULL,
    category            TEXT    NOT NULL CHECK (category IN ('schriftlich','muendlich','sonstige')),
    assessment_date     TEXT    NOT NULL,
    grade               REAL    NOT NULL,         -- 1.0 – 6.0 (.5er-Schritte erlaubt)
    points              REAL,                     -- optional
    max_points          REAL,                     -- optional
    note                TEXT,
    scheduled_event_id  INTEGER REFERENCES scheduled_events(id) ON DELETE SET NULL,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_assessments_user_subject ON assessments(user_id, subject);
CREATE INDEX idx_assessments_event ON assessments(scheduled_event_id);
```

**Begründung der Optionalität von `scheduled_event_id`:**
- Clemens muss Noten auch ohne vorher geplante KA eintragen können (z. B. unangekündigter Test, mündliche Halbjahres-Note).
- Bei Löschung der `scheduled_event` bleibt die Note erhalten (`ON DELETE SET NULL`).

### 2.3 Migration 006

Datei: `src/school_test_engine/storage/migrations/006_phase7_cockpit.sql`. Enthält beide CREATE-Statements + Indexes. Migrations-System fährt sie idempotent hoch.

## 3. Code-Struktur

### 3.1 Repositories (neu)

- `storage/events_repo.py`
  - `create(user_id, subject, kind, event_date, topics: list[str], note) -> int`
  - `update(event_id, **fields)`
  - `delete(event_id)`
  - `get(event_id) -> Event | None`
  - `list_upcoming(user_id, today: date, limit: int = 3) -> list[Event]` — `event_date >= today`, sortiert aufsteigend
  - `list_all(user_id) -> list[Event]` — sortiert nach event_date desc, dann created_at desc

- `storage/assessments_repo.py`
  - `create(user_id, subject, category, assessment_date, grade, points=None, max_points=None, note=None, scheduled_event_id=None) -> int`
  - `update(assessment_id, **fields)`
  - `delete(assessment_id)`
  - `get(assessment_id) -> Assessment | None`
  - `list_by_subject(user_id, subject) -> list[Assessment]` — sortiert nach assessment_date desc
  - `list_all(user_id) -> list[Assessment]`
  - `find_by_event(event_id) -> Assessment | None`

### 3.2 Cockpit-Service-Modul (neu)

Konsistent mit bestehendem Muster (`study/builder.py`, `grading/`, `importer/`): neues Domain-Package `cockpit/` mit `service.py`. Orchestriert beide Repositories + `attempts_repo` für komplexere Abfragen:

- `upcoming_events_for_menu(user_id) -> list[EventCardData]`
  Wird vom Hauptmenü gezogen. Liefert max. 3 nächste Events mit `days_until`, `topics`, optional `linked_assessment_id`.

- `comparison_for_assessment(assessment_id) -> ComparisonData | None`
  Liefert die Vergleichs-Daten zu einer Note: App-Übungs-Schnitt im Zeitraum **zwischen vorheriger KA im selben Fach und dieser KA**, oder — bei erster KA — alle Versuche bis zum KA-Datum.
  Rückgabe: `attempts_count`, `attempts_grade_avg`, `real_grade`, `delta_label` (`"besser" | "schlechter" | "gleich"`).
  Wenn keine App-Versuche im Zeitraum → return `None` (UI zeigt sanften Empty-State).

- `subject_grade_average(user_id, subject) -> SubjectAverage`
  Liefert `schriftlich_avg`, `muendlich_avg`, `zeugnis_estimate` (50/50 gewichtet).
  Wenn nur eine Kategorie Daten hat: `zeugnis_estimate = vorhandene_avg`.

- `aggregate_comparison(user_id) -> AggregateComparison | None`
  "Bei deinen letzten N Klassenarbeiten lag dein App-Schnitt im Schnitt X Noten über/unter der echten Note."

### 3.3 UI (neue Pages + Widgets)

#### Neue Widgets

- `widgets/exam_card.py` — Hero-KA-Karte für Hauptmenü-Strip. Fach-Eyebrow, Countdown-Pill ("in 3 Tagen"), Topic-Liste (max 3 Zeilen), `[Üben]`-Button (Phase 7 inaktiv mit Tooltip "in Phase 8") + `[…]`-Menu (Edit / Note eintragen / Löschen).
- `widgets/grade_pill.py` — runde, farbige Note-Anzeige (1=tea-700, 2=tea-500, 3=honey-500, 4=clay-500, 5/6=rose-500). Wiederverwendet auf Noten-Page und Vergleichs-View.
- `widgets/comparison_view.py` — Zeigt App-Übungs-Schnitt vs echte Note als kleine Hero-Card (zwei `grade_pill`s nebeneinander mit Pfeil und Delta-Label).

#### Neue Pages

- `pages/events.py` — Termine-Seite. Header (Eyebrow "Termine" + Fraunces "Was kommt"). Liste aller Events (anstehend mit warmem Hintergrund, vergangene gedimmt). + Button. Klick öffnet `EventDialog`.
- `pages/grades.py` — Noten-Seite. Header. Fach-Pills (Tabs) oben. Pro Fach: Hero-Card mit `schriftlich_avg`, `muendlich_avg`, `zeugnis_estimate`. Darunter Liste der `assessments` chronologisch mit `grade_pill` + Vergleichs-Block falls verfügbar. + Button öffnet `AssessmentDialog`.

#### Geänderte Pages

- `pages/menu.py` — adaptives Layout:
  - **Top-Bar erweitert:** zusätzlich zwei Icon-Buttons "Termine" 📅 und "Noten" 📊 links vom Profil-Chip. Buttons sind immer sichtbar (auch wenn keine KAs).
  - **Bei `upcoming_events_for_menu` non-empty:**
    KA-Hero-Strip (1–3 `ExamCard`s in horizontalem Layout, gleiche Breite) +
    Schnellzugriff-Reihe (kompaktes 4-Tile-Grid für Library/Lücken/Verlauf/Üben) darunter.
  - **Bei keinen Events:**
    Sanfter Empty-State "Keine Klassenarbeiten geplant. [+ Termin]" + klassisches 2×2-Card-Grid wie bisher.
  - Anschluss an `user_changed`-Signal: Cockpit-Daten werden neu geladen wenn Profil wechselt.

#### Dialoge

- `EventDialog` (Add/Edit)
  - Fach (QComboBox mit vordefinierten Fächern aus `_subjects.py` + "Anderes…"-Option)
  - Typ (QButtonGroup mit Radio-Buttons: KA / Klausur / Test / Sonstiges)
  - Datum (QDateEdit, default = heute + 7 Tage)
  - Topics (QPlainTextEdit, eine Zeile = ein Topic)
  - Notiz (QLineEdit, optional)
  - [Speichern] / [Abbrechen] / [Löschen (nur Edit)]

- `AssessmentDialog` (Add/Edit) — bewusst schlank für schnelle Eingabe durch Clemens:
  - Note: Big-Buttons-Reihe `1` `2` `3` `4` `5` `6`, ausgewählter Wert gehighlightet
  - +/− Buttons für .5er-Schritte (zeigt "2.5" wenn aktiv)
  - Fach: QComboBox, vorausgefüllt wenn aus KA-Karte geöffnet
  - Kategorie: Radio-Buttons (schriftlich / mündlich / sonstige), default "schriftlich"
  - Datum (default heute)
  - "Details" expandable (collapsed by default) mit: Punkte X/Y, Notiz
  - [Speichern] / [Abbrechen] / [Löschen (nur Edit)]

  Eingabezeit-Ziel: ≤ 5 Sekunden für den Standardfall (Note + Speichern).

## 4. Vergleichs-Logik (zentrales Feature)

### 4.1 Definition "App-Übungen vor dieser KA"

Für eine `assessment` A mit `scheduled_event_id = E`, `subject = S`, `assessment_date = D`:

1. Finde die **vorherige KA** im selben Fach: `prev_event_date = MAX(scheduled_events.event_date) WHERE subject = S AND event_date < E.event_date AND user_id = U`.
2. **Zeitraum:** `(prev_event_date, E.event_date]` — falls keine vorherige KA: `(−∞, E.event_date]`.
3. Hole alle `attempts` in diesem Zeitraum mit `tests.subject = S` (Join über `attempts.test_id`).
4. Berechne Durchschnittsnote über diese attempts (`attempts.grade_value`).
5. Vergleich: `delta = round(real_grade − app_avg, 1)`. Label:
   - `delta < −0.2` → "Du warst in der KA besser als in App-Übungen ↑"
   - `delta > 0.2` → "Du warst in der KA schlechter als in App-Übungen ↓"
   - sonst → "App-Übungen und echte KA waren sehr ähnlich ≈"

Wenn `assessment.scheduled_event_id IS NULL`: kein Vergleich möglich → UI zeigt Vergleichs-Block nicht.

### 4.2 Aggregat-Vergleich

Über alle `assessments` mit verlinkter `scheduled_event_id` und vorhandenen App-Übungen im jeweiligen Zeitraum:

- N = Anzahl Vergleiche
- avg_delta = arithmetisches Mittel der `delta`-Werte
- Wenn N ≥ 3: Zeile auf Noten-Seite unten "Bei deinen letzten N Klassenarbeiten lag dein App-Übungs-Schnitt im Schnitt {avg_delta:+.1f} Noten {besser/schlechter} als die echte Note."

## 5. Zeugnis-Schätzung

**Fix 50/50** schriftlich/mündlich. Keine Settings, kein Slider. Pro Fach auf der Noten-Seite:

```
zeugnis_estimate =
    0.5 * schriftlich_avg + 0.5 * muendlich_avg   wenn beide vorhanden
    schriftlich_avg                                wenn nur schriftlich
    muendlich_avg                                  wenn nur mündlich
    None                                           wenn nichts erfasst
```

Display: groß als Hero pro Fach (Fraunces, `grade_pill`). Wenn Schätzung nicht ganz: ".5" wird zur nächsten halben Note gerundet (deutsche Schulkonvention: 2,4 → 2; 2,6 → 3 — wir zeigen einfach 1 Nachkommastelle und keine Rundung, weil Schätzung).

## 6. Edge Cases

| Fall | Verhalten |
|------|-----------|
| Note ohne geplante KA eintragen | `scheduled_event_id = NULL`, Vergleichs-Block nicht gezeigt. |
| KA-Datum verschoben (nach Erfassung) | Edit-Dialog. Wenn assessment verknüpft: Note bleibt verknüpft. Vergleichs-Logik nutzt neues Datum. |
| Note nachträglich korrigiert | Edit-Dialog. Vergleich wird neu berechnet. |
| Mehrere KAs am gleichen Tag | Separate `scheduled_events`, beide im Strip. Sortierung sekundär nach `created_at`. |
| User gelöscht | `ON DELETE CASCADE` löscht events; assessments folgen über cascade in zweiter Tabelle. |
| KA-Datum erreicht ohne Note | KA-Karte bleibt im Strip (mit "vergangen — Note eintragen?"-Empty-State) bis Note erfasst ist. |
| Keine App-Übungen vor KA | Vergleichs-Block nicht gezeigt. Note wird trotzdem angezeigt. |
| Erste KA überhaupt | Vergleichszeitraum = alle Versuche bis zum KA-Datum (kein "vorheriger" event vorhanden). |
| KA-Datum in der Vergangenheit, kein Termin erfasst | Clemens kann Note direkt anlegen (ohne `scheduled_event`). Optional später: aus Note-Dialog heraus rückwirkend einen `scheduled_event` anlegen. *Vorerst:* nicht-verlinkte Notes sind OK, keine Vergleichs-Daten. |

## 7. Tests

### Unit
- `events_repo`: CRUD, Cascade-Verhalten bei User-Löschung
- `assessments_repo`: CRUD, `find_by_event`, `ON DELETE SET NULL` bei Event-Löschung
- `cockpit.comparison_for_assessment`: 
  - Mit & ohne vorheriger KA
  - Mit & ohne App-Übungen im Zeitraum
  - Korrekte Filterung nach Fach
  - Delta-Label-Grenzwerte
- `cockpit.subject_grade_average`: Mit nur einer Kategorie, mit beiden, ohne Daten
- `cockpit.aggregate_comparison`: N < 3 → None; korrekte Mittelung
- Migration 006 auf bestehender DB (Idempotenz)

### Integration / Smoke
- Manuell: KA anlegen → vor KA-Datum 2 Übungsversuche → KA-Datum erreichen → Note 2.0 eintragen → Vergleichs-Card erscheint mit korrekten Werten
- Profil-Wechsel → Cockpit-Daten ändern sich auf Hauptmenü
- Cascade: Profil löschen → events & assessments verschwinden

## 8. Risiken & offene Fragen

- **Vergleichs-Logik bei Test-Subject-Mismatch:** Wenn Clemens "Mathe" als Fach in der KA eingibt, aber ein Test im Library hat `subject="Mathematik"`, matcht nichts. **Mitigation:** Subject-Liste aus `_subjects.py` zentralisieren, beide Eingaben (KA und Test-JSON) gegen die gleiche Liste validieren.
- **Mündliche Noten-Pflege:** Clemens muss mündliche Noten selbst pflegen (Schule liefert sie meist nur 1–2× pro Halbjahr). Vielleicht später aus Eltern-Sicht. **Vorerst:** ganz normal über `AssessmentDialog` mit category="muendlich".
- **Empty States:** Erste Wochen wird Clemens fast keine Daten haben — das Schul-Cockpit muss auch leer hübsch aussehen. Empty-State-Copy ist in jeder neuen Page einzubauen ("Noch keine Klassenarbeiten geplant", "Noch keine Noten — trag deine erste ein").

## 9. Akzeptanzkriterien

Phase 7 ist fertig wenn:

1. Migration 006 läuft sauber auf bestehender DB.
2. Clemens kann eine KA anlegen, editieren, löschen.
3. Clemens kann eine Note anlegen, editieren, löschen (mit & ohne verlinkter KA).
4. Hauptmenü zeigt KA-Strip wenn anstehende Events vorhanden; sonst klassisches 2×2.
5. Top-Bar hat Icon-Zugang zu Termine + Noten unabhängig vom Hauptmenü-Zustand.
6. Vergleichs-Card erscheint auf Note-Detail wenn App-Übungen im Zeitraum vorhanden.
7. Aggregat-Zeile erscheint auf Noten-Seite wenn N ≥ 3 vergleichbare KAs.
8. Profil-Wechsel führt zu sauberer Datentrennung (CASCADE getestet).
9. Alle neuen Unit-Tests grün; existierende Tests weiterhin grün.
10. Manueller Smoke-Test-Pfad aus Sektion 7 funktioniert end-to-end.

## 10. Nicht-Ziele für Phase 7

- AI-Prompt-Generator / "Übungstest für diese KA bauen" (Phase 8)
- Foto-Import vom Schulplan (Phase 9)
- Daily-5-Widget / Spaced Repetition (separate Phase)
- Pro-Fach-Gewichtungs-Settings für Zeugnis (50/50 fest)
- Streaks, Badges, Gamification
- Multi-Device-Sync / Cloud-Backup
- PDF-Export Wochen-Report (kommt erst wenn das Datenmodell sich bewährt hat)

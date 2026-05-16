# Phase 17 — Schulkalender + Ferien-Banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Schulkalender als eigene Page mit filterbaren Event-Typen (KAs / Ferien / Frei / Schul-Events) und persistierten Filtern, plus Ferien-Countdown-Banner im Hauptmenü. iCal-Sync wird erweitert um Ferien/Frei/Events neben den bestehenden Klausuren.

**Architecture:** Neue Tabelle `calendar_events` (Migration 012) + Filter-Spalten auf `users`. Neues Domain-Paket `school_calendar/` (CalendarEntry/CalendarFilters Dataclasses + Service). `ical_sync/service.py` kriegt zweiten Schreibpfad; `classify()` ersetzt `is_klausur_event()` (Wrapper bleibt). Neue UI-Page `SchoolCalendarPage`, neues Widget `FerienBanner` in MenuPage, Logo-Menü-Eintrag „Schulkalender". Pattern-Reuse: `error_book/queries.py` (Pure-SQL-Layer), `pages/grades.py` (subjectTab-Style), `widgets/Pill` + `widgets/Eyebrow`.

**Tech Stack:** Python 3.12, PySide6, SQLite, pytest. Reuse: `icalendar`-Lib (Phase 15), existierendes Migration-System (`run_migrations`).

**Spec:** `docs/superpowers/specs/2026-05-16-phase-17-schulkalender-design.md`

---

## Task 1: Migration 012 — Schema + Filter-Spalten

**Files:**
- Create: `src/school_test_engine/storage/migrations/012_phase17_calendar.sql`
- Create: `tests/test_migration_012.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_migration_012.py
"""Phase 17: schema migration adds calendar_events + user filter columns."""
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import run_migrations


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def _columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _index_names(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA index_list({table})")}


def test_calendar_events_table_exists_with_columns(conn):
    cols = _columns(conn, "calendar_events")
    assert {"id", "user_id", "kind", "title", "start_date", "end_date",
            "external_uid", "external_source", "created_at"}.issubset(cols)


def test_calendar_events_kind_check_constraint(conn):
    from school_test_engine.storage import users_repo
    uid = users_repo.create_user(conn, name="T")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO calendar_events (user_id, kind, title, start_date, end_date) "
            "VALUES (?, 'invalid_kind', 'x', '2026-01-01', '2026-01-01')",
            (uid,),
        )
        conn.commit()


def test_calendar_events_unique_external_uid_per_user(conn):
    from school_test_engine.storage import users_repo
    uid = users_repo.create_user(conn, name="T")
    conn.execute(
        "INSERT INTO calendar_events (user_id, kind, title, start_date, end_date, external_uid) "
        "VALUES (?, 'ferien', 'F1', '2026-07-07', '2026-08-16', 'uid-A')",
        (uid,),
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO calendar_events (user_id, kind, title, start_date, end_date, external_uid) "
            "VALUES (?, 'ferien', 'F2', '2026-10-19', '2026-10-31', 'uid-A')",
            (uid,),
        )
        conn.commit()


def test_users_has_calendar_filter_columns(conn):
    cols = _columns(conn, "users")
    assert {"calendar_show_klausuren", "calendar_show_ferien",
            "calendar_show_frei", "calendar_show_events",
            "calendar_timeframe"}.issubset(cols)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_012.py -v`
Expected: FAIL (table or columns missing).

- [ ] **Step 3: Create migration SQL**

```sql
-- src/school_test_engine/storage/migrations/012_phase17_calendar.sql
-- Phase 17: Schulkalender — calendar_events + per-user filter state

CREATE TABLE IF NOT EXISTS calendar_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            TEXT    NOT NULL
                    CHECK (kind IN ('ferien', 'frei', 'event')),
    title           TEXT    NOT NULL,
    start_date      TEXT    NOT NULL,
    end_date        TEXT    NOT NULL,
    external_uid    TEXT,
    external_source TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_user_date
    ON calendar_events(user_id, start_date);

CREATE UNIQUE INDEX IF NOT EXISTS idx_calendar_events_external_uid
    ON calendar_events(user_id, external_uid)
    WHERE external_uid IS NOT NULL;

ALTER TABLE users ADD COLUMN calendar_show_klausuren INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_show_ferien    INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_show_frei      INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_show_events    INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_timeframe      TEXT    NOT NULL DEFAULT 'future'
                                                       CHECK (calendar_timeframe IN ('future', 'all', 'past'));
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_migration_012.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/migrations/012_phase17_calendar.sql \
        tests/test_migration_012.py
git commit -m "feat(migration): 012 — calendar_events table + per-user filter columns"
```

---

## Task 2: users_repo — 5 neue Kwargs für Filter-Persistenz

**Files:**
- Modify: `src/school_test_engine/storage/users_repo.py`
- Create: `tests/test_users_repo_calendar.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_users_repo_calendar.py
"""users_repo.update_user persists calendar filter columns (Phase 17)."""
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def test_defaults_are_one_and_future(conn):
    uid = users_repo.create_user(conn, name="T")
    row = users_repo.get_user(conn, uid)
    assert row["calendar_show_klausuren"] == 1
    assert row["calendar_show_ferien"] == 1
    assert row["calendar_show_frei"] == 1
    assert row["calendar_show_events"] == 1
    assert row["calendar_timeframe"] == "future"


def test_update_calendar_filters_roundtrip(conn):
    uid = users_repo.create_user(conn, name="T")
    users_repo.update_user(
        conn, uid,
        calendar_show_klausuren=0,
        calendar_show_ferien=1,
        calendar_show_frei=0,
        calendar_show_events=1,
        calendar_timeframe="past",
    )
    row = users_repo.get_user(conn, uid)
    assert row["calendar_show_klausuren"] == 0
    assert row["calendar_show_ferien"] == 1
    assert row["calendar_show_frei"] == 0
    assert row["calendar_show_events"] == 1
    assert row["calendar_timeframe"] == "past"


def test_none_does_not_change_existing_value(conn):
    uid = users_repo.create_user(conn, name="T")
    users_repo.update_user(conn, uid, calendar_show_klausuren=0, calendar_timeframe="past")
    users_repo.update_user(conn, uid, calendar_show_klausuren=None, calendar_timeframe=None)
    row = users_repo.get_user(conn, uid)
    assert row["calendar_show_klausuren"] == 0
    assert row["calendar_timeframe"] == "past"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_users_repo_calendar.py -v`
Expected: FAIL with `TypeError: update_user() got unexpected keyword argument 'calendar_show_klausuren'`.

- [ ] **Step 3: Add five kwargs to update_user**

In `src/school_test_engine/storage/users_repo.py` extend the signature of `update_user` and the field-collection block. Add the new kwargs after the existing `ical_last_sync_summary` kwarg:

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
    show_keyboard_hints: int | None = None,
    ical_feed_url=_SENTINEL,
    ical_last_sync_at=_SENTINEL,
    ical_last_sync_summary=_SENTINEL,
    calendar_show_klausuren: int | None = None,
    calendar_show_ferien: int | None = None,
    calendar_show_frei: int | None = None,
    calendar_show_events: int | None = None,
    calendar_timeframe: str | None = None,
) -> None:
    fields: list[str] = []
    values: list = []
    # ... existing branches unchanged ...
    if calendar_show_klausuren is not None:
        fields.append("calendar_show_klausuren = ?"); values.append(int(calendar_show_klausuren))
    if calendar_show_ferien is not None:
        fields.append("calendar_show_ferien = ?"); values.append(int(calendar_show_ferien))
    if calendar_show_frei is not None:
        fields.append("calendar_show_frei = ?"); values.append(int(calendar_show_frei))
    if calendar_show_events is not None:
        fields.append("calendar_show_events = ?"); values.append(int(calendar_show_events))
    if calendar_timeframe is not None:
        fields.append("calendar_timeframe = ?"); values.append(calendar_timeframe)
    if not fields:
        return
    values.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_users_repo_calendar.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/users_repo.py tests/test_users_repo_calendar.py
git commit -m "feat(users_repo): 5 new kwargs for calendar filter persistence"
```

---

## Task 3: Parser — dtend_date + is_multi_day

**Files:**
- Modify: `src/school_test_engine/ical_sync/parser.py`
- Modify: `tests/ical_sync/test_parser.py`

- [ ] **Step 1: Append three failing tests to test_parser.py**

```python
# tests/ical_sync/test_parser.py — append at end of file

def test_dtend_date_for_date_only_event_is_inclusive():
    """DATE-only DTEND in iCal is exclusive — parser normalizes to inclusive."""
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:t1\nSUMMARY:Sommerferien\n"
        b"DTSTART;VALUE=DATE:20250707\nDTEND;VALUE=DATE:20250816\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    from school_test_engine.ical_sync.parser import parse_events
    events = parse_events(ics)
    assert len(events) == 1
    assert events[0].dtstart_date == "2025-07-07"
    assert events[0].dtend_date == "2025-08-15"
    assert events[0].is_multi_day is True


def test_dtend_date_for_datetime_event_is_same_day():
    """DATETIME DTEND on the same day means a same-day event."""
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:t2\nSUMMARY:KA\n"
        b"DTSTART;TZID=Europe/Berlin:20260310T093500\n"
        b"DTEND;TZID=Europe/Berlin:20260310T110500\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    from school_test_engine.ical_sync.parser import parse_events
    events = parse_events(ics)
    assert events[0].dtstart_date == "2026-03-10"
    assert events[0].dtend_date == "2026-03-10"
    assert events[0].is_multi_day is False


def test_missing_dtend_means_same_day():
    """A VEVENT without DTEND falls back to dtstart_date."""
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:t3\nSUMMARY:X\n"
        b"DTSTART;VALUE=DATE:20260512\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    from school_test_engine.ical_sync.parser import parse_events
    events = parse_events(ics)
    assert events[0].dtstart_date == "2026-05-12"
    assert events[0].dtend_date == "2026-05-12"
    assert events[0].is_multi_day is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ical_sync/test_parser.py -v`
Expected: 3 new tests FAIL with `AttributeError: 'RawVEvent' object has no attribute 'dtend_date'`.

- [ ] **Step 3: Extend RawVEvent + parse_events**

Replace `src/school_test_engine/ical_sync/parser.py`:

```python
"""Wrap the icalendar library and emit stdlib-only RawVEvent dataclasses.

This isolates the rest of the app from the icalendar API — if the library
ever needs to be swapped, only this file changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import icalendar


@dataclass(frozen=True)
class RawVEvent:
    uid: str
    summary: str
    description: str
    dtstart_date: str
    dtend_date: str
    categories: tuple[str, ...]

    @property
    def is_multi_day(self) -> bool:
        return self.dtend_date > self.dtstart_date


def parse_events(ics_bytes: bytes) -> list[RawVEvent]:
    """Parse ics bytes. Raises ValueError when input is not a valid iCal."""
    try:
        cal = icalendar.Calendar.from_ical(ics_bytes)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Invalid iCal data: {e}") from e

    out: list[RawVEvent] = []
    for comp in cal.walk("VEVENT"):
        dtstart = comp.get("DTSTART")
        if dtstart is None:
            continue
        dt = dtstart.dt
        start_iso = dt.date().isoformat() if isinstance(dt, datetime) else dt.isoformat()

        dtend = comp.get("DTEND")
        if dtend is None:
            end_iso = start_iso
        else:
            de = dtend.dt
            if isinstance(de, datetime):
                end_iso = de.date().isoformat()
            else:
                # DATE-only DTEND is exclusive → step back one day
                end_iso = (de - timedelta(days=1)).isoformat()

        out.append(RawVEvent(
            uid=str(comp.get("UID", "")),
            summary=str(comp.get("SUMMARY", "")),
            description=str(comp.get("DESCRIPTION", "")),
            dtstart_date=start_iso,
            dtend_date=end_iso,
            categories=_categories(comp),
        ))
    return out


def _categories(comp) -> tuple[str, ...]:
    cat = comp.get("CATEGORIES")
    if cat is None:
        return ()
    if isinstance(cat, list):
        return tuple(str(c) for vcats in cat for c in vcats.cats)
    return tuple(str(c) for c in cat.cats)
```

- [ ] **Step 4: Run all parser tests**

Run: `pytest tests/ical_sync/test_parser.py -v`
Expected: all pass (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ical_sync/parser.py tests/ical_sync/test_parser.py
git commit -m "feat(ical_sync/parser): expose dtend_date + is_multi_day on RawVEvent"
```

---

## Task 4: Classifier — classify() + Backward-Compat-Wrapper

**Files:**
- Modify: `src/school_test_engine/ical_sync/classifier.py`
- Create: `tests/ical_sync/test_classifier_classify.py` (new file — keep existing test_classifier.py untouched for the is_klausur_event wrapper)

- [ ] **Step 1: Write the failing tests**

```python
# tests/ical_sync/test_classifier_classify.py
"""Classify VEVENTs into klausur / ferien / frei / event / None (skip)."""
from __future__ import annotations

import pytest

from school_test_engine.ical_sync.classifier import classify, is_klausur_event
from school_test_engine.ical_sync.parser import RawVEvent


def _event(uid="x", summary="", desc="", start="2026-05-15",
            end=None, categories=()):
    return RawVEvent(
        uid=uid, summary=summary, description=desc,
        dtstart_date=start, dtend_date=end if end else start,
        categories=tuple(categories),
    )


def test_klausur_uid_marker_returns_klausur():
    e = _event(uid="20010101T000001-klausur-9084-14627-2026-03-10@x.org",
               categories=("Arbeiten",))
    assert classify(e) == "klausur"


def test_multi_day_ferien_category_returns_ferien():
    e = _event(start="2026-07-07", end="2026-08-15", categories=("Ferien",))
    assert classify(e) == "ferien"


def test_single_day_ferien_category_returns_frei():
    e = _event(start="2026-05-12", end="2026-05-12", categories=("Ferien",))
    assert classify(e) == "frei"


def test_feiertag_category_multi_day_returns_ferien():
    e = _event(start="2026-12-24", end="2026-12-26", categories=("Feiertag",))
    assert classify(e) == "ferien"


def test_feiertag_category_single_day_returns_frei():
    e = _event(start="2026-10-03", categories=("Feiertag",))
    assert classify(e) == "frei"


def test_arbeiten_without_klausur_uid_returns_event():
    """Wettbewerb etc. — CATEGORIES:Arbeiten ohne -klausur- im UID."""
    e = _event(uid="20250920T153052-5927@x.org",
               summary="Mathematikwettbewerb",
               categories=("Arbeiten",))
    assert classify(e) == "event"


def test_unknown_categories_returns_none():
    e = _event(categories=("Unterricht",))
    assert classify(e) is None


def test_no_categories_returns_none():
    e = _event(categories=())
    assert classify(e) is None


def test_is_klausur_event_backward_compat():
    """is_klausur_event must remain functional (Phase 15 callers + tests)."""
    e_kl = _event(uid="x-klausur-y", categories=("Arbeiten",))
    e_no = _event(uid="x-y", categories=("Ferien",), start="2026-07-07", end="2026-08-15")
    assert is_klausur_event(e_kl) is True
    assert is_klausur_event(e_no) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ical_sync/test_classifier_classify.py -v`
Expected: FAIL — `classify` does not exist yet.

- [ ] **Step 3: Rewrite classifier.py**

```python
# src/school_test_engine/ical_sync/classifier.py
"""Classify VEVENTs from the Schulportal Hessen feed into kinds.

Returns one of:
    'klausur' — KAs / Lernkontrollen / Klausuren (UID contains '-klausur-')
    'ferien'  — multi-day school holidays (CATEGORIES Ferien/Feiertag + range)
    'frei'    — single-day off (Pädagogischer Tag etc.)
    'event'   — other school events (Wettbewerbe, AGs, Theater, ...)
    None      — skip; unknown / not relevant
"""
from __future__ import annotations

from typing import Literal

from .parser import RawVEvent

EventKind = Literal["klausur", "ferien", "frei", "event"]

_KLAUSUR_MARKER = "-klausur-"


def classify(event: RawVEvent) -> EventKind | None:
    if _KLAUSUR_MARKER in event.uid:
        return "klausur"

    cats_lower = {c.lower() for c in event.categories}

    if "ferien" in cats_lower or "feiertag" in cats_lower:
        return "ferien" if event.is_multi_day else "frei"

    if "arbeiten" in cats_lower:
        # CATEGORIES:Arbeiten WITHOUT -klausur- UID = Wettbewerb, Olympiade etc.
        return "event"

    return None


def is_klausur_event(event: RawVEvent) -> bool:
    """Backward-compat wrapper for Phase 15 callers."""
    return classify(event) == "klausur"
```

- [ ] **Step 4: Run all classifier tests (new + old)**

Run: `pytest tests/ical_sync/test_classifier.py tests/ical_sync/test_classifier_classify.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ical_sync/classifier.py \
        tests/ical_sync/test_classifier_classify.py
git commit -m "feat(ical_sync/classifier): classify() 4-way + skip; is_klausur_event wrapper"
```

---

## Task 5: calendar_events_repo — CRUD + list

**Files:**
- Create: `src/school_test_engine/storage/calendar_events_repo.py`
- Create: `tests/storage/test_calendar_events_repo.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_calendar_events_repo.py
"""calendar_events_repo CRUD + list_for_user with kind+timeframe filtering."""
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import (
    calendar_events_repo, run_migrations, users_repo,
)


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, name="Clemens")


def test_create_and_read_back(conn, uid):
    eid = calendar_events_repo.create(
        conn, user_id=uid, kind="ferien", title="Sommerferien",
        start_date="2026-07-07", end_date="2026-08-15",
        external_uid="uid-A", external_source="schulportal_hessen",
    )
    assert eid > 0
    row = conn.execute("SELECT * FROM calendar_events WHERE id = ?", (eid,)).fetchone()
    assert row["title"] == "Sommerferien"
    assert row["kind"] == "ferien"
    assert row["external_source"] == "schulportal_hessen"


def test_list_for_user_future_timeframe(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Past",
                                start_date="2024-07-01", end_date="2024-08-01")
    calendar_events_repo.create(conn, user_id=uid, kind="event", title="Future",
                                start_date="2030-01-01", end_date="2030-01-01")
    rows = calendar_events_repo.list_for_user(
        conn, uid, today="2026-05-15", timeframe="future",
        kinds={"ferien", "event"},
    )
    titles = [r["title"] for r in rows]
    assert titles == ["Future"]


def test_list_for_user_past_timeframe(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Past",
                                start_date="2024-07-01", end_date="2024-08-01")
    calendar_events_repo.create(conn, user_id=uid, kind="event", title="Future",
                                start_date="2030-01-01", end_date="2030-01-01")
    rows = calendar_events_repo.list_for_user(
        conn, uid, today="2026-05-15", timeframe="past",
        kinds={"ferien", "event"},
    )
    titles = [r["title"] for r in rows]
    assert titles == ["Past"]


def test_list_for_user_all_timeframe(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Past",
                                start_date="2024-07-01", end_date="2024-08-01")
    calendar_events_repo.create(conn, user_id=uid, kind="event", title="Future",
                                start_date="2030-01-01", end_date="2030-01-01")
    rows = calendar_events_repo.list_for_user(
        conn, uid, today="2026-05-15", timeframe="all",
        kinds={"ferien", "event"},
    )
    assert len(rows) == 2


def test_list_for_user_filters_by_kinds(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="F",
                                start_date="2030-01-01", end_date="2030-01-10")
    calendar_events_repo.create(conn, user_id=uid, kind="event", title="E",
                                start_date="2030-01-15", end_date="2030-01-15")
    rows = calendar_events_repo.list_for_user(
        conn, uid, today="2026-05-15", timeframe="all", kinds={"ferien"},
    )
    titles = [r["title"] for r in rows]
    assert titles == ["F"]


def test_update_by_external_uid_changes_title_and_dates(conn, uid):
    calendar_events_repo.create(
        conn, user_id=uid, kind="ferien", title="Old",
        start_date="2026-07-07", end_date="2026-08-15",
        external_uid="uid-A",
    )
    changed = calendar_events_repo.update_by_external_uid(
        conn, user_id=uid, external_uid="uid-A",
        kind="ferien", title="New", start_date="2026-07-08", end_date="2026-08-16",
    )
    assert changed is True
    row = conn.execute("SELECT title, start_date, end_date FROM calendar_events").fetchone()
    assert row["title"] == "New"
    assert row["start_date"] == "2026-07-08"


def test_delete_by_external_uid_removes_row(conn, uid):
    calendar_events_repo.create(
        conn, user_id=uid, kind="event", title="X",
        start_date="2026-01-01", end_date="2026-01-01",
        external_uid="uid-X",
    )
    assert calendar_events_repo.delete_by_external_uid(conn, uid, "uid-X") is True
    rows = conn.execute("SELECT id FROM calendar_events").fetchall()
    assert rows == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/storage/test_calendar_events_repo.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement calendar_events_repo.py**

```python
# src/school_test_engine/storage/calendar_events_repo.py
"""CRUD + filtered listing for calendar_events (Phase 17)."""
from __future__ import annotations

import sqlite3


def create(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    kind: str,
    title: str,
    start_date: str,
    end_date: str,
    external_uid: str | None = None,
    external_source: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO calendar_events
            (user_id, kind, title, start_date, end_date, external_uid, external_source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, kind, title, start_date, end_date, external_uid, external_source),
    )
    conn.commit()
    eid = cur.lastrowid
    assert eid is not None
    return eid


def list_for_user(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    today: str | None = None,
    timeframe: str = "future",
    kinds: set[str] | None = None,
) -> list[sqlite3.Row]:
    where = ["user_id = ?"]
    params: list = [user_id]

    if kinds:
        placeholders = ",".join("?" for _ in kinds)
        where.append(f"kind IN ({placeholders})")
        params.extend(kinds)

    if timeframe == "future" and today:
        where.append("end_date >= ?"); params.append(today)
    elif timeframe == "past" and today:
        where.append("end_date < ?"); params.append(today)
    # "all" → no date filter

    sql = (
        f"SELECT * FROM calendar_events WHERE {' AND '.join(where)} "
        f"ORDER BY start_date ASC, id ASC"
    )
    cur = conn.execute(sql, params)
    return cur.fetchall()


def list_external_uids(conn: sqlite3.Connection, user_id: int) -> set[str]:
    cur = conn.execute(
        "SELECT external_uid FROM calendar_events "
        "WHERE user_id = ? AND external_uid IS NOT NULL",
        (user_id,),
    )
    return {r["external_uid"] for r in cur.fetchall()}


def list_with_external_uid(
    conn: sqlite3.Connection, user_id: int
) -> list[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM calendar_events "
        "WHERE user_id = ? AND external_uid IS NOT NULL",
        (user_id,),
    )
    return cur.fetchall()


def update_by_external_uid(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    external_uid: str,
    kind: str,
    title: str,
    start_date: str,
    end_date: str,
) -> bool:
    cur = conn.execute(
        """
        UPDATE calendar_events
        SET kind = ?, title = ?, start_date = ?, end_date = ?
        WHERE user_id = ? AND external_uid = ?
        """,
        (kind, title, start_date, end_date, user_id, external_uid),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_by_external_uid(
    conn: sqlite3.Connection, user_id: int, external_uid: str
) -> bool:
    cur = conn.execute(
        "DELETE FROM calendar_events WHERE user_id = ? AND external_uid = ?",
        (user_id, external_uid),
    )
    conn.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/storage/test_calendar_events_repo.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/calendar_events_repo.py \
        tests/storage/test_calendar_events_repo.py
git commit -m "feat(storage): calendar_events_repo — CRUD + list_for_user with filters"
```

---

## Task 6: calendar_events_repo — find_active_vacation + find_next_vacation

**Files:**
- Modify: `src/school_test_engine/storage/calendar_events_repo.py`
- Modify: `tests/storage/test_calendar_events_repo.py`

- [ ] **Step 1: Append failing tests**

```python
# tests/storage/test_calendar_events_repo.py — append at end

def test_find_active_vacation_returns_current_ferien(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommer",
                                start_date="2026-07-07", end_date="2026-08-15")
    row = calendar_events_repo.find_active_vacation(conn, uid, "2026-07-20")
    assert row is not None
    assert row["title"] == "Sommer"


def test_find_active_vacation_ignores_single_day_frei(conn, uid):
    """Bewegliche Feiertage (kind='frei') triggern den Banner nicht."""
    calendar_events_repo.create(conn, user_id=uid, kind="frei", title="Päd. Tag",
                                start_date="2026-05-15", end_date="2026-05-15")
    row = calendar_events_repo.find_active_vacation(conn, uid, "2026-05-15")
    assert row is None


def test_find_active_vacation_returns_none_outside_range(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommer",
                                start_date="2026-07-07", end_date="2026-08-15")
    row = calendar_events_repo.find_active_vacation(conn, uid, "2026-09-01")
    assert row is None


def test_find_next_vacation_returns_earliest_future(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Herbst",
                                start_date="2026-10-19", end_date="2026-10-31")
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Weihnachten",
                                start_date="2026-12-22", end_date="2027-01-06")
    row = calendar_events_repo.find_next_vacation(conn, uid, "2026-05-15")
    assert row is not None
    assert row["title"] == "Herbst"


def test_find_next_vacation_ignores_frei_kind(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="frei", title="Brückentag",
                                start_date="2026-05-29", end_date="2026-05-29")
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommer",
                                start_date="2026-07-07", end_date="2026-08-15")
    row = calendar_events_repo.find_next_vacation(conn, uid, "2026-05-15")
    assert row["title"] == "Sommer"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/test_calendar_events_repo.py -v -k "vacation"`
Expected: FAIL with `AttributeError: module ... has no attribute 'find_active_vacation'`.

- [ ] **Step 3: Append the two functions**

In `src/school_test_engine/storage/calendar_events_repo.py`:

```python
def find_active_vacation(
    conn: sqlite3.Connection, user_id: int, today: str
) -> sqlite3.Row | None:
    """The current vacation (kind='ferien') today is inside — or None."""
    cur = conn.execute(
        """
        SELECT * FROM calendar_events
        WHERE user_id = ? AND kind = 'ferien'
          AND start_date <= ? AND end_date >= ?
        ORDER BY start_date DESC
        LIMIT 1
        """,
        (user_id, today, today),
    )
    return cur.fetchone()


def find_next_vacation(
    conn: sqlite3.Connection, user_id: int, today: str
) -> sqlite3.Row | None:
    """The earliest vacation (kind='ferien') strictly after today — or None."""
    cur = conn.execute(
        """
        SELECT * FROM calendar_events
        WHERE user_id = ? AND kind = 'ferien'
          AND start_date > ?
        ORDER BY start_date ASC
        LIMIT 1
        """,
        (user_id, today),
    )
    return cur.fetchone()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/storage/test_calendar_events_repo.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/calendar_events_repo.py \
        tests/storage/test_calendar_events_repo.py
git commit -m "feat(storage): find_active_vacation + find_next_vacation (kind='ferien' only)"
```

---

## Task 7: ical_sync.service — dual write path

**Files:**
- Modify: `src/school_test_engine/ical_sync/service.py`
- Modify: `tests/ical_sync/test_service.py`

- [ ] **Step 1: Append failing tests**

```python
# tests/ical_sync/test_service.py — append at end. Mind the existing helpers/fixtures.

def test_sync_persists_multi_day_ferien_to_calendar_events(monkeypatch, conn, uid):
    from school_test_engine.ical_sync import service
    from school_test_engine.storage import calendar_events_repo, users_repo

    users_repo.update_user(conn, uid, ical_feed_url="https://example.com/feed")

    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:abc\nSUMMARY:Sommerferien\n"
        b"DTSTART;VALUE=DATE:20260707\nDTEND;VALUE=DATE:20260817\n"
        b"CATEGORIES:Ferien\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url: ics)

    result = service.sync_feed(conn, uid)
    assert result.error is None
    assert result.cal_added == 1
    rows = calendar_events_repo.list_for_user(conn, uid, today="2026-01-01",
                                              timeframe="all", kinds={"ferien"})
    assert len(rows) == 1
    assert rows[0]["title"] == "Sommerferien"
    assert rows[0]["start_date"] == "2026-07-07"
    assert rows[0]["end_date"] == "2026-08-16"


def test_sync_persists_single_day_frei(monkeypatch, conn, uid):
    from school_test_engine.ical_sync import service
    from school_test_engine.storage import calendar_events_repo, users_repo

    users_repo.update_user(conn, uid, ical_feed_url="https://example.com/feed")
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:p1\nSUMMARY:Paedagogischer Tag\n"
        b"DTSTART;VALUE=DATE:20260512\nDTEND;VALUE=DATE:20260513\n"
        b"CATEGORIES:Ferien\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url: ics)

    service.sync_feed(conn, uid)
    rows = calendar_events_repo.list_for_user(conn, uid, today="2026-01-01",
                                              timeframe="all", kinds={"frei"})
    assert len(rows) == 1
    assert rows[0]["kind"] == "frei"


def test_sync_persists_event_kind_for_wettbewerb(monkeypatch, conn, uid):
    from school_test_engine.ical_sync import service
    from school_test_engine.storage import calendar_events_repo, users_repo

    users_repo.update_user(conn, uid, ical_feed_url="https://example.com/feed")
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\n"
        b"UID:w1\nSUMMARY:Mathewettbewerb\n"
        b"DTSTART;TZID=Europe/Berlin:20260428T112500\n"
        b"DTEND;TZID=Europe/Berlin:20260428T125500\n"
        b"CATEGORIES:Arbeiten\n"
        b"END:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url: ics)

    service.sync_feed(conn, uid)
    rows = calendar_events_repo.list_for_user(conn, uid, today="2026-01-01",
                                              timeframe="all", kinds={"event"})
    assert len(rows) == 1
    assert rows[0]["title"] == "Mathewettbewerb"


def test_sync_updates_calendar_event_when_date_changes(monkeypatch, conn, uid):
    from school_test_engine.ical_sync import service
    from school_test_engine.storage import users_repo

    users_repo.update_user(conn, uid, ical_feed_url="https://example.com/feed")
    ics_v1 = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\nUID:f1\nSUMMARY:Herbst\n"
        b"DTSTART;VALUE=DATE:20261019\nDTEND;VALUE=DATE:20261101\n"
        b"CATEGORIES:Ferien\nEND:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url: ics_v1)
    service.sync_feed(conn, uid)

    ics_v2 = ics_v1.replace(b"20261019", b"20261020").replace(b"20261101", b"20261102")
    monkeypatch.setattr(service, "_fetch", lambda url: ics_v2)
    result = service.sync_feed(conn, uid)
    assert result.cal_updated == 1


def test_sync_deletes_calendar_event_when_gone_from_feed(monkeypatch, conn, uid):
    from school_test_engine.ical_sync import service
    from school_test_engine.storage import calendar_events_repo, users_repo

    users_repo.update_user(conn, uid, ical_feed_url="https://example.com/feed")
    ics_v1 = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\nUID:f1\nSUMMARY:Herbst\n"
        b"DTSTART;VALUE=DATE:20261019\nDTEND;VALUE=DATE:20261101\n"
        b"CATEGORIES:Ferien\nEND:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url: ics_v1)
    service.sync_feed(conn, uid)

    ics_v2 = b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\nEND:VCALENDAR\n"
    monkeypatch.setattr(service, "_fetch", lambda url: ics_v2)
    result = service.sync_feed(conn, uid)
    assert result.cal_deleted == 1
    assert calendar_events_repo.list_external_uids(conn, uid) == set()


def test_sync_mixed_feed_writes_to_both_tables(monkeypatch, conn, uid):
    from school_test_engine.ical_sync import service
    from school_test_engine.storage import (
        calendar_events_repo, events_repo, users_repo,
    )

    users_repo.update_user(conn, uid, ical_feed_url="https://example.com/feed")
    ics = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:test\n"
        b"BEGIN:VEVENT\nUID:f1\nSUMMARY:Sommer\n"
        b"DTSTART;VALUE=DATE:20260707\nDTEND;VALUE=DATE:20260817\n"
        b"CATEGORIES:Ferien\nEND:VEVENT\n"
        b"BEGIN:VEVENT\n"
        b"UID:20010101T000001-klausur-9084-14627-2026-03-10@x.org\n"
        b"SUMMARY:Mathe R8b Arbeit\nDESCRIPTION:Arbeit in Mathematik R8b (082M07-R)\n"
        b"DTSTART;TZID=Europe/Berlin:20260310T093500\n"
        b"DTEND;TZID=Europe/Berlin:20260310T110500\n"
        b"CATEGORIES:Arbeiten\nEND:VEVENT\n"
        b"END:VCALENDAR\n"
    )
    monkeypatch.setattr(service, "_fetch", lambda url: ics)

    result = service.sync_feed(conn, uid)
    assert result.added == 1            # KA
    assert result.cal_added == 1        # Ferien
    assert len(events_repo.list_all(conn, uid)) == 1
    cal_rows = calendar_events_repo.list_for_user(
        conn, uid, today="2026-01-01", timeframe="all",
        kinds={"ferien", "frei", "event"},
    )
    assert len(cal_rows) == 1
```

Add a top-of-file fixture if not already present:

```python
# tests/ical_sync/test_service.py — at the top of the file, after imports
@pytest.fixture
def uid(conn):
    from school_test_engine.storage import users_repo
    return users_repo.create_user(conn, name="Clemens")
```

(Only add if `uid` fixture is not already in the file — check first.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ical_sync/test_service.py -v -k "cal_added or persists_multi or persists_single or persists_event or updates_calendar or deletes_calendar or mixed_feed"`
Expected: FAIL — `SyncResult` has no `cal_added`/`cal_updated`/`cal_deleted` attr.

- [ ] **Step 3: Rewrite service.py for dual write path**

```python
# src/school_test_engine/ical_sync/service.py
"""Orchestrate fetch → parse → classify → split → diff → apply.

KAs land in scheduled_events (Phase 7-Pfad); Ferien/Frei/Event in calendar_events
(Phase 17). Both paths run during the same sync_feed call.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from ..storage import (
    assessments_repo, calendar_events_repo, events_repo, users_repo,
)
from . import classifier, extractor, fetcher, parser
from .extractor import EventRecord
from .fetcher import FeedFetchError


@dataclass(frozen=True)
class SyncResult:
    added: int = 0
    updated: int = 0
    deleted: int = 0
    cal_added: int = 0
    cal_updated: int = 0
    cal_deleted: int = 0
    skipped: int = 0
    error: str | None = None
    synced_at: str = ""


_fetch = fetcher.fetch_feed


@dataclass(frozen=True)
class _CalRecord:
    external_uid: str
    kind: str
    title: str
    start_date: str
    end_date: str


def sync_feed(conn: sqlite3.Connection, user_id: int) -> SyncResult:
    user = users_repo.get_user(conn, user_id)
    if user is None or not user["ical_feed_url"]:
        return SyncResult(error="Keine Feed-URL hinterlegt")
    url = user["ical_feed_url"]
    try:
        raw_bytes = _fetch(url)
        events = parser.parse_events(raw_bytes)
    except (FeedFetchError, ValueError) as e:
        return _persist_error(conn, user_id, str(e))

    klausuren: list[EventRecord] = []
    cal_records: list[_CalRecord] = []
    skipped = 0

    for v in events:
        kind = classifier.classify(v)
        if kind is None:
            skipped += 1
            continue
        if kind == "klausur":
            rec = extractor.to_event_record(v)
            if rec is None:
                skipped += 1
            else:
                klausuren.append(rec)
        else:
            cal_records.append(_CalRecord(
                external_uid=v.uid,
                kind=kind,
                title=v.summary,
                start_date=v.dtstart_date,
                end_date=v.dtend_date,
            ))

    adds, updates, deletes = _diff_klausuren(conn, user_id, klausuren)
    _apply_klausuren(conn, user_id, adds, updates, deletes)

    cal_adds, cal_updates, cal_deletes = _diff_calendar(conn, user_id, cal_records)
    _apply_calendar(conn, user_id, cal_adds, cal_updates, cal_deletes)

    return _persist_summary(
        conn, user_id,
        added=len(adds), updated=len(updates), deleted=len(deletes),
        cal_added=len(cal_adds), cal_updated=len(cal_updates),
        cal_deleted=len(cal_deletes),
        skipped=skipped,
    )


def _diff_klausuren(conn, user_id, feed_records: list[EventRecord]):
    feed_by_uid = {r.external_uid: r for r in feed_records}
    db_rows = events_repo.list_with_external_uid(conn, user_id)
    db_by_uid = {r["external_uid"]: r for r in db_rows}

    adds = [r for uid, r in feed_by_uid.items() if uid not in db_by_uid]
    updates = [
        (r, db_by_uid[r.external_uid])
        for uid, r in feed_by_uid.items()
        if uid in db_by_uid and _has_klausur_changes(r, db_by_uid[uid])
    ]
    delete_candidates = [row for uid, row in db_by_uid.items() if uid not in feed_by_uid]
    deletes = [
        row for row in delete_candidates
        if assessments_repo.find_by_event(conn, row["id"]) is None
    ]
    return adds, updates, deletes


def _has_klausur_changes(rec: EventRecord, db_row) -> bool:
    return (
        rec.event_date != db_row["event_date"]
        or rec.subject != db_row["subject"]
        or rec.kind != db_row["kind"]
    )


def _apply_klausuren(conn, user_id, adds, updates, deletes):
    for rec in adds:
        events_repo.create(
            conn, user_id,
            rec.subject, rec.kind, rec.event_date,
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


def _diff_calendar(conn, user_id, feed_records: list[_CalRecord]):
    feed_by_uid = {r.external_uid: r for r in feed_records}
    db_rows = calendar_events_repo.list_with_external_uid(conn, user_id)
    db_by_uid = {r["external_uid"]: r for r in db_rows}

    adds = [r for uid, r in feed_by_uid.items() if uid not in db_by_uid]
    updates = [
        r for uid, r in feed_by_uid.items()
        if uid in db_by_uid and _has_calendar_changes(r, db_by_uid[uid])
    ]
    deletes = [row for uid, row in db_by_uid.items() if uid not in feed_by_uid]
    return adds, updates, deletes


def _has_calendar_changes(rec: _CalRecord, db_row) -> bool:
    return (
        rec.kind != db_row["kind"]
        or rec.title != db_row["title"]
        or rec.start_date != db_row["start_date"]
        or rec.end_date != db_row["end_date"]
    )


def _apply_calendar(conn, user_id, adds, updates, deletes):
    for rec in adds:
        calendar_events_repo.create(
            conn,
            user_id=user_id,
            kind=rec.kind,
            title=rec.title,
            start_date=rec.start_date,
            end_date=rec.end_date,
            external_uid=rec.external_uid,
            external_source="schulportal_hessen",
        )
    for rec in updates:
        calendar_events_repo.update_by_external_uid(
            conn,
            user_id=user_id,
            external_uid=rec.external_uid,
            kind=rec.kind, title=rec.title,
            start_date=rec.start_date, end_date=rec.end_date,
        )
    for row in deletes:
        calendar_events_repo.delete_by_external_uid(conn, user_id, row["external_uid"])


def _persist_summary(
    conn, user_id, *,
    added, updated, deleted,
    cal_added, cal_updated, cal_deleted,
    skipped,
) -> SyncResult:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary_json = json.dumps({
        "added": added, "updated": updated, "deleted": deleted,
        "cal_added": cal_added, "cal_updated": cal_updated, "cal_deleted": cal_deleted,
        "skipped": skipped, "error": None,
    })
    users_repo.update_user(
        conn, user_id,
        ical_last_sync_at=now,
        ical_last_sync_summary=summary_json,
    )
    return SyncResult(
        added=added, updated=updated, deleted=deleted,
        cal_added=cal_added, cal_updated=cal_updated, cal_deleted=cal_deleted,
        skipped=skipped, synced_at=now,
    )


def _persist_error(conn, user_id, error_msg: str) -> SyncResult:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary_json = json.dumps({
        "added": 0, "updated": 0, "deleted": 0,
        "cal_added": 0, "cal_updated": 0, "cal_deleted": 0,
        "skipped": 0, "error": error_msg,
    })
    users_repo.update_user(
        conn, user_id,
        ical_last_sync_at=now,
        ical_last_sync_summary=summary_json,
    )
    return SyncResult(error=error_msg, synced_at=now)
```

- [ ] **Step 4: Run all sync tests**

Run: `pytest tests/ical_sync/test_service.py -v`
Expected: existing + 6 new pass.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ical_sync/service.py tests/ical_sync/test_service.py
git commit -m "feat(ical_sync/service): dual write path — KAs + calendar_events"
```

---

## Task 8: school_calendar package — CalendarEntry + CalendarFilters

**Files:**
- Create: `src/school_test_engine/school_calendar/__init__.py`
- Create: `src/school_test_engine/school_calendar/models.py`
- Create: `src/school_test_engine/school_calendar/filters.py`
- Create: `tests/school_calendar/__init__.py`
- Create: `tests/school_calendar/test_models.py`
- Create: `tests/school_calendar/test_filters.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/school_calendar/test_models.py
from __future__ import annotations

from datetime import date

import pytest

from school_test_engine.school_calendar.models import CalendarEntry


def test_calendar_entry_is_frozen():
    e = CalendarEntry(
        source="klausur", kind="klausur",
        title="Mathe Klassenarbeit",
        start_date=date(2026, 5, 15), end_date=date(2026, 5, 15),
        subject="Mathe", entry_id=42,
    )
    import dataclasses
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.title = "x"  # type: ignore


def test_is_multi_day_true_for_range():
    e = CalendarEntry(
        source="calendar", kind="ferien", title="Sommer",
        start_date=date(2026, 7, 7), end_date=date(2026, 8, 15),
        subject=None, entry_id=1,
    )
    assert e.is_multi_day is True


def test_is_multi_day_false_for_single_day():
    e = CalendarEntry(
        source="calendar", kind="frei", title="Päd. Tag",
        start_date=date(2026, 5, 12), end_date=date(2026, 5, 12),
        subject=None, entry_id=2,
    )
    assert e.is_multi_day is False
```

```python
# tests/school_calendar/test_filters.py
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.school_calendar.filters import CalendarFilters
from school_test_engine.storage import run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def test_defaults_all_kinds_on_future():
    f = CalendarFilters.defaults()
    assert f.show_klausuren is True
    assert f.show_ferien is True
    assert f.show_frei is True
    assert f.show_events is True
    assert f.timeframe == "future"


def test_from_user_row_reads_db_state(conn):
    uid = users_repo.create_user(conn, name="T")
    users_repo.update_user(conn, uid, calendar_show_klausuren=0, calendar_timeframe="past")
    row = users_repo.get_user(conn, uid)
    f = CalendarFilters.from_user_row(row)
    assert f.show_klausuren is False
    assert f.show_ferien is True
    assert f.timeframe == "past"


def test_with_kind_set_returns_new_instance():
    f = CalendarFilters.defaults()
    f2 = f.with_kind_set("ferien", False)
    assert f.show_ferien is True   # original unchanged
    assert f2.show_ferien is False


def test_active_kinds_reflects_toggles():
    f = CalendarFilters.defaults().with_kind_set("frei", False).with_kind_set("event", False)
    assert f.active_kinds() == {"klausur", "ferien"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/school_calendar/ -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement package**

```python
# src/school_test_engine/school_calendar/__init__.py
"""Schulkalender domain — view-only over scheduled_events + calendar_events."""
```

```python
# src/school_test_engine/school_calendar/models.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

Source = Literal["klausur", "calendar"]
Kind = Literal["klausur", "ferien", "frei", "event"]


@dataclass(frozen=True)
class CalendarEntry:
    """A merged entry: KA from scheduled_events or a row from calendar_events."""
    source: Source
    kind: Kind
    title: str
    start_date: date
    end_date: date
    subject: str | None
    entry_id: int

    @property
    def is_multi_day(self) -> bool:
        return self.end_date > self.start_date
```

```python
# src/school_test_engine/school_calendar/filters.py
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from typing import Literal

Timeframe = Literal["future", "all", "past"]
_KIND_TO_FIELD = {
    "klausur": "show_klausuren",
    "ferien": "show_ferien",
    "frei": "show_frei",
    "event": "show_events",
}


@dataclass(frozen=True)
class CalendarFilters:
    show_klausuren: bool
    show_ferien: bool
    show_frei: bool
    show_events: bool
    timeframe: Timeframe

    @classmethod
    def defaults(cls) -> "CalendarFilters":
        return cls(True, True, True, True, "future")

    @classmethod
    def from_user_row(cls, row: sqlite3.Row) -> "CalendarFilters":
        return cls(
            show_klausuren=bool(row["calendar_show_klausuren"]),
            show_ferien=bool(row["calendar_show_ferien"]),
            show_frei=bool(row["calendar_show_frei"]),
            show_events=bool(row["calendar_show_events"]),
            timeframe=row["calendar_timeframe"],
        )

    def with_kind_set(self, kind: str, value: bool) -> "CalendarFilters":
        field = _KIND_TO_FIELD[kind]
        return replace(self, **{field: value})

    def with_timeframe(self, tf: str) -> "CalendarFilters":
        return replace(self, timeframe=tf)  # type: ignore[arg-type]

    def active_kinds(self) -> set[str]:
        out: set[str] = set()
        if self.show_klausuren: out.add("klausur")
        if self.show_ferien:    out.add("ferien")
        if self.show_frei:      out.add("frei")
        if self.show_events:    out.add("event")
        return out
```

```python
# tests/school_calendar/__init__.py
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/school_calendar/ -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/school_calendar/ tests/school_calendar/
git commit -m "feat(school_calendar): CalendarEntry + CalendarFilters dataclasses"
```

---

## Task 9: events_repo.list_for_calendar

**Files:**
- Modify: `src/school_test_engine/storage/events_repo.py`
- Create: `tests/storage/test_events_repo_list_for_calendar.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/storage/test_events_repo_list_for_calendar.py
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import events_repo, run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def test_list_for_calendar_returns_all_kas_sorted_by_date(conn):
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-01")
    events_repo.create(conn, uid, "Englisch", "klausur", "2026-05-15")
    events_repo.create(conn, uid, "Bio", "test", "2026-07-10")
    rows = events_repo.list_for_calendar(conn, uid)
    dates = [r["event_date"] for r in rows]
    assert dates == ["2026-05-15", "2026-06-01", "2026-07-10"]


def test_list_for_calendar_scopes_by_user(conn):
    a = users_repo.create_user(conn, name="A")
    b = users_repo.create_user(conn, name="B")
    events_repo.create(conn, a, "Mathe", "klassenarbeit", "2026-06-01")
    events_repo.create(conn, b, "Englisch", "klausur", "2026-05-15")
    rows = events_repo.list_for_calendar(conn, a)
    assert len(rows) == 1
    assert rows[0]["subject"] == "Mathe"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/test_events_repo_list_for_calendar.py -v`
Expected: FAIL — `events_repo` has no `list_for_calendar`.

- [ ] **Step 3: Add the function to events_repo.py**

Append at end of `src/school_test_engine/storage/events_repo.py`:

```python
def list_for_calendar(
    conn: sqlite3.Connection, user_id: int
) -> list[sqlite3.Row]:
    """All KAs of one user, sorted ASC by event_date for the calendar view."""
    cur = conn.execute(
        """
        SELECT * FROM scheduled_events
        WHERE user_id = ?
        ORDER BY event_date ASC, created_at ASC
        """,
        (user_id,),
    )
    return cur.fetchall()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/storage/test_events_repo_list_for_calendar.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/events_repo.py \
        tests/storage/test_events_repo_list_for_calendar.py
git commit -m "feat(storage/events_repo): list_for_calendar — ASC sorted KAs"
```

---

## Task 10: school_calendar.service — list_entries + group_by_month

**Files:**
- Create: `src/school_test_engine/school_calendar/service.py`
- Create: `tests/school_calendar/test_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/school_calendar/test_service.py
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.school_calendar.filters import CalendarFilters
from school_test_engine.school_calendar.service import (
    group_by_month, list_entries,
)
from school_test_engine.storage import (
    calendar_events_repo, events_repo, run_migrations, users_repo,
)


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, name="C")


def test_list_entries_merges_klausuren_and_calendar_chronologically(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-15")
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommer",
                                start_date="2026-07-07", end_date="2026-08-15")
    calendar_events_repo.create(conn, user_id=uid, kind="frei", title="Päd. Tag",
                                start_date="2026-05-28", end_date="2026-05-28")
    entries = list_entries(conn, uid, date(2026, 5, 1), CalendarFilters.defaults())
    titles = [e.title for e in entries]
    assert titles[0] == "Päd. Tag"
    assert titles[1].startswith("Mathe")
    assert titles[2] == "Sommer"


def test_list_entries_filters_klausur_out(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-15")
    f = CalendarFilters.defaults().with_kind_set("klausur", False)
    entries = list_entries(conn, uid, date(2026, 5, 1), f)
    assert entries == []


def test_list_entries_respects_timeframe_for_klausuren(conn, uid):
    events_repo.create(conn, uid, "Past", "klassenarbeit", "2024-05-01")
    events_repo.create(conn, uid, "Future", "klassenarbeit", "2030-05-01")
    f = CalendarFilters.defaults()  # future
    entries = list_entries(conn, uid, date(2026, 5, 15), f)
    subjects = [e.subject for e in entries]
    assert subjects == ["Future"]


def test_list_entries_empty_active_kinds_returns_empty(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2030-06-15")
    f = CalendarFilters(False, False, False, False, "future")
    assert list_entries(conn, uid, date(2026, 1, 1), f) == []


def test_group_by_month_returns_sections_in_chronological_order(conn, uid):
    events_repo.create(conn, uid, "A", "klassenarbeit", "2026-05-10")
    events_repo.create(conn, uid, "B", "klassenarbeit", "2026-07-03")
    events_repo.create(conn, uid, "C", "klassenarbeit", "2026-05-20")
    entries = list_entries(conn, uid, date(2026, 1, 1), CalendarFilters.defaults())
    groups = group_by_month(entries)
    labels = [g[0] for g in groups]
    assert labels == ["Mai 2026", "Juli 2026"]
    assert [e.subject for e in groups[0][1]] == ["A", "C"]


def test_klausur_entry_title_includes_subject_and_kind(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-15")
    entries = list_entries(conn, uid, date(2026, 5, 1), CalendarFilters.defaults())
    assert entries[0].title == "Mathe Klassenarbeit"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/school_calendar/test_service.py -v`
Expected: FAIL — `school_calendar.service` missing.

- [ ] **Step 3: Implement school_calendar/service.py**

```python
# src/school_test_engine/school_calendar/service.py
"""Schulkalender service: merge KAs + calendar_events, filter, group."""
from __future__ import annotations

import sqlite3
from datetime import date

from ..storage import calendar_events_repo, events_repo
from .filters import CalendarFilters
from .models import CalendarEntry


_KIND_LABEL = {
    "klassenarbeit": "Klassenarbeit",
    "klausur": "Klausur",
    "test": "Test",
    "sonstiges": "Termin",
}

_MONTHS_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def list_entries(
    conn: sqlite3.Connection,
    user_id: int,
    today: date,
    filters: CalendarFilters,
) -> list[CalendarEntry]:
    active = filters.active_kinds()
    if not active:
        return []

    entries: list[CalendarEntry] = []

    if "klausur" in active:
        for row in events_repo.list_for_calendar(conn, user_id):
            entries.append(_from_klausur_row(row))

    cal_kinds = active - {"klausur"}
    if cal_kinds:
        for row in calendar_events_repo.list_for_user(
            conn, user_id,
            today=today.isoformat(),
            timeframe=filters.timeframe,
            kinds=cal_kinds,
        ):
            entries.append(_from_calendar_row(row))

    entries = _apply_timeframe(entries, today, filters.timeframe)
    entries.sort(key=lambda e: (e.start_date, e.kind, e.entry_id))
    return entries


def group_by_month(
    entries: list[CalendarEntry],
) -> list[tuple[str, list[CalendarEntry]]]:
    out: list[tuple[str, list[CalendarEntry]]] = []
    current_key: tuple[int, int] | None = None
    for e in entries:
        key = (e.start_date.year, e.start_date.month)
        if key != current_key:
            label = f"{_MONTHS_DE[e.start_date.month - 1]} {e.start_date.year}"
            out.append((label, []))
            current_key = key
        out[-1][1].append(e)
    return out


def _apply_timeframe(
    entries: list[CalendarEntry], today: date, timeframe: str
) -> list[CalendarEntry]:
    if timeframe == "future":
        return [e for e in entries if e.end_date >= today]
    if timeframe == "past":
        return [e for e in entries if e.end_date < today]
    return entries


def _from_klausur_row(row: sqlite3.Row) -> CalendarEntry:
    d = date.fromisoformat(row["event_date"])
    kind_label = _KIND_LABEL.get(row["kind"], row["kind"].title())
    title = f"{row['subject']} {kind_label}"
    return CalendarEntry(
        source="klausur",
        kind="klausur",
        title=title,
        start_date=d,
        end_date=d,
        subject=row["subject"],
        entry_id=row["id"],
    )


def _from_calendar_row(row: sqlite3.Row) -> CalendarEntry:
    return CalendarEntry(
        source="calendar",
        kind=row["kind"],
        title=row["title"],
        start_date=date.fromisoformat(row["start_date"]),
        end_date=date.fromisoformat(row["end_date"]),
        subject=None,
        entry_id=row["id"],
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/school_calendar/test_service.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/school_calendar/service.py \
        tests/school_calendar/test_service.py
git commit -m "feat(school_calendar): list_entries + group_by_month service"
```

---

## Task 11: ferien_banner_state — Service-Funktion + State-Dataclass

**Files:**
- Modify: `src/school_test_engine/school_calendar/service.py`
- Create: `tests/school_calendar/test_ferien_banner_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/school_calendar/test_ferien_banner_service.py
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.school_calendar.service import (
    FerienBannerState, ferien_banner_state,
)
from school_test_engine.storage import calendar_events_repo, run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, name="C")


def test_hidden_when_no_vacations(conn, uid):
    state = ferien_banner_state(conn, uid, date(2026, 5, 15))
    assert state.mode == "hidden"


def test_countdown_to_next_vacation(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Herbstferien",
                                start_date="2026-10-19", end_date="2026-10-31")
    state = ferien_banner_state(conn, uid, date(2026, 9, 26))
    assert state.mode == "countdown"
    assert state.days == 23
    assert state.vacation_title == "Herbstferien"
    assert "23" in state.label
    assert "Herbstferien" in state.label


def test_countdown_label_for_one_day_uses_morgen(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommerferien",
                                start_date="2026-07-07", end_date="2026-08-15")
    state = ferien_banner_state(conn, uid, date(2026, 7, 6))
    assert state.days == 1
    assert "Morgen" in state.label


def test_in_vacation_remaining_days(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommerferien",
                                start_date="2026-07-07", end_date="2026-08-15")
    state = ferien_banner_state(conn, uid, date(2026, 8, 10))
    assert state.mode == "in_vacation"
    assert state.days == 5
    assert "5" in state.label
    assert "Sommerferien" in state.label


def test_in_vacation_zero_days_is_last_day(conn, uid):
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommerferien",
                                start_date="2026-07-07", end_date="2026-08-15")
    state = ferien_banner_state(conn, uid, date(2026, 8, 15))
    assert state.mode == "in_vacation"
    assert state.days == 0
    assert "Letzter Ferientag" in state.label


def test_frei_kind_does_not_trigger_banner(conn, uid):
    """Single-day frei (Pädagogischer Tag) MUST NOT show as ferien banner."""
    calendar_events_repo.create(conn, user_id=uid, kind="frei", title="Päd. Tag",
                                start_date="2026-05-28", end_date="2026-05-28")
    state = ferien_banner_state(conn, uid, date(2026, 5, 15))
    assert state.mode == "hidden"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/school_calendar/test_ferien_banner_service.py -v`
Expected: FAIL.

- [ ] **Step 3: Append to school_calendar/service.py**

Add to `src/school_test_engine/school_calendar/service.py`:

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FerienBannerState:
    mode: Literal["hidden", "countdown", "in_vacation"]
    label: str
    days: int | None
    target_date: date | None
    vacation_title: str | None


def ferien_banner_state(
    conn: sqlite3.Connection, user_id: int, today: date
) -> FerienBannerState:
    today_iso = today.isoformat()

    active = calendar_events_repo.find_active_vacation(conn, user_id, today_iso)
    if active is not None:
        end = date.fromisoformat(active["end_date"])
        remaining = (end - today).days
        title = active["title"]
        if remaining == 0:
            label = "Letzter Ferientag — morgen geht's wieder los."
        else:
            label = f"Noch {remaining} Tage {title} — genieß sie! 🌞"
        return FerienBannerState(
            mode="in_vacation", label=label, days=remaining,
            target_date=end, vacation_title=title,
        )

    upcoming = calendar_events_repo.find_next_vacation(conn, user_id, today_iso)
    if upcoming is not None:
        start = date.fromisoformat(upcoming["start_date"])
        days = (start - today).days
        title = upcoming["title"]
        if days == 1:
            label = f"Morgen geht's los: {title} starten!"
        else:
            label = f"Noch {days} Tage bis {title} — {start.strftime('%d.%m.%Y')}"
        return FerienBannerState(
            mode="countdown", label=label, days=days,
            target_date=start, vacation_title=title,
        )

    return FerienBannerState(
        mode="hidden", label="", days=None, target_date=None, vacation_title=None,
    )
```

(Move the `from dataclasses import dataclass` import to the top of the file if not already present; add `from typing import Literal` if missing.)

- [ ] **Step 4: Run tests**

Run: `pytest tests/school_calendar/test_ferien_banner_service.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/school_calendar/service.py \
        tests/school_calendar/test_ferien_banner_service.py
git commit -m "feat(school_calendar): ferien_banner_state — 5 modes including in-vacation"
```

---

## Task 12: CalendarEntryCard widget

**Files:**
- Create: `src/school_test_engine/ui/widgets/calendar_entry_card.py`
- Create: `tests/ui/test_calendar_entry_card.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ui/test_calendar_entry_card.py
from __future__ import annotations

from datetime import date

import pytest

from school_test_engine.school_calendar.models import CalendarEntry


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _entry(**kw):
    base = dict(
        source="calendar", kind="ferien", title="Sommerferien",
        start_date=date(2026, 7, 7), end_date=date(2026, 8, 15),
        subject=None, entry_id=1,
    )
    base.update(kw)
    return CalendarEntry(**base)


def test_card_renders_date_for_single_day():
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard
    e = _entry(kind="klausur", source="klausur",
               start_date=date(2026, 5, 15), end_date=date(2026, 5, 15),
               title="Mathe Klassenarbeit", subject="Mathe")
    card = CalendarEntryCard(e)
    assert card._date_label.text() == "15.05."


def test_card_renders_date_range_for_multi_day():
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard
    card = CalendarEntryCard(_entry())
    assert card._date_label.text() == "07.07.–15.08."


def test_klausur_card_is_clickable_and_emits_signal():
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard
    e = _entry(kind="klausur", source="klausur", subject="Mathe",
               start_date=date(2026, 5, 15), end_date=date(2026, 5, 15),
               entry_id=42, title="Mathe Klassenarbeit")
    card = CalendarEntryCard(e)
    received: list[int] = []
    card.clicked.connect(received.append)
    # Direkter Signal-Emit (kein QTest Click — wir testen die Verdrahtung)
    card._maybe_emit_click()
    assert received == [42]


def test_non_klausur_card_does_not_emit_on_click():
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard
    card = CalendarEntryCard(_entry())     # kind='ferien'
    received: list[int] = []
    card.clicked.connect(received.append)
    card._maybe_emit_click()
    assert received == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_calendar_entry_card.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement widget**

```python
# src/school_test_engine/ui/widgets/calendar_entry_card.py
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ...school_calendar.models import CalendarEntry
from ..design import Color, FontFamily
from .pill import Pill


_PILL_VARIANT_FOR_KIND = {
    "klausur": "clay",
    "ferien": "tea",
    "frei": "honey",
    "event": "sky",
}

_PILL_LABEL_FOR_KIND = {
    "klausur": "KA",
    "ferien": "Ferien",
    "frei": "Frei",
    "event": "Event",
}


class CalendarEntryCard(QFrame):
    """Schlanke Card: [DateBadge] [Title] [Pill]. Klausur-Cards sind klickbar."""

    clicked = Signal(int)

    def __init__(self, entry: CalendarEntry, parent=None):
        super().__init__(parent)
        self.setObjectName("calendarEntryCard")
        self._entry = entry

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(12)

        self._date_label = QLabel(self._format_date_range(entry))
        self._date_label.setObjectName("dateBadge")
        self._date_label.setFont(QFont(FontFamily.MONO, 10))
        self._date_label.setMinimumWidth(110)
        h.addWidget(self._date_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel(entry.title)
        title.setFont(QFont(FontFamily.SANS, 11, QFont.Weight.Medium))
        title_col.addWidget(title)
        h.addLayout(title_col)

        h.addStretch(1)

        pill = Pill(_PILL_LABEL_FOR_KIND[entry.kind],
                    variant=_PILL_VARIANT_FOR_KIND[entry.kind])
        h.addWidget(pill)

        if entry.kind == "klausur":
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _format_date_range(self, e: CalendarEntry) -> str:
        if e.is_multi_day:
            same_year = e.start_date.year == e.end_date.year
            if same_year:
                return f"{e.start_date.strftime('%d.%m.')}–{e.end_date.strftime('%d.%m.')}"
            return (
                f"{e.start_date.strftime('%d.%m.%Y')}–"
                f"{e.end_date.strftime('%d.%m.%Y')}"
            )
        return e.start_date.strftime("%d.%m.")

    def _maybe_emit_click(self) -> None:
        if self._entry.kind == "klausur":
            self.clicked.emit(self._entry.entry_id)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._maybe_emit_click()
        super().mousePressEvent(event)
```

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_calendar_entry_card.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/widgets/calendar_entry_card.py \
        tests/ui/test_calendar_entry_card.py
git commit -m "feat(ui/widget): CalendarEntryCard — date badge + title + kind pill"
```

---

## Task 13: FerienBanner widget

**Files:**
- Create: `src/school_test_engine/ui/widgets/ferien_banner.py`
- Create: `tests/ui/test_ferien_banner_widget.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ui/test_ferien_banner_widget.py
from __future__ import annotations

from datetime import date

import pytest

from school_test_engine.school_calendar.service import FerienBannerState


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_banner_label_reflects_state():
    from school_test_engine.ui.widgets.ferien_banner import FerienBanner
    s = FerienBannerState(
        mode="countdown",
        label="Noch 23 Tage bis Herbstferien — 17.10.2026",
        days=23, target_date=date(2026, 10, 17),
        vacation_title="Herbstferien",
    )
    b = FerienBanner(s)
    assert "23" in b._label.text()
    assert "Herbstferien" in b._label.text()


def test_banner_click_calls_window_show_school_calendar(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF
    from school_test_engine.ui.widgets.ferien_banner import FerienBanner

    class _StubWindow:
        def __init__(self):
            self.called = 0
        def show_school_calendar(self):
            self.called += 1

    win = _StubWindow()
    s = FerienBannerState(mode="countdown", label="x", days=1,
                          target_date=date(2026, 1, 1), vacation_title="X")
    b = FerienBanner(s, get_window=lambda: win)
    ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(1, 1), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    b.mousePressEvent(ev)
    assert win.called == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_ferien_banner_widget.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement widget**

```python
# src/school_test_engine/ui/widgets/ferien_banner.py
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ...school_calendar.service import FerienBannerState
from ..design import Color, FontFamily


class FerienBanner(QFrame):
    """Klickbare Card unter der Menü-Begrüßung — Countdown / In-Vacation."""

    def __init__(
        self,
        state: FerienBannerState,
        parent=None,
        get_window: Callable | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("ferienBanner")
        self._state = state
        self._get_window = get_window or (lambda: self.window())
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(12)

        # 4px tea-strip on the left (paint via fixed-width frame with QSS color)
        strip = QFrame()
        strip.setObjectName("ferienBannerStrip")
        strip.setFixedWidth(4)
        h.addWidget(strip)

        emoji = QLabel("🌴" if state.mode == "countdown" else "🌞")
        emoji.setStyleSheet("font-size: 18pt;")
        h.addWidget(emoji)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._label = QLabel(state.label)
        self._label.setFont(QFont(FontFamily.SANS, 11, QFont.Weight.Medium))
        text_col.addWidget(self._label)

        if state.mode == "countdown" and state.target_date:
            sub = QLabel(f"Beginn: {state.target_date.strftime('%d.%m.%Y')}")
            sub.setStyleSheet(f"color: {Color.PAPER_500}; font-size: 9pt;")
            text_col.addWidget(sub)

        h.addLayout(text_col)
        h.addStretch(1)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            win = self._get_window()
            if win is not None and hasattr(win, "show_school_calendar"):
                win.show_school_calendar()
        super().mousePressEvent(event)
```

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_ferien_banner_widget.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/widgets/ferien_banner.py \
        tests/ui/test_ferien_banner_widget.py
git commit -m "feat(ui/widget): FerienBanner — countdown/in-vacation, clickable"
```

---

## Task 14: SchoolCalendarPage

**Files:**
- Create: `src/school_test_engine/ui/pages/school_calendar.py`
- Create: `tests/ui/test_school_calendar_page.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ui/test_school_calendar_page.py
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.storage import (
    calendar_events_repo, events_repo, run_migrations, users_repo,
)


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


class _StubWindow:
    def __init__(self, conn, user_id):
        self.conn = conn
        self.active_user_id = user_id
        self.opened_event_id: int | None = None
    def show_event_edit(self, event_id, return_to="menu"):
        self.opened_event_id = event_id


def test_page_renders_chronological_entries_from_both_sources(conn):
    uid = users_repo.create_user(conn, name="C")
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2030-06-15")
    calendar_events_repo.create(conn, user_id=uid, kind="ferien", title="Sommer",
                                start_date="2030-07-07", end_date="2030-08-15")
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=date(2030, 5, 1))
    page.reload()
    titles = [c._entry.title for c in page._cards]
    assert titles == ["Mathe Klassenarbeit", "Sommer"]


def test_chip_toggle_persists_filter(conn):
    uid = users_repo.create_user(conn, name="C")
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=date(2030, 5, 1))
    page.reload()
    page._on_chip_toggled("ferien", False)
    row = users_repo.get_user(conn, uid)
    assert row["calendar_show_ferien"] == 0


def test_tab_change_persists_timeframe(conn):
    uid = users_repo.create_user(conn, name="C")
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=date(2030, 5, 1))
    page.reload()
    page._on_timeframe_changed("past")
    row = users_repo.get_user(conn, uid)
    assert row["calendar_timeframe"] == "past"


def test_empty_states_when_all_filters_off(conn):
    uid = users_repo.create_user(conn, name="C")
    users_repo.update_user(
        conn, uid,
        calendar_show_klausuren=0, calendar_show_ferien=0,
        calendar_show_frei=0, calendar_show_events=0,
    )
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=date(2030, 5, 1))
    page.reload()
    assert page._empty_label.isVisible() is True
    assert "ausgeschaltet" in page._empty_label.text()


def test_klausur_click_opens_event_edit(conn):
    uid = users_repo.create_user(conn, name="C")
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2030-06-15")
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage
    win = _StubWindow(conn, uid)
    page = SchoolCalendarPage(win, conn, today=date(2030, 5, 1))
    page.reload()
    assert len(page._cards) == 1
    page._cards[0]._maybe_emit_click()
    assert win.opened_event_id == eid
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_school_calendar_page.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement page**

```python
# src/school_test_engine/ui/pages/school_calendar.py
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ...school_calendar.filters import CalendarFilters
from ...school_calendar.service import group_by_month, list_entries
from ...storage import users_repo
from ..design import Color, FontFamily
from ..widgets.calendar_entry_card import CalendarEntryCard
from ..widgets.eyebrow import Eyebrow


_CHIP_KINDS = [
    ("klausur", "KAs"),
    ("ferien", "Ferien"),
    ("frei", "Frei"),
    ("event", "Events"),
]
_TIMEFRAMES = [("future", "Ab heute"), ("all", "Alle"), ("past", "Vergangen")]


class SchoolCalendarPage(QWidget):
    """Agenda-Liste über KAs + calendar_events mit persistierten Filtern."""

    def __init__(self, window, conn: sqlite3.Connection, today: date | None = None):
        super().__init__()
        self.window = window
        self.conn = conn
        self._today_override = today
        self._user_id: int | None = window.active_user_id
        self._filters = CalendarFilters.defaults()
        self._loading = False
        self._cards: list[CalendarEntryCard] = []
        self._chip_buttons: dict[str, QPushButton] = {}
        self._tab_buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(14)

        outer.addWidget(Eyebrow("Schulkalender"))
        title = QLabel("Alle Termine")
        title.setObjectName("title")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        intro = QLabel(
            "Klassenarbeiten, Ferien, freie Tage und Schul-Events."
        )
        intro.setStyleSheet(f"color: {Color.PAPER_500}; font-size: 10pt;")
        outer.addWidget(intro)

        # Filter row: chips
        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        for kind, label in _CHIP_KINDS:
            b = QPushButton(label)
            b.setObjectName("filterChip")
            b.setCheckable(True)
            b.setChecked(True)
            b.toggled.connect(lambda checked, k=kind: self._on_chip_toggled(k, checked))
            self._chip_buttons[kind] = b
            chip_row.addWidget(b)
        chip_row.addStretch(1)
        outer.addLayout(chip_row)

        # Timeframe tabs
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        for tf, label in _TIMEFRAMES:
            b = QPushButton(label)
            b.setObjectName("subjectTab")
            b.setCheckable(True)
            b.clicked.connect(lambda _, t=tf: self._on_timeframe_changed(t))
            self._tab_group.addButton(b)
            self._tab_buttons[tf] = b
            tab_row.addWidget(b)
        tab_row.addStretch(1)
        outer.addLayout(tab_row)

        # Empty-State Label
        self._empty_label = QLabel("")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {Color.PAPER_600}; font-family: 'Fraunces'; "
            f"font-style: italic; font-size: 13pt; padding: 40px;"
        )
        self._empty_label.setVisible(False)
        outer.addWidget(self._empty_label)

        # Scrollable list
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list_host)
        outer.addWidget(self._scroll, 1)

    def _today(self) -> date:
        return self._today_override or date.today()

    def reload(self) -> None:
        self._user_id = self.window.active_user_id
        if self._user_id is None:
            return
        user_row = users_repo.get_user(self.conn, self._user_id)
        self._filters = CalendarFilters.from_user_row(user_row)
        self._loading = True
        try:
            self._apply_filters_to_ui()
        finally:
            self._loading = False
        self._reload_list_only()

    def _apply_filters_to_ui(self) -> None:
        for kind, btn in self._chip_buttons.items():
            checked = getattr(self._filters, _kind_field(kind))
            btn.setChecked(bool(checked))
        for tf, btn in self._tab_buttons.items():
            btn.setChecked(tf == self._filters.timeframe)

    def _reload_list_only(self) -> None:
        # Drop old cards (Phase 16 lesson: setParent(None) BEFORE deleteLater)
        self._clear_cards()
        if not self._filters.active_kinds():
            self._show_empty("Alle Filter sind ausgeschaltet — klick oben eine Kategorie an.")
            return
        entries = list_entries(self.conn, self._user_id, self._today(), self._filters)
        if not entries:
            self._show_empty("Keine Termine im gewählten Zeitraum.")
            return
        self._empty_label.setVisible(False)
        for month_label, month_entries in group_by_month(entries):
            self._add_month_header(month_label)
            for entry in month_entries:
                card = CalendarEntryCard(entry, parent=self._list_host)
                if entry.kind == "klausur":
                    card.clicked.connect(self._open_klausur)
                self._cards.append(card)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def _clear_cards(self) -> None:
        # Remove month headers AND cards (anything with objectName != stretch)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._cards = []

    def _add_month_header(self, label: str) -> None:
        eb = Eyebrow(label.upper())
        eb.setParent(self._list_host)
        self._list_layout.insertWidget(self._list_layout.count() - 1, eb)

    def _show_empty(self, text: str) -> None:
        self._empty_label.setText(text)
        self._empty_label.setVisible(True)

    def _on_chip_toggled(self, kind: str, checked: bool) -> None:
        if self._loading or self._user_id is None:
            return
        self._filters = self._filters.with_kind_set(kind, checked)
        users_repo.update_user(
            self.conn, self._user_id,
            **{_kind_db_column(kind): int(checked)},
        )
        self._reload_list_only()

    def _on_timeframe_changed(self, tf: str) -> None:
        if self._loading or self._user_id is None:
            return
        self._filters = self._filters.with_timeframe(tf)
        users_repo.update_user(self.conn, self._user_id, calendar_timeframe=tf)
        self._reload_list_only()

    def _open_klausur(self, event_id: int) -> None:
        if hasattr(self.window, "show_event_edit"):
            self.window.show_event_edit(event_id, return_to="school_calendar")


def _kind_field(kind: str) -> str:
    return {"klausur": "show_klausuren",
            "ferien": "show_ferien",
            "frei": "show_frei",
            "event": "show_events"}[kind]


def _kind_db_column(kind: str) -> str:
    return {"klausur": "calendar_show_klausuren",
            "ferien": "calendar_show_ferien",
            "frei": "calendar_show_frei",
            "event": "calendar_show_events"}[kind]
```

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_school_calendar_page.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/school_calendar.py \
        tests/ui/test_school_calendar_page.py
git commit -m "feat(ui/page): SchoolCalendarPage — agenda list with chips + tabs + persistence"
```

---

## Task 15: MainWindow + GlobalHeader integration

**Files:**
- Modify: `src/school_test_engine/ui/main_window.py`
- Modify: `src/school_test_engine/ui/widgets/global_header.py`
- Create: `tests/ui/test_global_header_school_calendar.py`

- [ ] **Step 1: Write failing test**

```python
# tests/ui/test_global_header_school_calendar.py
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_logo_menu_has_schulkalender_entry():
    from school_test_engine.ui.widgets.global_header import GlobalHeader

    class _StubWindow:
        def __init__(self):
            self.called = 0
        def show_menu(self): pass
        def show_test_create(self): pass
        def show_events(self): pass
        def show_grades(self): pass
        def show_error_book(self): pass
        def show_school_calendar(self):
            self.called += 1
        def show_profile_picker(self): pass

    win = _StubWindow()
    header = GlobalHeader(win)
    actions = header._logo_menu._menu.actions()
    labels = [a.text() for a in actions if a.text()]
    assert "Schulkalender" in labels
    # Trigger the action
    for a in actions:
        if a.text() == "Schulkalender":
            a.trigger()
    assert win.called == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_global_header_school_calendar.py -v`
Expected: FAIL — entry missing or `show_school_calendar` unknown.

- [ ] **Step 3: Add the menu entry**

In `src/school_test_engine/ui/widgets/global_header.py`, after the existing „Fehlerheft" line, add:

```python
        self._logo_menu.add_action("Schulkalender", window.show_school_calendar)
```

So the block reads:

```python
        self._logo_menu.add_action("Test erstellen", window.show_test_create)
        self._logo_menu.add_action("Termine", window.show_events)
        self._logo_menu.add_action("Noten", window.show_grades)
        self._logo_menu.add_action("Fehlerheft", window.show_error_book)
        self._logo_menu.add_action("Schulkalender", window.show_school_calendar)
        self._logo_menu.add_separator()
        self._logo_menu.add_action("Profil wechseln", window.show_profile_picker)
```

- [ ] **Step 4: Add MainWindow.show_school_calendar**

In `src/school_test_engine/ui/main_window.py`:

1. Add `self._school_calendar_page = None` to `__init__` (next to other page-holders).

2. Add the method (near other `show_*` methods):

```python
    def show_school_calendar(self) -> None:
        if self.active_user_id is None:
            return
        if self._school_calendar_page is None:
            from .pages.school_calendar import SchoolCalendarPage
            self._school_calendar_page = SchoolCalendarPage(self, self.conn)
            self._stack.addWidget(self._school_calendar_page)
            self.user_changed.connect(lambda _uid: self._school_calendar_page.reload())
            if hasattr(self, "events_synced"):
                self.events_synced.connect(self._school_calendar_page.reload)
        self._school_calendar_page.reload()
        self._stack.setCurrentWidget(self._school_calendar_page)
        self._global_header.set_page_actions([])
```

- [ ] **Step 5: Run tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_global_header_school_calendar.py -v`
Expected: 1 passed. Run also full UI suite to confirm no regressions: `QT_QPA_PLATFORM=offscreen pytest tests/ui/ -v`.

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/widgets/global_header.py \
        src/school_test_engine/ui/main_window.py \
        tests/ui/test_global_header_school_calendar.py
git commit -m "feat(ui): wire SchoolCalendarPage — logo-menu entry + MainWindow router"
```

---

## Task 16: MenuPage — FerienBanner slot

**Files:**
- Modify: `src/school_test_engine/ui/pages/menu.py`
- Create: `tests/ui/test_menu_page_ferien_banner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/ui/test_menu_page_ferien_banner.py
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.storage import (
    calendar_events_repo, run_migrations, users_repo,
)


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


class _StubWindow:
    def __init__(self, conn, uid):
        self.conn = conn
        self.active_user_id = uid
    # MenuPage probes various methods; provide no-op stubs as needed.


def _open_menu(conn, uid, today):
    from school_test_engine.ui.pages.menu import MenuPage
    win = _StubWindow(conn, uid)
    page = MenuPage(win, conn, today=today)
    page.reload()
    return page


def test_banner_renders_when_next_vacation_exists(conn):
    uid = users_repo.create_user(conn, name="C")
    calendar_events_repo.create(conn, user_id=uid, kind="ferien",
                                title="Herbstferien",
                                start_date="2026-10-19", end_date="2026-10-31")
    page = _open_menu(conn, uid, date(2026, 9, 26))
    assert page._ferien_banner is not None
    assert "Herbstferien" in page._ferien_banner._label.text()


def test_banner_hidden_when_no_vacation(conn):
    uid = users_repo.create_user(conn, name="C")
    page = _open_menu(conn, uid, date(2026, 5, 15))
    assert page._ferien_banner is None


def test_banner_refreshes_on_reload(conn):
    uid = users_repo.create_user(conn, name="C")
    page = _open_menu(conn, uid, date(2026, 5, 15))
    assert page._ferien_banner is None
    calendar_events_repo.create(conn, user_id=uid, kind="ferien",
                                title="Herbstferien",
                                start_date="2026-10-19", end_date="2026-10-31")
    page.reload()
    assert page._ferien_banner is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_menu_page_ferien_banner.py -v`
Expected: FAIL — `MenuPage` does not accept `today` or has no `_ferien_banner`.

- [ ] **Step 3: Wire FerienBanner into MenuPage**

In `src/school_test_engine/ui/pages/menu.py`:

1. Accept an optional `today: date | None = None` kwarg in `__init__` and store it as `self._today_override`.
2. Add `self._ferien_banner: FerienBanner | None = None` and `self._ferien_banner_slot: QVBoxLayout` placed immediately below the greeting label.
3. Add a `_refresh_ferien_banner()` method:

```python
    def _refresh_ferien_banner(self) -> None:
        from ...school_calendar.service import ferien_banner_state
        from ..widgets.ferien_banner import FerienBanner
        # Clear previous banner
        while self._ferien_banner_slot.count():
            item = self._ferien_banner_slot.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._ferien_banner = None

        today = self._today_override or date.today()
        state = ferien_banner_state(self.conn, self.window.active_user_id, today)
        if state.mode == "hidden":
            return
        self._ferien_banner = FerienBanner(state, parent=self,
                                            get_window=lambda: self.window)
        self._ferien_banner_slot.addWidget(self._ferien_banner)
```

4. Call `self._refresh_ferien_banner()` at the end of `reload()`.

5. Make sure `from datetime import date` is imported in `menu.py`.

(Concrete insertion lines depend on the existing structure of `menu.py` — locate the greeting label `_greeting_label` and insert the slot immediately after it.)

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ui/test_menu_page_ferien_banner.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/menu.py tests/ui/test_menu_page_ferien_banner.py
git commit -m "feat(ui/menu): FerienBanner slot below greeting, refresh on reload"
```

---

## Task 17: iCal-Fixture erweitern + E2E

**Files:**
- Modify: `tests/fixtures/schulkalender_mini.ics`
- Create: `tests/test_school_calendar_e2e.py`

- [ ] **Step 1: Extend the fixture**

Append two VEVENTs before `END:VCALENDAR` in `tests/fixtures/schulkalender_mini.ics`:

```ics
BEGIN:VEVENT
DTSTAMP:20260515T080000
DTSTART;VALUE=DATE:20260528
DTEND;VALUE=DATE:20260529
SUMMARY:Pädagogischer Tag
DESCRIPTION:
CATEGORIES:Ferien
UID:20240409T113106-3791@6115.start.schulportal.hessen.de
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20260515T080000
DTSTART;VALUE=DATE:20261019
DTEND;VALUE=DATE:20261101
SUMMARY:Herbstferien
DESCRIPTION:
CATEGORIES:Ferien
UID:20240409T113106-3792@6115.start.schulportal.hessen.de
END:VEVENT
```

- [ ] **Step 2: Verify existing iCal-sync tests still pass after fixture change**

Run: `pytest tests/ical_sync/test_service.py -v`
Expected: still all green. If a test asserts a specific count of skipped/added events, update its expectation to reflect the two new events.

- [ ] **Step 3: Write E2E test**

```python
# tests/test_school_calendar_e2e.py
"""End-to-end: sync iCal fixture → calendar contents → filter toggle → banner."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from school_test_engine.ical_sync import service
from school_test_engine.school_calendar.filters import CalendarFilters
from school_test_engine.school_calendar.service import (
    ferien_banner_state, list_entries,
)
from school_test_engine.storage import run_migrations, users_repo


FIXTURE = Path(__file__).parent / "fixtures" / "schulkalender_mini.ics"


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def test_full_loop_sync_filter_banner(monkeypatch, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://example.com/feed")

    ics_bytes = FIXTURE.read_bytes()
    monkeypatch.setattr(service, "_fetch", lambda url: ics_bytes)
    result = service.sync_feed(conn, uid)
    assert result.error is None
    # Sommerferien + Pädagogischer Tag + Herbstferien + Mathewettbewerb = 4
    assert result.cal_added == 4

    # All filters default-on, future timeframe — today before Herbst, after Sommer.
    f = CalendarFilters.defaults()
    entries = list_entries(conn, uid, date(2026, 9, 1), f)
    titles = {e.title for e in entries}
    assert "Herbstferien" in titles
    assert "Pädagogischer Tag" not in titles   # vergangen → futurefilter strippt

    # Banner countdown to Herbstferien
    state = ferien_banner_state(conn, uid, date(2026, 9, 26))
    assert state.mode == "countdown"
    assert state.vacation_title == "Herbstferien"

    # Toggle Ferien filter off → only events remain
    f2 = f.with_kind_set("ferien", False).with_kind_set("klausur", False)\
          .with_kind_set("frei", False)
    entries2 = list_entries(conn, uid, date(2026, 1, 1), f2)
    assert {e.title for e in entries2} == {"Mathematikwettbewerb Klassenstufe 8"}
```

- [ ] **Step 4: Run E2E**

Run: `pytest tests/test_school_calendar_e2e.py -v`
Expected: 1 passed.

- [ ] **Step 5: Run the entire suite**

Run: `pytest -q`
Expected: all tests green (was 410 → should now be ~460).

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/schulkalender_mini.ics tests/test_school_calendar_e2e.py
git commit -m "test(school_calendar): fixture extension + full-loop e2e"
```

---

## Task 18: Manual Acceptance + QSS Styling

**Files:**
- Modify: `src/school_test_engine/ui/style.qss` (Phase 17 block at the end)

- [ ] **Step 1: Add QSS rules**

Append a Phase-17 block at the end of `src/school_test_engine/ui/style.qss`:

```css
/* === Phase 17: Schulkalender === */
QPushButton#filterChip {
    background: #fffdf8;
    color: #3a2d18;
    border: 1px solid #d8cdb8;
    border-radius: 999px;
    padding: 5px 14px;
    font-size: 10pt;
    min-height: 20px;
}
QPushButton#filterChip:checked {
    background: #e8eddc;
    border-color: #b1c190;
    color: #3e552d;
}
QPushButton#filterChip:hover {
    border-color: #c0b497;
}

QFrame#calendarEntryCard {
    background: #fffdf8;
    border: 1px solid #ecd9bf;
    border-radius: 10px;
}
QLabel#dateBadge {
    color: #57462b;
    font-weight: 600;
}

QFrame#ferienBanner {
    background: #fcf7e8;
    border: 1px solid #ecd9bf;
    border-radius: 10px;
}
QFrame#ferienBannerStrip {
    background: #b1c190;
    border: none;
    border-radius: 2px;
}
```

(Colors taken from the existing Kessler palette referenced throughout `style.qss`.)

- [ ] **Step 2: Manual smoke test**

1. Start the app: `python -m school_test_engine`
2. Pick or create a profile.
3. Open Logo-Menu → click „Schulkalender" → page loads with chips + tabs.
4. Toggle „Frei" off → reload page → chip stays off (persistence works).
5. Switch tab to „Vergangen" → list re-orders.
6. Open Hauptmenü — Ferien-Banner appears beneath greeting if a future vacation is synced.
7. Click banner → routes to SchoolCalendarPage.
8. Verify Phase-7 cockpit (Termine, Noten, Menu KA-Hero) still works — Phase 17 must not regress them.

- [ ] **Step 3: Run full suite one last time**

Run: `pytest -q`
Expected: ~460 passed.

- [ ] **Step 4: Commit QSS + acceptance**

```bash
git add src/school_test_engine/ui/style.qss
git commit -m "style(qss): Phase 17 — filterChip, calendarEntryCard, ferienBanner"
```

---

## Self-Review

**Spec coverage:**
- §5 Datenmodell → Task 1 (migration), Task 8 (dataclasses)
- §6 iCal-Ingest → Task 3 (parser), Task 4 (classifier), Task 7 (service)
- §7.1 calendar_events_repo → Task 5 + Task 6
- §7.2 events_repo.list_for_calendar → Task 9
- §7.3 users_repo erweitert → Task 2
- §8.1 school_calendar.service.list_entries / group_by_month → Task 10
- §8.2 ferien_banner_state → Task 11
- §9.1 SchoolCalendarPage → Task 14
- §9.2 CalendarEntryCard → Task 12
- §9.3 FerienBanner → Task 13
- §9.4 MenuPage-Integration → Task 16
- §9.5 Logo-Menü-Eintrag → Task 15
- §9.6 MainWindow Routing → Task 15
- §10 Filter-Persistenz-Flow → Task 14 (Reentrancy-Guard inside)
- §11 Test-Strategie → wird über Tasks 1-17 abgedeckt
- §12 Akzeptanz-Kriterien → Task 17 (E2E) + Task 18 (manual)

**Type consistency:** `CalendarEntry`, `CalendarFilters`, `FerienBannerState` are imported with consistent names across tasks. Method names `with_kind_set`, `with_timeframe`, `active_kinds`, `from_user_row` match between dataclass (Task 8) and consumers (Task 10, Task 14). `ferien_banner_state` signature `(conn, user_id, today)` matches usage in Task 16.

**Placeholder scan:** No "TBD"/"TODO"/"implement later" remain. The only `...` are inside Python code blocks inside dataclass/method bodies that are fully specified above or below in the same task.

# Phase 7 — Schul-Cockpit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Schul-Cockpit to school-test-engine that tracks upcoming Klassenarbeiten, real school grades (schriftlich/mündlich), and compares app-practice performance to real KA results.

**Architecture:** Two new SQLite tables (`scheduled_events`, `assessments`) added via Migration 006. New domain package `cockpit/` with `service.py` orchestrates events/assessments/attempts repos for cross-cutting queries. Two new UI pages (Termine, Noten) + one adaptive change to the main menu (KA-Heroes replace 2×2 grid when KAs are pending). Existing `attempts` data model is untouched.

**Tech Stack:** Python 3.11, PySide6, SQLite (via stdlib sqlite3), pytest. No new dependencies. Follows existing project conventions (functional repos with `sqlite3.Connection`, pure-SQL migration files, design tokens in `ui/design.py`, Pill/Eyebrow widget primitives).

**Spec reference:** `docs/superpowers/specs/2026-05-12-phase-7-schul-cockpit-design.md`

**Note on commits:** Project is not currently a git repository. If you want the per-task commits below, run `git init && git add . && git commit -m "baseline"` once before starting Task 1. Otherwise treat each `git commit` step as "logical checkpoint" only.

---

## File Structure

**New files:**
- `src/school_test_engine/storage/migrations/006_phase7_cockpit.sql` — schema additions
- `src/school_test_engine/storage/events_repo.py` — CRUD for `scheduled_events`
- `src/school_test_engine/storage/assessments_repo.py` — CRUD for `assessments`
- `src/school_test_engine/cockpit/__init__.py` — package marker (empty)
- `src/school_test_engine/cockpit/service.py` — cross-cutting cockpit queries
- `src/school_test_engine/ui/widgets/grade_pill.py` — circular note display
- `src/school_test_engine/ui/widgets/exam_card.py` — hero KA-card for menu strip
- `src/school_test_engine/ui/widgets/comparison_view.py` — app-vs-real grade comparison block
- `src/school_test_engine/ui/dialogs/__init__.py` — package marker
- `src/school_test_engine/ui/dialogs/event_dialog.py` — KA add/edit dialog
- `src/school_test_engine/ui/dialogs/assessment_dialog.py` — note add/edit dialog
- `src/school_test_engine/ui/pages/events.py` — Termine-Seite
- `src/school_test_engine/ui/pages/grades.py` — Noten-Seite
- `tests/test_migration_006.py`
- `tests/test_events_repo.py`
- `tests/test_assessments_repo.py`
- `tests/test_cockpit_service.py`
- `tests/fixtures/conftest.py` — extension for shared `conn` fixture (if not already present)

**Modified files:**
- `src/school_test_engine/ui/main_window.py` — wire new pages, add navigation methods
- `src/school_test_engine/ui/pages/menu.py` — adaptive layout, top-bar icons
- `src/school_test_engine/ui/style.qss` — add styles for new widgets/cards
- `src/school_test_engine/ui/_subjects.py` — re-export SUBJECTS_ALL (already there); add `KIND_LABELS` for event kinds if useful

---

## Task 1: Migration 006 — schema for scheduled_events + assessments

**Files:**
- Create: `src/school_test_engine/storage/migrations/006_phase7_cockpit.sql`
- Test: `tests/test_migration_006.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_migration_006.py
import pytest

from school_test_engine.storage import connect, run_migrations


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_scheduled_events_table_exists(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_events'"
    )
    assert cur.fetchone() is not None


def test_assessments_table_exists(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='assessments'"
    )
    assert cur.fetchone() is not None


def test_assessments_event_fk_set_null_on_event_delete(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (2, 'Test', '👤', 1, '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO scheduled_events (id, user_id, subject, kind, event_date, topics) "
        "VALUES (10, 2, 'Mathe', 'klassenarbeit', '2026-05-15', '[]')"
    )
    conn.execute(
        "INSERT INTO assessments "
        "(id, user_id, subject, category, assessment_date, grade, scheduled_event_id) "
        "VALUES (100, 2, 'Mathe', 'schriftlich', '2026-05-15', 2.0, 10)"
    )
    conn.commit()
    conn.execute("DELETE FROM scheduled_events WHERE id = 10")
    conn.commit()
    row = conn.execute("SELECT scheduled_event_id FROM assessments WHERE id = 100").fetchone()
    assert row["scheduled_event_id"] is None


def test_cascade_on_user_delete_assessments_and_events(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (2, 'Test', '👤', 1, '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO scheduled_events (user_id, subject, kind, event_date, topics) "
        "VALUES (2, 'Mathe', 'klassenarbeit', '2026-05-15', '[]')"
    )
    conn.execute(
        "INSERT INTO assessments (user_id, subject, category, assessment_date, grade) "
        "VALUES (2, 'Mathe', 'schriftlich', '2026-05-15', 2.0)"
    )
    conn.commit()
    conn.execute("DELETE FROM users WHERE id = 2")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM scheduled_events WHERE user_id = 2").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM assessments WHERE user_id = 2").fetchone()[0] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_006.py -v`
Expected: FAIL with "no such table: scheduled_events".

- [ ] **Step 3: Write migration SQL**

Create `src/school_test_engine/storage/migrations/006_phase7_cockpit.sql`:

```sql
-- Phase 7: Schul-Cockpit — Termine + echte Noten

CREATE TABLE IF NOT EXISTS scheduled_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject     TEXT    NOT NULL,
    kind        TEXT    NOT NULL CHECK (kind IN ('klassenarbeit','klausur','test','sonstiges')),
    event_date  TEXT    NOT NULL,
    topics      TEXT    NOT NULL DEFAULT '[]',
    note        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scheduled_user_date
    ON scheduled_events(user_id, event_date);

CREATE TABLE IF NOT EXISTS assessments (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject            TEXT    NOT NULL,
    category           TEXT    NOT NULL CHECK (category IN ('schriftlich','muendlich','sonstige')),
    assessment_date    TEXT    NOT NULL,
    grade              REAL    NOT NULL,
    points             REAL,
    max_points         REAL,
    note               TEXT,
    scheduled_event_id INTEGER REFERENCES scheduled_events(id) ON DELETE SET NULL,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_assessments_user_subject
    ON assessments(user_id, subject);
CREATE INDEX IF NOT EXISTS idx_assessments_event
    ON assessments(scheduled_event_id);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migration_006.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/migrations/006_phase7_cockpit.sql tests/test_migration_006.py
git commit -m "feat(phase7): migration 006 — scheduled_events + assessments tables"
```

---

## Task 2: events_repo — CRUD for scheduled_events

**Files:**
- Create: `src/school_test_engine/storage/events_repo.py`
- Test: `tests/test_events_repo.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_events_repo.py
import pytest

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import events_repo


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, "Clemens", "🧒")


def test_create_minimal(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=["Funktionen"])
    row = events_repo.get(conn, eid)
    assert row["subject"] == "Mathe"
    assert row["kind"] == "klassenarbeit"
    assert row["event_date"] == "2026-05-20"


def test_create_topics_stored_as_json(conn, uid):
    eid = events_repo.create(conn, uid, "Bio", "klassenarbeit", "2026-06-01", topics=["Zellbiologie", "Genetik"])
    row = events_repo.get(conn, eid)
    import json
    assert json.loads(row["topics"]) == ["Zellbiologie", "Genetik"]


def test_list_upcoming_filters_past_events(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-04-01", topics=[])  # past
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-01", topics=[])  # future
    upcoming = events_repo.list_upcoming(conn, uid, today="2026-05-12", limit=3)
    assert len(upcoming) == 1
    assert upcoming[0]["event_date"] == "2026-06-01"


def test_list_upcoming_sorted_ascending(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-15", topics=[])
    events_repo.create(conn, uid, "Englisch", "klassenarbeit", "2026-05-20", topics=[])
    upcoming = events_repo.list_upcoming(conn, uid, today="2026-05-12", limit=3)
    assert [r["event_date"] for r in upcoming] == ["2026-05-20", "2026-06-15"]


def test_list_upcoming_respects_limit(conn, uid):
    for i in range(5):
        events_repo.create(conn, uid, "Mathe", "klassenarbeit", f"2026-06-{i+1:02d}", topics=[])
    upcoming = events_repo.list_upcoming(conn, uid, today="2026-05-12", limit=3)
    assert len(upcoming) == 3


def test_list_all_includes_past(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-01-15", topics=[])
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-15", topics=[])
    all_events = events_repo.list_all(conn, uid)
    assert len(all_events) == 2


def test_update_changes_fields(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=["A"])
    events_repo.update(conn, eid, event_date="2026-05-27", topics=["B", "C"], note="Verschoben")
    row = events_repo.get(conn, eid)
    assert row["event_date"] == "2026-05-27"
    assert row["note"] == "Verschoben"
    import json
    assert json.loads(row["topics"]) == ["B", "C"]


def test_delete_removes_row(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=[])
    events_repo.delete(conn, eid)
    assert events_repo.get(conn, eid) is None


def test_user_isolation(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    events_repo.create(conn, a, "Mathe", "klassenarbeit", "2026-06-01", topics=[])
    assert len(events_repo.list_all(conn, a)) == 1
    assert len(events_repo.list_all(conn, b)) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events_repo.py -v`
Expected: All FAIL with "No module named 'school_test_engine.storage.events_repo'".

- [ ] **Step 3: Write the repo module**

Create `src/school_test_engine/storage/events_repo.py`:

```python
from __future__ import annotations

import json
import sqlite3
from typing import Iterable


def create(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str,
    kind: str,
    event_date: str,
    *,
    topics: Iterable[str] | None = None,
    note: str | None = None,
) -> int:
    topics_json = json.dumps(list(topics) if topics else [])
    cur = conn.execute(
        """
        INSERT INTO scheduled_events (user_id, subject, kind, event_date, topics, note)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, subject, kind, event_date, topics_json, note),
    )
    conn.commit()
    eid = cur.lastrowid
    assert eid is not None
    return eid


def get(conn: sqlite3.Connection, event_id: int) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM scheduled_events WHERE id = ?", (event_id,))
    return cur.fetchone()


def list_upcoming(
    conn: sqlite3.Connection, user_id: int, today: str, limit: int = 3
) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM scheduled_events
        WHERE user_id = ? AND event_date >= ?
        ORDER BY event_date ASC, created_at ASC
        LIMIT ?
        """,
        (user_id, today, limit),
    )
    return cur.fetchall()


def list_all(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM scheduled_events
        WHERE user_id = ?
        ORDER BY event_date DESC, created_at DESC
        """,
        (user_id,),
    )
    return cur.fetchall()


_SENTINEL = object()


def update(
    conn: sqlite3.Connection,
    event_id: int,
    *,
    subject: str | None = None,
    kind: str | None = None,
    event_date: str | None = None,
    topics: Iterable[str] | None = _SENTINEL,  # type: ignore[assignment]
    note=_SENTINEL,
) -> None:
    fields: list[str] = []
    values: list = []
    if subject is not None:
        fields.append("subject = ?"); values.append(subject)
    if kind is not None:
        fields.append("kind = ?"); values.append(kind)
    if event_date is not None:
        fields.append("event_date = ?"); values.append(event_date)
    if topics is not _SENTINEL:
        fields.append("topics = ?"); values.append(json.dumps(list(topics or [])))
    if note is not _SENTINEL:
        fields.append("note = ?"); values.append(note)
    if not fields:
        return
    values.append(event_id)
    conn.execute(f"UPDATE scheduled_events SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()


def delete(conn: sqlite3.Connection, event_id: int) -> None:
    conn.execute("DELETE FROM scheduled_events WHERE id = ?", (event_id,))
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_events_repo.py -v`
Expected: All PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/events_repo.py tests/test_events_repo.py
git commit -m "feat(phase7): events_repo CRUD for scheduled_events"
```

---

## Task 3: assessments_repo — CRUD for assessments

**Files:**
- Create: `src/school_test_engine/storage/assessments_repo.py`
- Test: `tests/test_assessments_repo.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_assessments_repo.py
import pytest

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import assessments_repo, events_repo


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, "Clemens", "🧒")


def test_create_minimal(conn, uid):
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0)
    row = assessments_repo.get(conn, aid)
    assert row["subject"] == "Mathe"
    assert row["grade"] == 2.0
    assert row["scheduled_event_id"] is None


def test_create_with_event_link(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0, scheduled_event_id=eid)
    row = assessments_repo.get(conn, aid)
    assert row["scheduled_event_id"] == eid


def test_list_by_subject(conn, uid):
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0)
    assessments_repo.create(conn, uid, "Englisch", "schriftlich", "2026-05-22", grade=3.0)
    assessments_repo.create(conn, uid, "Mathe", "muendlich", "2026-04-01", grade=2.5)
    rows = assessments_repo.list_by_subject(conn, uid, "Mathe")
    assert len(rows) == 2
    # newest first
    assert rows[0]["assessment_date"] == "2026-05-20"


def test_list_all_chronological_desc(conn, uid):
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0)
    assessments_repo.create(conn, uid, "Bio", "muendlich", "2026-04-01", grade=2.5)
    rows = assessments_repo.list_all(conn, uid)
    assert [r["assessment_date"] for r in rows] == ["2026-05-20", "2026-04-01"]


def test_find_by_event(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0, scheduled_event_id=eid)
    row = assessments_repo.find_by_event(conn, eid)
    assert row is not None
    assert row["id"] == aid


def test_find_by_event_returns_none_if_no_link(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=[])
    assert assessments_repo.find_by_event(conn, eid) is None


def test_update_changes_fields(conn, uid):
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=3.0)
    assessments_repo.update(conn, aid, grade=2.5, note="korrigiert")
    row = assessments_repo.get(conn, aid)
    assert row["grade"] == 2.5
    assert row["note"] == "korrigiert"


def test_delete_removes_row(conn, uid):
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0)
    assessments_repo.delete(conn, aid)
    assert assessments_repo.get(conn, aid) is None


def test_points_optional(conn, uid):
    aid = assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", "2026-05-20",
        grade=2.0, points=38, max_points=50, note="gut"
    )
    row = assessments_repo.get(conn, aid)
    assert row["points"] == 38
    assert row["max_points"] == 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_assessments_repo.py -v`
Expected: All FAIL with import error.

- [ ] **Step 3: Write the repo module**

Create `src/school_test_engine/storage/assessments_repo.py`:

```python
from __future__ import annotations

import sqlite3


def create(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str,
    category: str,
    assessment_date: str,
    *,
    grade: float,
    points: float | None = None,
    max_points: float | None = None,
    note: str | None = None,
    scheduled_event_id: int | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO assessments
            (user_id, subject, category, assessment_date,
             grade, points, max_points, note, scheduled_event_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, subject, category, assessment_date,
         grade, points, max_points, note, scheduled_event_id),
    )
    conn.commit()
    aid = cur.lastrowid
    assert aid is not None
    return aid


def get(conn: sqlite3.Connection, assessment_id: int) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM assessments WHERE id = ?", (assessment_id,))
    return cur.fetchone()


def list_by_subject(
    conn: sqlite3.Connection, user_id: int, subject: str
) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM assessments
        WHERE user_id = ? AND subject = ?
        ORDER BY assessment_date DESC, created_at DESC
        """,
        (user_id, subject),
    )
    return cur.fetchall()


def list_all(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM assessments
        WHERE user_id = ?
        ORDER BY assessment_date DESC, created_at DESC
        """,
        (user_id,),
    )
    return cur.fetchall()


def find_by_event(conn: sqlite3.Connection, event_id: int) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT * FROM assessments WHERE scheduled_event_id = ? "
        "ORDER BY created_at ASC LIMIT 1",
        (event_id,),
    )
    return cur.fetchone()


_SENTINEL = object()


def update(
    conn: sqlite3.Connection,
    assessment_id: int,
    *,
    subject: str | None = None,
    category: str | None = None,
    assessment_date: str | None = None,
    grade: float | None = None,
    points=_SENTINEL,
    max_points=_SENTINEL,
    note=_SENTINEL,
    scheduled_event_id=_SENTINEL,
) -> None:
    fields: list[str] = []
    values: list = []
    if subject is not None:
        fields.append("subject = ?"); values.append(subject)
    if category is not None:
        fields.append("category = ?"); values.append(category)
    if assessment_date is not None:
        fields.append("assessment_date = ?"); values.append(assessment_date)
    if grade is not None:
        fields.append("grade = ?"); values.append(grade)
    if points is not _SENTINEL:
        fields.append("points = ?"); values.append(points)
    if max_points is not _SENTINEL:
        fields.append("max_points = ?"); values.append(max_points)
    if note is not _SENTINEL:
        fields.append("note = ?"); values.append(note)
    if scheduled_event_id is not _SENTINEL:
        fields.append("scheduled_event_id = ?"); values.append(scheduled_event_id)
    if not fields:
        return
    values.append(assessment_id)
    conn.execute(f"UPDATE assessments SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()


def delete(conn: sqlite3.Connection, assessment_id: int) -> None:
    conn.execute("DELETE FROM assessments WHERE id = ?", (assessment_id,))
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_assessments_repo.py -v`
Expected: All PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/assessments_repo.py tests/test_assessments_repo.py
git commit -m "feat(phase7): assessments_repo CRUD"
```

---

## Task 4: cockpit/service.py — upcoming_events_for_menu

**Files:**
- Create: `src/school_test_engine/cockpit/__init__.py` (empty)
- Create: `src/school_test_engine/cockpit/service.py`
- Test: `tests/test_cockpit_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cockpit_service.py`:

```python
import json
import pytest
from datetime import date

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import events_repo, assessments_repo
from school_test_engine.cockpit import service as cockpit


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, "Clemens", "🧒")


def test_upcoming_events_for_menu_returns_pending(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=["Funktionen"])
    events_repo.create(conn, uid, "Englisch", "klassenarbeit", "2026-06-01", topics=["Vocab U5"])
    result = cockpit.upcoming_events_for_menu(conn, uid, today=date(2026, 5, 12))
    assert len(result) == 2
    assert result[0].subject == "Mathe"
    assert result[0].days_until == 8
    assert result[0].topics == ["Funktionen"]
    assert result[0].linked_assessment_id is None


def test_upcoming_events_for_menu_marks_linked_assessment(conn, uid):
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-20", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-20", grade=2.0, scheduled_event_id=eid)
    result = cockpit.upcoming_events_for_menu(conn, uid, today=date(2026, 5, 12))
    assert result[0].linked_assessment_id == aid


def test_upcoming_events_for_menu_excludes_past(conn, uid):
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-04-01", topics=[])
    result = cockpit.upcoming_events_for_menu(conn, uid, today=date(2026, 5, 12))
    assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cockpit_service.py -v`
Expected: FAIL with import error.

- [ ] **Step 3: Write service module**

Create `src/school_test_engine/cockpit/__init__.py`:

```python
```

Create `src/school_test_engine/cockpit/service.py`:

```python
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class EventCardData:
    event_id: int
    subject: str
    kind: str
    event_date: str            # ISO YYYY-MM-DD
    days_until: int            # negative if event_date in past
    topics: list[str]
    note: str | None
    linked_assessment_id: int | None


def upcoming_events_for_menu(
    conn: sqlite3.Connection, user_id: int, today: date, limit: int = 3
) -> list[EventCardData]:
    today_iso = today.isoformat()
    cur = conn.execute(
        """
        SELECT e.*, a.id AS assessment_id
        FROM scheduled_events e
        LEFT JOIN assessments a ON a.scheduled_event_id = e.id
        WHERE e.user_id = ? AND e.event_date >= ?
        ORDER BY e.event_date ASC, e.created_at ASC
        LIMIT ?
        """,
        (user_id, today_iso, limit),
    )
    out: list[EventCardData] = []
    for row in cur.fetchall():
        event_d = datetime.fromisoformat(row["event_date"]).date()
        days = (event_d - today).days
        out.append(EventCardData(
            event_id=row["id"],
            subject=row["subject"],
            kind=row["kind"],
            event_date=row["event_date"],
            days_until=days,
            topics=json.loads(row["topics"] or "[]"),
            note=row["note"],
            linked_assessment_id=row["assessment_id"],
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cockpit_service.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/cockpit/ tests/test_cockpit_service.py
git commit -m "feat(phase7): cockpit.upcoming_events_for_menu"
```

---

## Task 5: cockpit.comparison_for_assessment

**Files:**
- Modify: `src/school_test_engine/cockpit/service.py`
- Test: append to `tests/test_cockpit_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cockpit_service.py`:

```python
from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import attempts_repo
from pathlib import Path


def _seed_test_and_attempt(conn, user_id, subject, finished_at, note_value):
    """Helper: import a test for `subject`, create one finished attempt with given note."""
    # Build a minimal test JSON inline rather than relying on file
    payload = (
        '{"title":"x","subject":"' + subject + '","points_total":10,'
        '"notenschluessel":{"1":[100,90],"2":[89,75],"3":[74,60],"4":[59,45],"5":[44,20],"6":[19,0]},'
        '"questions":[{"id":"q1","type":"single","topic":"t","points":10,"prompt":"p","choices":[{"id":"a","text":"a"}],"answer":"a"}]}'
    )
    test_id = import_from_string(conn, payload, user_id=user_id)
    aid = attempts_repo.start_attempt(conn, test_id, 10, user_id)
    attempts_repo.finish_attempt(conn, aid, points_earned=10, percent=100, note=note_value)
    conn.execute("UPDATE attempts SET finished_at = ? WHERE id = ?", (finished_at, aid))
    conn.commit()
    return test_id, aid


def test_comparison_uses_attempts_between_prev_ka_and_this_ka(conn, uid):
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-03-01T10:00:00Z", note_value=3)  # before prev KA
    prev_eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-04-01", topics=[])
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-04-01", grade=3.0, scheduled_event_id=prev_eid)
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-04-15T10:00:00Z", note_value=2)  # in window
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-05-01T10:00:00Z", note_value=2)  # in window
    this_eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-15", topics=[])
    this_aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-15", grade=2.0, scheduled_event_id=this_eid)

    cmp = cockpit.comparison_for_assessment(conn, this_aid)
    assert cmp is not None
    assert cmp.attempts_count == 2
    assert cmp.attempts_grade_avg == pytest.approx(2.0)
    assert cmp.real_grade == 2.0
    assert cmp.delta_label == "App-Übungen und echte KA waren sehr ähnlich"


def test_comparison_first_ka_uses_all_attempts_before(conn, uid):
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-03-01T10:00:00Z", note_value=2)
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-04-01T10:00:00Z", note_value=2)
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-15", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-15", grade=3.0, scheduled_event_id=eid)
    cmp = cockpit.comparison_for_assessment(conn, aid)
    assert cmp is not None
    assert cmp.attempts_count == 2
    assert cmp.delta_label.startswith("Du warst in der KA schlechter")


def test_comparison_filters_by_subject(conn, uid):
    _seed_test_and_attempt(conn, uid, "Englisch", "2026-04-15T10:00:00Z", note_value=1)
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-15", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-15", grade=2.0, scheduled_event_id=eid)
    cmp = cockpit.comparison_for_assessment(conn, aid)
    assert cmp is None  # no Mathe attempts in window


def test_comparison_none_for_unlinked_assessment(conn, uid):
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-15", grade=2.0)
    assert cockpit.comparison_for_assessment(conn, aid) is None


def test_comparison_app_better_label(conn, uid):
    _seed_test_and_attempt(conn, uid, "Mathe", "2026-05-01T10:00:00Z", note_value=4)
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-05-15", topics=[])
    aid = assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-15", grade=2.0, scheduled_event_id=eid)
    cmp = cockpit.comparison_for_assessment(conn, aid)
    assert cmp.delta_label.startswith("Du warst in der KA besser")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cockpit_service.py -v -k comparison`
Expected: 5 FAIL with AttributeError.

- [ ] **Step 3: Append to `cockpit/service.py`**

Add to `src/school_test_engine/cockpit/service.py`:

```python
@dataclass(frozen=True)
class ComparisonData:
    assessment_id: int
    subject: str
    attempts_count: int
    attempts_grade_avg: float
    real_grade: float
    delta: float          # real - app_avg (positive = app was easier, KA worse)
    delta_label: str


_LABEL_BETTER = "Du warst in der KA besser als in App-Übungen ↑"
_LABEL_WORSE = "Du warst in der KA schlechter als in App-Übungen ↓"
_LABEL_SIMILAR = "App-Übungen und echte KA waren sehr ähnlich"


def _delta_label(delta: float) -> str:
    if delta < -0.2:
        return _LABEL_BETTER
    if delta > 0.2:
        return _LABEL_WORSE
    return _LABEL_SIMILAR


def comparison_for_assessment(
    conn: sqlite3.Connection, assessment_id: int
) -> ComparisonData | None:
    """Compute app-practice vs real grade comparison for one assessment.

    Window: attempts in the same subject finished between the previous
    scheduled_event (same subject) and this assessment's event_date.
    If no previous event: all attempts up to event_date.
    Returns None if the assessment has no scheduled_event_id or no
    matching attempts in the window.
    """
    a = conn.execute(
        "SELECT * FROM assessments WHERE id = ?", (assessment_id,)
    ).fetchone()
    if a is None or a["scheduled_event_id"] is None:
        return None
    event = conn.execute(
        "SELECT * FROM scheduled_events WHERE id = ?", (a["scheduled_event_id"],)
    ).fetchone()
    if event is None:
        return None

    # Find previous event of same subject for the same user
    prev = conn.execute(
        """
        SELECT MAX(event_date) AS prev_date
        FROM scheduled_events
        WHERE user_id = ? AND subject = ? AND event_date < ?
        """,
        (a["user_id"], a["subject"], event["event_date"]),
    ).fetchone()
    prev_date = prev["prev_date"] if prev else None

    # Find attempts in window
    if prev_date is None:
        cur = conn.execute(
            """
            SELECT AVG(att.note) AS avg_note, COUNT(*) AS n
            FROM attempts att
            JOIN tests t ON t.id = att.test_id
            WHERE att.user_id = ?
              AND att.completed = 1
              AND t.subject = ?
              AND date(att.finished_at) <= ?
            """,
            (a["user_id"], a["subject"], event["event_date"]),
        )
    else:
        cur = conn.execute(
            """
            SELECT AVG(att.note) AS avg_note, COUNT(*) AS n
            FROM attempts att
            JOIN tests t ON t.id = att.test_id
            WHERE att.user_id = ?
              AND att.completed = 1
              AND t.subject = ?
              AND date(att.finished_at) > ?
              AND date(att.finished_at) <= ?
            """,
            (a["user_id"], a["subject"], prev_date, event["event_date"]),
        )
    row = cur.fetchone()
    n = int(row["n"] or 0)
    if n == 0:
        return None
    app_avg = float(row["avg_note"])
    real = float(a["grade"])
    delta = round(real - app_avg, 2)
    return ComparisonData(
        assessment_id=assessment_id,
        subject=a["subject"],
        attempts_count=n,
        attempts_grade_avg=round(app_avg, 2),
        real_grade=real,
        delta=delta,
        delta_label=_delta_label(delta),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cockpit_service.py -v`
Expected: All PASS (8 tests, 3 from previous task + 5 new).

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/cockpit/service.py tests/test_cockpit_service.py
git commit -m "feat(phase7): cockpit.comparison_for_assessment with windowed attempt avg"
```

---

## Task 6: cockpit.subject_grade_average + aggregate_comparison

**Files:**
- Modify: `src/school_test_engine/cockpit/service.py`
- Test: append to `tests/test_cockpit_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cockpit_service.py`:

```python
def test_subject_grade_average_both_categories(conn, uid):
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-04-01", grade=2.0)
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-05-01", grade=3.0)
    assessments_repo.create(conn, uid, "Mathe", "muendlich", "2026-04-15", grade=2.0)
    avg = cockpit.subject_grade_average(conn, uid, "Mathe")
    assert avg.schriftlich_avg == 2.5
    assert avg.muendlich_avg == 2.0
    assert avg.zeugnis_estimate == pytest.approx(2.25)


def test_subject_grade_average_only_schriftlich(conn, uid):
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-04-01", grade=2.0)
    avg = cockpit.subject_grade_average(conn, uid, "Mathe")
    assert avg.schriftlich_avg == 2.0
    assert avg.muendlich_avg is None
    assert avg.zeugnis_estimate == 2.0


def test_subject_grade_average_empty(conn, uid):
    avg = cockpit.subject_grade_average(conn, uid, "Mathe")
    assert avg.schriftlich_avg is None
    assert avg.muendlich_avg is None
    assert avg.zeugnis_estimate is None


def test_aggregate_comparison_needs_three_or_more(conn, uid):
    # only 2 comparable assessments → None
    for i, d in enumerate(["2026-03-15", "2026-04-15"]):
        _seed_test_and_attempt(conn, uid, "Mathe", f"2026-0{2+i}-25T10:00:00Z", note_value=2)
        eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", d, topics=[])
        assessments_repo.create(conn, uid, "Mathe", "schriftlich", d, grade=2.0, scheduled_event_id=eid)
    assert cockpit.aggregate_comparison(conn, uid) is None


def test_aggregate_comparison_returns_mean_delta(conn, uid):
    dates = ["2026-02-15", "2026-03-15", "2026-04-15"]
    for i, d in enumerate(dates):
        _seed_test_and_attempt(conn, uid, "Mathe", f"2026-0{1+i}-25T10:00:00Z", note_value=3)
        eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", d, topics=[])
        assessments_repo.create(conn, uid, "Mathe", "schriftlich", d, grade=2.0, scheduled_event_id=eid)
    agg = cockpit.aggregate_comparison(conn, uid)
    assert agg is not None
    assert agg.count == 3
    assert agg.avg_delta == pytest.approx(-1.0)  # real 2 - app 3 = -1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cockpit_service.py -v -k "grade_average or aggregate"`
Expected: 5 FAIL.

- [ ] **Step 3: Append to `cockpit/service.py`**

```python
@dataclass(frozen=True)
class SubjectAverage:
    subject: str
    schriftlich_avg: float | None
    muendlich_avg: float | None
    zeugnis_estimate: float | None


def subject_grade_average(
    conn: sqlite3.Connection, user_id: int, subject: str
) -> SubjectAverage:
    def _avg(category: str) -> float | None:
        row = conn.execute(
            "SELECT AVG(grade) AS a, COUNT(*) AS n FROM assessments "
            "WHERE user_id = ? AND subject = ? AND category = ?",
            (user_id, subject, category),
        ).fetchone()
        if not row or (row["n"] or 0) == 0:
            return None
        return round(float(row["a"]), 2)

    s = _avg("schriftlich")
    m = _avg("muendlich")
    if s is not None and m is not None:
        z = round(0.5 * s + 0.5 * m, 2)
    elif s is not None:
        z = s
    elif m is not None:
        z = m
    else:
        z = None
    return SubjectAverage(subject=subject, schriftlich_avg=s, muendlich_avg=m, zeugnis_estimate=z)


@dataclass(frozen=True)
class AggregateComparison:
    count: int
    avg_delta: float
    label: str


def aggregate_comparison(
    conn: sqlite3.Connection, user_id: int
) -> AggregateComparison | None:
    rows = conn.execute(
        "SELECT id FROM assessments "
        "WHERE user_id = ? AND scheduled_event_id IS NOT NULL",
        (user_id,),
    ).fetchall()
    deltas: list[float] = []
    for r in rows:
        cmp = comparison_for_assessment(conn, r["id"])
        if cmp is not None:
            deltas.append(cmp.delta)
    if len(deltas) < 3:
        return None
    mean = sum(deltas) / len(deltas)
    avg_delta = round(mean, 2)
    if avg_delta < -0.05:
        label = f"Bei deinen letzten {len(deltas)} Klassenarbeiten lag dein App-Übungs-Schnitt im Schnitt {abs(avg_delta):.1f} Noten schlechter als die echte Note."
    elif avg_delta > 0.05:
        label = f"Bei deinen letzten {len(deltas)} Klassenarbeiten lag dein App-Übungs-Schnitt im Schnitt {abs(avg_delta):.1f} Noten besser als die echte Note."
    else:
        label = f"Bei deinen letzten {len(deltas)} Klassenarbeiten lag dein App-Übungs-Schnitt sehr nah an der echten Note."
    return AggregateComparison(count=len(deltas), avg_delta=avg_delta, label=label)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cockpit_service.py -v`
Expected: All PASS (13 total).

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/cockpit/service.py tests/test_cockpit_service.py
git commit -m "feat(phase7): cockpit.subject_grade_average + aggregate_comparison"
```

---

## Task 7: GradePill widget

**Files:**
- Create: `src/school_test_engine/ui/widgets/grade_pill.py`

- [ ] **Step 1: Write the widget**

Create `src/school_test_engine/ui/widgets/grade_pill.py`:

```python
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from .._subjects import note_color


def GradePill(grade: float, *, size: int = 56, parent=None) -> QLabel:
    """Circular note display. Color follows _subjects.note_color() based on rounded grade.

    `grade` may be fractional (e.g. 2.5). Display formats:
      - whole number: "2"
      - half step:   "2,5" (German comma)
    """
    rounded = max(1, min(6, int(round(grade))))
    bg = note_color(rounded)
    if abs(grade - int(grade)) < 0.01:
        text = str(int(grade))
    else:
        text = f"{grade:.1f}".replace(".", ",")
    lbl = QLabel(text, parent)
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"background: {bg}; color: #f6f1e6; "
        f"font-family: 'Fraunces'; font-size: {int(size * 0.45)}pt; "
        f"font-weight: 500; border-radius: {size // 2}px;"
    )
    return lbl
```

- [ ] **Step 2: Smoke test by importing**

Run: `python -c "from PySide6.QtWidgets import QApplication; app = QApplication([]); from school_test_engine.ui.widgets.grade_pill import GradePill; p = GradePill(2.5); print('ok size=', p.size())"`
Expected: prints `ok size= PySide6.QtCore.QSize(56, 56)` (no exception).

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/widgets/grade_pill.py
git commit -m "feat(phase7): GradePill widget — circular note display"
```

---

## Task 8: ExamCard widget — hero KA card for menu strip

**Files:**
- Create: `src/school_test_engine/ui/widgets/exam_card.py`

- [ ] **Step 1: Write the widget**

Create `src/school_test_engine/ui/widgets/exam_card.py`:

```python
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..design import Color, FontFamily, Semantic
from .clickable_card import ClickableCard
from .pill import Pill
from .._subjects import subject_variant


def _countdown_text(days_until: int) -> str:
    if days_until < 0:
        return f"vor {abs(days_until)} Tagen"
    if days_until == 0:
        return "heute"
    if days_until == 1:
        return "morgen"
    return f"in {days_until} Tagen"


def _countdown_variant(days_until: int) -> str:
    # rose for "urgent" (<= 3 days), honey for soon (<= 7), paper otherwise; past = paper dimmed
    if days_until < 0:
        return "paper"
    if days_until <= 3:
        return "rose"
    if days_until <= 7:
        return "honey"
    return "tea"


class ExamCard(ClickableCard):
    """Hero KA card. Click opens detail dialog (handled by parent via clicked signal)."""

    practice_clicked = Signal(int)   # emits event_id (Phase 8 will hook up)
    enter_grade_clicked = Signal(int)
    edit_clicked = Signal(int)

    def __init__(self, event_data, parent=None):
        super().__init__(object_name="examCard", parent=parent)
        self.event_id = event_data.event_id
        self.setMinimumSize(260, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)

        # Top row: subject pill + countdown pill
        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(Pill(event_data.subject.upper(), subject_variant(event_data.subject)))
        top.addWidget(Pill(_countdown_text(event_data.days_until), _countdown_variant(event_data.days_until)))
        top.addStretch(1)
        layout.addLayout(top)

        # Title: kind label
        kind_label = {
            "klassenarbeit": "Klassenarbeit",
            "klausur": "Klausur",
            "test": "Test",
            "sonstiges": "Termin",
        }.get(event_data.kind, "Termin")
        title = QLabel(kind_label)
        title.setObjectName("h2")
        title.setFont(QFont(FontFamily.DISPLAY, 16, QFont.Weight.Medium))
        title.setStyleSheet(f"color: {Semantic.FG};")
        layout.addWidget(title)

        # Topics (up to 3 lines)
        topics_text = "\n".join(f"· {t}" for t in event_data.topics[:3]) if event_data.topics else "Keine Themen erfasst"
        topics = QLabel(topics_text)
        topics.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
        topics.setWordWrap(True)
        layout.addWidget(topics)

        layout.addStretch(1)

        # Bottom row: actions
        actions = QHBoxLayout()
        actions.setSpacing(8)
        if event_data.linked_assessment_id is None:
            grade_btn = QPushButton("Note eintragen")
            grade_btn.setObjectName("primary")
            grade_btn.clicked.connect(lambda: self.enter_grade_clicked.emit(self.event_id))
            actions.addWidget(grade_btn)
        else:
            done = Pill("Note erfasst ✓", "tea")
            actions.addWidget(done)
        actions.addStretch(1)
        edit = QPushButton("…")
        edit.setObjectName("text")
        edit.setFixedWidth(36)
        edit.clicked.connect(lambda: self.edit_clicked.emit(self.event_id))
        actions.addWidget(edit)
        layout.addLayout(actions)
```

- [ ] **Step 2: Smoke test by importing**

Run: `python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.cockpit.service import EventCardData
from school_test_engine.ui.widgets.exam_card import ExamCard
d = EventCardData(1, 'Mathe', 'klassenarbeit', '2026-05-20', 3, ['Funktionen', 'Gleichungen'], None, None)
c = ExamCard(d)
print('ok')"`
Expected: prints `ok` (no exception).

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/widgets/exam_card.py
git commit -m "feat(phase7): ExamCard widget — hero KA card with countdown + actions"
```

---

## Task 9: ComparisonView widget

**Files:**
- Create: `src/school_test_engine/ui/widgets/comparison_view.py`

- [ ] **Step 1: Write the widget**

Create `src/school_test_engine/ui/widgets/comparison_view.py`:

```python
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..design import Color, FontFamily, Semantic
from .grade_pill import GradePill


class ComparisonView(QFrame):
    """Shows app-practice average vs. real grade for one assessment."""

    def __init__(self, comparison_data, parent=None):
        super().__init__(parent)
        self.setObjectName("comparisonCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 16)
        outer.setSpacing(10)

        eyebrow = QLabel("VERGLEICH")
        eyebrow.setObjectName("eyebrow")
        outer.addWidget(eyebrow)

        row = QHBoxLayout()
        row.setSpacing(20)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        app_col = QVBoxLayout()
        app_col.setSpacing(4)
        app_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_col.addWidget(GradePill(comparison_data.attempts_grade_avg, size=56), alignment=Qt.AlignmentFlag.AlignCenter)
        app_label = QLabel(f"App-Übungen\n({comparison_data.attempts_count})")
        app_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_label.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 9pt;")
        app_col.addWidget(app_label)
        row.addLayout(app_col)

        arrow = QLabel("→")
        arrow.setStyleSheet(f"color: {Semantic.ACCENT}; font-size: 22pt;")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(arrow)

        real_col = QVBoxLayout()
        real_col.setSpacing(4)
        real_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        real_col.addWidget(GradePill(comparison_data.real_grade, size=72), alignment=Qt.AlignmentFlag.AlignCenter)
        real_label = QLabel("echte Note")
        real_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        real_label.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 9pt;")
        real_col.addWidget(real_label)
        row.addLayout(real_col)
        row.addStretch(1)

        outer.addLayout(row)

        delta_lbl = QLabel(comparison_data.delta_label)
        delta_lbl.setFont(QFont(FontFamily.DISPLAY, 12, QFont.Weight.Normal))
        delta_lbl.setStyleSheet(f"color: {Semantic.FG};")
        delta_lbl.setWordWrap(True)
        outer.addWidget(delta_lbl)
```

- [ ] **Step 2: Smoke test by importing**

Run: `python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.cockpit.service import ComparisonData
from school_test_engine.ui.widgets.comparison_view import ComparisonView
d = ComparisonData(1, 'Mathe', 3, 2.4, 2.0, -0.4, 'Du warst in der KA besser als in App-Übungen ↑')
v = ComparisonView(d)
print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/widgets/comparison_view.py
git commit -m "feat(phase7): ComparisonView widget — app vs real grade block"
```

---

## Task 10: EventDialog — add/edit KA

**Files:**
- Create: `src/school_test_engine/ui/dialogs/__init__.py` (empty)
- Create: `src/school_test_engine/ui/dialogs/event_dialog.py`

- [ ] **Step 1: Write the dialog**

Create `src/school_test_engine/ui/dialogs/__init__.py` (empty).

Create `src/school_test_engine/ui/dialogs/event_dialog.py`:

```python
from __future__ import annotations

import json
from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from .._subjects import SUBJECTS_ALL


KIND_LABELS = [
    ("klassenarbeit", "Klassenarbeit"),
    ("klausur", "Klausur"),
    ("test", "Test"),
    ("sonstiges", "Sonstiges"),
]


class EventDialog(QDialog):
    """Add or edit a scheduled_event. Returns dict via .data() when accepted.

    Usage:
        dlg = EventDialog(parent, initial=row_or_None)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.data()
            # payload = {"subject":..., "kind":..., "event_date":..., "topics":[...], "note":...}
    """

    def __init__(self, parent=None, initial=None):
        super().__init__(parent)
        self.setWindowTitle("Klassenarbeit" if initial is None else "Termin bearbeiten")
        self.setMinimumWidth(420)
        self._deleted = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        # Subject
        self.subject = QComboBox()
        self.subject.addItems(SUBJECTS_ALL)
        self.subject.setEditable(True)  # "Anderes…"-Effekt: user can type custom value
        form.addRow("Fach:", self.subject)

        # Kind (radio buttons)
        kind_row = QHBoxLayout()
        self.kind_group = QButtonGroup(self)
        self._kind_buttons: dict[str, QRadioButton] = {}
        for value, label in KIND_LABELS:
            rb = QRadioButton(label)
            self._kind_buttons[value] = rb
            self.kind_group.addButton(rb)
            kind_row.addWidget(rb)
        self._kind_buttons["klassenarbeit"].setChecked(True)
        form.addRow("Typ:", kind_row)

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        default_date = date.today() + timedelta(days=7)
        self.date_edit.setDate(QDate(default_date.year, default_date.month, default_date.day))
        form.addRow("Datum:", self.date_edit)

        # Topics
        self.topics_edit = QPlainTextEdit()
        self.topics_edit.setPlaceholderText("Eine Zeile = ein Thema")
        self.topics_edit.setMaximumHeight(110)
        form.addRow("Themen:", self.topics_edit)

        # Note
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("optional, z. B. „Formelsammlung erlaubt“")
        form.addRow("Notiz:", self.note_edit)

        layout.addLayout(form)

        # Bottom row: optional Delete + Save/Cancel
        bottom = QHBoxLayout()
        if initial is not None:
            del_btn = QPushButton("Löschen")
            del_btn.setObjectName("danger")
            del_btn.clicked.connect(self._on_delete)
            bottom.addWidget(del_btn)
        bottom.addStretch(1)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        bottom.addWidget(btns)
        layout.addLayout(bottom)

        if initial is not None:
            self._populate(initial)

    def _populate(self, row):
        idx = self.subject.findText(row["subject"])
        if idx >= 0:
            self.subject.setCurrentIndex(idx)
        else:
            self.subject.setEditText(row["subject"])
        if row["kind"] in self._kind_buttons:
            self._kind_buttons[row["kind"]].setChecked(True)
        d = row["event_date"]
        # ISO string YYYY-MM-DD
        y, m, da = int(d[:4]), int(d[5:7]), int(d[8:10])
        self.date_edit.setDate(QDate(y, m, da))
        topics = json.loads(row["topics"] or "[]")
        self.topics_edit.setPlainText("\n".join(topics))
        if row["note"]:
            self.note_edit.setText(row["note"])

    def _on_delete(self):
        self._deleted = True
        self.accept()

    def is_delete(self) -> bool:
        return self._deleted

    def data(self) -> dict:
        kind = next(v for v, rb in self._kind_buttons.items() if rb.isChecked())
        topics_text = self.topics_edit.toPlainText()
        topics = [t.strip() for t in topics_text.splitlines() if t.strip()]
        return {
            "subject": self.subject.currentText().strip(),
            "kind": kind,
            "event_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "topics": topics,
            "note": self.note_edit.text().strip() or None,
        }
```

- [ ] **Step 2: Smoke test by importing**

Run: `python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.ui.dialogs.event_dialog import EventDialog
d = EventDialog()
print('ok', d.data())"`
Expected: prints `ok {...}` with sensible defaults.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/dialogs/
git commit -m "feat(phase7): EventDialog for KA add/edit/delete"
```

---

## Task 11: AssessmentDialog — fast note entry

**Files:**
- Create: `src/school_test_engine/ui/dialogs/assessment_dialog.py`

- [ ] **Step 1: Write the dialog**

Create `src/school_test_engine/ui/dialogs/assessment_dialog.py`:

```python
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from .._subjects import SUBJECTS_ALL, note_color
from ..design import FontFamily


CATEGORY_LABELS = [
    ("schriftlich", "schriftlich"),
    ("muendlich", "mündlich"),
    ("sonstige", "sonstige"),
]


class _GradeSelector(QFrame):
    """Big-button row 1..6 with +/- 0.5 step buttons."""
    changed = Signal(float)

    def __init__(self, initial: float = 2.0, parent=None):
        super().__init__(parent)
        self._value = float(initial)
        h = QHBoxLayout(self)
        h.setSpacing(4)
        h.setContentsMargins(0, 0, 0, 0)

        self._buttons: dict[int, QPushButton] = {}
        for n in range(1, 7):
            b = QPushButton(str(n))
            b.setCheckable(True)
            b.setFixedSize(48, 48)
            color = note_color(n)
            b.setStyleSheet(
                f"QPushButton {{ background: #f4efe6; color: {color}; "
                f"font-family: 'Fraunces'; font-size: 18pt; border: 2px solid transparent; border-radius: 10px; }}"
                f"QPushButton:checked {{ background: {color}; color: #f6f1e6; }}"
            )
            b.clicked.connect(lambda _, val=n: self._set_int(val))
            self._buttons[n] = b
            h.addWidget(b)

        h.addSpacing(8)
        self._half = QPushButton(",5")
        self._half.setCheckable(True)
        self._half.setFixedSize(40, 48)
        self._half.setStyleSheet(
            "QPushButton { background: #f4efe6; color: #4a4538; "
            "font-family: 'Fraunces'; font-size: 14pt; border: 2px solid transparent; border-radius: 10px; }"
            "QPushButton:checked { background: #c79d44; color: #f6f1e6; }"
        )
        self._half.clicked.connect(self._toggle_half)
        h.addWidget(self._half)
        h.addStretch(1)

        self._apply(self._value)

    def _set_int(self, val: int):
        self._value = float(val)
        self._apply(self._value)
        self.changed.emit(self._value)

    def _toggle_half(self):
        base = int(self._value)
        if abs(self._value - base) < 0.01:
            self._value = base + 0.5
        else:
            self._value = float(base)
        self._apply(self._value)
        self.changed.emit(self._value)

    def _apply(self, val: float):
        base = int(val)
        for n, b in self._buttons.items():
            b.setChecked(n == base)
        self._half.setChecked(abs(val - base) >= 0.4)

    def value(self) -> float:
        return self._value

    def set_value(self, val: float):
        self._value = val
        self._apply(val)


class AssessmentDialog(QDialog):
    """Add or edit an assessment. Designed for fast entry (≤ 5 seconds for default case).

    Usage:
        dlg = AssessmentDialog(parent, initial=row_or_None,
                               prefill_subject=..., prefill_event_id=...)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            payload = dlg.data()
    """

    def __init__(self, parent=None, initial=None,
                 prefill_subject: str | None = None,
                 prefill_event_id: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("Note" if initial is None else "Note bearbeiten")
        self.setMinimumWidth(440)
        self._deleted = False
        self._prefill_event_id = prefill_event_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        # Grade selector — biggest visual element
        grade_label = QLabel("Note")
        grade_label.setObjectName("eyebrow")
        layout.addWidget(grade_label)
        self.grade = _GradeSelector(initial=2.0)
        layout.addWidget(self.grade)

        # Compact form for the rest
        form = QFormLayout()
        form.setSpacing(8)

        self.subject = QComboBox()
        self.subject.addItems(SUBJECTS_ALL)
        self.subject.setEditable(True)
        if prefill_subject:
            idx = self.subject.findText(prefill_subject)
            if idx >= 0:
                self.subject.setCurrentIndex(idx)
            else:
                self.subject.setEditText(prefill_subject)
        form.addRow("Fach:", self.subject)

        cat_row = QHBoxLayout()
        self.cat_group = QButtonGroup(self)
        self._cat_buttons: dict[str, QRadioButton] = {}
        for value, label in CATEGORY_LABELS:
            rb = QRadioButton(label)
            self._cat_buttons[value] = rb
            self.cat_group.addButton(rb)
            cat_row.addWidget(rb)
        self._cat_buttons["schriftlich"].setChecked(True)
        form.addRow("Art:", cat_row)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        today = date.today()
        self.date_edit.setDate(QDate(today.year, today.month, today.day))
        form.addRow("Datum:", self.date_edit)

        # Points (collapsible "Details")
        self.points = QDoubleSpinBox()
        self.points.setMaximum(1000)
        self.points.setDecimals(1)
        self.max_points = QDoubleSpinBox()
        self.max_points.setMaximum(1000)
        self.max_points.setDecimals(1)
        pts_row = QHBoxLayout()
        pts_row.addWidget(self.points)
        pts_row.addWidget(QLabel("von"))
        pts_row.addWidget(self.max_points)
        form.addRow("Punkte:", pts_row)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("optional")
        form.addRow("Notiz:", self.note_edit)

        layout.addLayout(form)

        bottom = QHBoxLayout()
        if initial is not None:
            del_btn = QPushButton("Löschen")
            del_btn.setObjectName("danger")
            del_btn.clicked.connect(self._on_delete)
            bottom.addWidget(del_btn)
        bottom.addStretch(1)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        bottom.addWidget(btns)
        layout.addLayout(bottom)

        if initial is not None:
            self._populate(initial)

    def _populate(self, row):
        self.grade.set_value(float(row["grade"]))
        idx = self.subject.findText(row["subject"])
        if idx >= 0:
            self.subject.setCurrentIndex(idx)
        else:
            self.subject.setEditText(row["subject"])
        if row["category"] in self._cat_buttons:
            self._cat_buttons[row["category"]].setChecked(True)
        d = row["assessment_date"]
        self.date_edit.setDate(QDate(int(d[:4]), int(d[5:7]), int(d[8:10])))
        if row["points"] is not None:
            self.points.setValue(float(row["points"]))
        if row["max_points"] is not None:
            self.max_points.setValue(float(row["max_points"]))
        if row["note"]:
            self.note_edit.setText(row["note"])

    def _on_delete(self):
        self._deleted = True
        self.accept()

    def is_delete(self) -> bool:
        return self._deleted

    def data(self) -> dict:
        category = next(v for v, rb in self._cat_buttons.items() if rb.isChecked())
        points = self.points.value() if self.points.value() > 0 else None
        max_points = self.max_points.value() if self.max_points.value() > 0 else None
        return {
            "subject": self.subject.currentText().strip(),
            "category": category,
            "assessment_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "grade": self.grade.value(),
            "points": points,
            "max_points": max_points,
            "note": self.note_edit.text().strip() or None,
            "scheduled_event_id": self._prefill_event_id,
        }
```

- [ ] **Step 2: Smoke test**

Run: `python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.ui.dialogs.assessment_dialog import AssessmentDialog
d = AssessmentDialog(prefill_subject='Mathe', prefill_event_id=5)
print('ok', d.data())"`
Expected: prints `ok {...}` with prefilled `subject='Mathe'` and `scheduled_event_id=5`.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/dialogs/assessment_dialog.py
git commit -m "feat(phase7): AssessmentDialog with big grade buttons + 0.5-step toggle"
```

---

## Task 12: EventsPage — Termine-Seite

**Files:**
- Create: `src/school_test_engine/ui/pages/events.py`

- [ ] **Step 1: Write the page**

Create `src/school_test_engine/ui/pages/events.py`:

```python
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...storage import events_repo, assessments_repo
from ..design import Color, FontFamily, Semantic
from ..dialogs.event_dialog import EventDialog
from ..dialogs.assessment_dialog import AssessmentDialog
from ..widgets.clickable_card import ClickableCard
from ..widgets.pill import Pill
from .._subjects import subject_variant


def _kind_label(kind: str) -> str:
    return {
        "klassenarbeit": "Klassenarbeit",
        "klausur": "Klausur",
        "test": "Test",
        "sonstiges": "Sonstiges",
    }.get(kind, "Termin")


def _format_date(iso: str) -> str:
    d = datetime.fromisoformat(iso).date()
    return d.strftime("%a, %d.%m.%Y")


class EventsPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(16)

        # Header row: back + eyebrow/title + add
        head = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(self.window.show_menu)
        head.addWidget(back)
        head.addStretch(1)
        add = QPushButton("+ Termin")
        add.setObjectName("primary")
        add.clicked.connect(self._add_event)
        head.addWidget(add)
        outer.addLayout(head)

        eyebrow = QLabel("TERMINE")
        eyebrow.setObjectName("eyebrow")
        outer.addWidget(eyebrow)

        title = QLabel("Was kommt")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        # Scrollable list
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(10)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._list_container)
        outer.addWidget(self._scroll, 1)

    def reload(self) -> None:
        uid = self.window.active_user_id
        if uid is None:
            return
        # Clear list
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        events = events_repo.list_all(self.conn, uid)
        if not events:
            empty = QLabel("Noch keine Termine eingetragen.\nKlick auf „+ Termin“ um den ersten anzulegen.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 11pt; padding: 40px;")
            empty.setWordWrap(True)
            self._list_layout.addWidget(empty)
            return

        today_iso = date.today().isoformat()
        for ev in events:
            card = self._make_event_row(ev, is_past=ev["event_date"] < today_iso)
            self._list_layout.addWidget(card)

    def _make_event_row(self, ev, is_past: bool) -> ClickableCard:
        card = ClickableCard(object_name="eventListCard")
        card.clicked.connect(lambda eid=ev["id"]: self._edit_event(eid))
        if is_past:
            card.setProperty("dimmed", True)
        card.setMinimumHeight(80)

        h = QHBoxLayout(card)
        h.setContentsMargins(18, 12, 18, 12)
        h.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(2)
        date_lbl = QLabel(_format_date(ev["event_date"]))
        date_lbl.setStyleSheet(
            f"color: {Color.PAPER_600 if is_past else Semantic.FG}; font-size: 10pt;"
        )
        left.addWidget(date_lbl)

        kind_lbl = QLabel(_kind_label(ev["kind"]))
        kind_lbl.setFont(QFont(FontFamily.DISPLAY, 16, QFont.Weight.Medium))
        kind_lbl.setStyleSheet(
            f"color: {Color.PAPER_500 if is_past else Semantic.FG};"
        )
        left.addWidget(kind_lbl)

        topics = json.loads(ev["topics"] or "[]")
        if topics:
            topics_lbl = QLabel(" · ".join(topics))
            topics_lbl.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
            topics_lbl.setWordWrap(True)
            left.addWidget(topics_lbl)

        h.addLayout(left, 1)

        # Subject pill
        h.addWidget(Pill(ev["subject"].upper(), subject_variant(ev["subject"])))

        # Assessment status
        assess = assessments_repo.find_by_event(self.conn, ev["id"])
        if assess is not None:
            h.addWidget(Pill(f"Note {str(assess['grade']).replace('.', ',')}", "tea"))
        elif is_past:
            h.addWidget(Pill("Note fehlt", "honey"))

        return card

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_event(self):
        dlg = EventDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.data()
            events_repo.create(
                self.conn, self.window.active_user_id,
                data["subject"], data["kind"], data["event_date"],
                topics=data["topics"], note=data["note"],
            )
            self.reload()

    def _edit_event(self, event_id: int):
        ev = events_repo.get(self.conn, event_id)
        if ev is None:
            return
        dlg = EventDialog(self, initial=ev)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.is_delete():
            events_repo.delete(self.conn, event_id)
        else:
            data = dlg.data()
            events_repo.update(
                self.conn, event_id,
                subject=data["subject"], kind=data["kind"], event_date=data["event_date"],
                topics=data["topics"], note=data["note"],
            )
        self.reload()
```

- [ ] **Step 2: Smoke test**

Run: `python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
class FakeWindow:
    active_user_id = 1
    def show_menu(self): pass
import sqlite3
from school_test_engine.storage import connect, run_migrations
c = connect(':memory:')
run_migrations(c)
from school_test_engine.ui.pages.events import EventsPage
p = EventsPage(FakeWindow(), c)
p.reload()
print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/pages/events.py
git commit -m "feat(phase7): EventsPage — list/add/edit/delete Termine"
```

---

## Task 13: GradesPage — Noten-Seite with subject tabs + comparison

**Files:**
- Create: `src/school_test_engine/ui/pages/grades.py`

- [ ] **Step 1: Write the page**

Create `src/school_test_engine/ui/pages/grades.py`:

```python
from __future__ import annotations

import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...cockpit import service as cockpit
from ...storage import assessments_repo
from ..design import Color, FontFamily, Semantic
from ..dialogs.assessment_dialog import AssessmentDialog
from ..widgets.comparison_view import ComparisonView
from ..widgets.grade_pill import GradePill
from ..widgets.pill import Pill
from .._subjects import SUBJECTS_ALL, subject_variant


CATEGORY_LABEL = {"schriftlich": "schriftlich", "muendlich": "mündlich", "sonstige": "sonstige"}


def _format_date(iso: str) -> str:
    d = datetime.fromisoformat(iso).date()
    return d.strftime("%d.%m.%Y")


class GradesPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._current_subject = SUBJECTS_ALL[0]

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(16)

        # Header
        head = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(self.window.show_menu)
        head.addWidget(back)
        head.addStretch(1)
        add = QPushButton("+ Note")
        add.setObjectName("primary")
        add.clicked.connect(self._add_assessment)
        head.addWidget(add)
        outer.addLayout(head)

        eyebrow = QLabel("NOTEN")
        eyebrow.setObjectName("eyebrow")
        outer.addWidget(eyebrow)

        title = QLabel("Wie's läuft")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        # Subject pill row
        self._subject_row = QHBoxLayout()
        self._subject_row.setSpacing(6)
        self._subject_buttons: dict[str, QPushButton] = {}
        for s in SUBJECTS_ALL:
            b = QPushButton(s)
            b.setCheckable(True)
            b.setObjectName("subjectTab")
            b.clicked.connect(lambda _, sub=s: self._select_subject(sub))
            self._subject_buttons[s] = b
            self._subject_row.addWidget(b)
        self._subject_row.addStretch(1)
        outer.addLayout(self._subject_row)

        # Scrollable content
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setSpacing(14)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, 1)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reload(self) -> None:
        for sub, btn in self._subject_buttons.items():
            btn.setChecked(sub == self._current_subject)
        self._render_content()

    def _select_subject(self, subject: str):
        self._current_subject = subject
        self.reload()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_content(self):
        uid = self.window.active_user_id
        if uid is None:
            return
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Hero: subject average
        avg = cockpit.subject_grade_average(self.conn, uid, self._current_subject)
        self._content_layout.addWidget(self._build_average_hero(avg))

        # List of assessments
        rows = assessments_repo.list_by_subject(self.conn, uid, self._current_subject)
        if not rows:
            empty = QLabel("Noch keine Noten in diesem Fach.\nKlick auf „+ Note“ um deine erste einzutragen.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 11pt; padding: 30px;")
            empty.setWordWrap(True)
            self._content_layout.addWidget(empty)
        else:
            for r in rows:
                self._content_layout.addWidget(self._build_assessment_card(r))

        # Aggregate comparison (across all subjects)
        agg = cockpit.aggregate_comparison(self.conn, uid)
        if agg is not None:
            agg_lbl = QLabel(agg.label)
            agg_lbl.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 11pt; padding-top: 20px;")
            agg_lbl.setWordWrap(True)
            self._content_layout.addWidget(agg_lbl)

    def _build_average_hero(self, avg) -> QFrame:
        f = QFrame()
        f.setObjectName("gradeHero")
        h = QHBoxLayout(f)
        h.setContentsMargins(20, 18, 20, 18)
        h.setSpacing(20)

        if avg.zeugnis_estimate is not None:
            h.addWidget(GradePill(avg.zeugnis_estimate, size=84))
        else:
            placeholder = QLabel("—")
            placeholder.setFixedSize(84, 84)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(
                "background: #f4efe6; color: #b3a98e; font-family: 'Fraunces'; "
                "font-size: 32pt; border-radius: 42px;"
            )
            h.addWidget(placeholder)

        details = QVBoxLayout()
        details.setSpacing(4)
        eyebrow = QLabel("ZEUGNIS-SCHÄTZUNG · 50/50")
        eyebrow.setObjectName("eyebrow")
        details.addWidget(eyebrow)
        zeugnis_value = "—" if avg.zeugnis_estimate is None else f"{avg.zeugnis_estimate:.2f}".replace(".", ",")
        zeugnis_lbl = QLabel(zeugnis_value)
        zeugnis_lbl.setFont(QFont(FontFamily.DISPLAY, 22, QFont.Weight.Normal))
        details.addWidget(zeugnis_lbl)

        breakdown = QLabel(
            f"schriftlich {self._fmt_avg(avg.schriftlich_avg)}   ·   mündlich {self._fmt_avg(avg.muendlich_avg)}"
        )
        breakdown.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
        details.addWidget(breakdown)
        h.addLayout(details)
        h.addStretch(1)
        return f

    def _fmt_avg(self, val: float | None) -> str:
        if val is None:
            return "—"
        return f"{val:.2f}".replace(".", ",")

    def _build_assessment_card(self, row) -> QFrame:
        card = QFrame()
        card.setObjectName("assessmentCard")
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(GradePill(float(row["grade"]), size=44))
        info = QVBoxLayout()
        info.setSpacing(2)
        cat_lbl = QLabel(CATEGORY_LABEL.get(row["category"], row["category"]).upper())
        cat_lbl.setObjectName("eyebrow")
        info.addWidget(cat_lbl)
        date_lbl = QLabel(_format_date(row["assessment_date"]))
        date_lbl.setStyleSheet(f"color: {Semantic.FG}; font-size: 11pt;")
        info.addWidget(date_lbl)
        if row["points"] is not None and row["max_points"] is not None:
            pts = QLabel(f"{row['points']:.0f} / {row['max_points']:.0f} Punkte")
            pts.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
            info.addWidget(pts)
        if row["note"]:
            note = QLabel(row["note"])
            note.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt; font-style: italic;")
            note.setWordWrap(True)
            info.addWidget(note)
        head.addLayout(info, 1)

        edit_btn = QPushButton("Bearbeiten")
        edit_btn.setObjectName("text")
        edit_btn.clicked.connect(lambda _, aid=row["id"]: self._edit_assessment(aid))
        head.addWidget(edit_btn)
        v.addLayout(head)

        # Comparison block if linked
        if row["scheduled_event_id"] is not None:
            cmp = cockpit.comparison_for_assessment(self.conn, row["id"])
            if cmp is not None:
                v.addWidget(ComparisonView(cmp))

        return card

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_assessment(self):
        dlg = AssessmentDialog(self, prefill_subject=self._current_subject)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.data()
            assessments_repo.create(
                self.conn, self.window.active_user_id,
                data["subject"], data["category"], data["assessment_date"],
                grade=data["grade"], points=data["points"], max_points=data["max_points"],
                note=data["note"], scheduled_event_id=data["scheduled_event_id"],
            )
            self.reload()

    def _edit_assessment(self, assessment_id: int):
        row = assessments_repo.get(self.conn, assessment_id)
        if row is None:
            return
        dlg = AssessmentDialog(self, initial=row, prefill_event_id=row["scheduled_event_id"])
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.is_delete():
            assessments_repo.delete(self.conn, assessment_id)
        else:
            data = dlg.data()
            assessments_repo.update(
                self.conn, assessment_id,
                subject=data["subject"], category=data["category"], assessment_date=data["assessment_date"],
                grade=data["grade"], points=data["points"], max_points=data["max_points"],
                note=data["note"], scheduled_event_id=data["scheduled_event_id"],
            )
        self.reload()
```

- [ ] **Step 2: Smoke test**

Run: `python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
class FakeWindow:
    active_user_id = 1
    def show_menu(self): pass
from school_test_engine.storage import connect, run_migrations
c = connect(':memory:')
run_migrations(c)
from school_test_engine.ui.pages.grades import GradesPage
p = GradesPage(FakeWindow(), c)
p.reload()
print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/pages/grades.py
git commit -m "feat(phase7): GradesPage with subject tabs, hero average, comparison cards"
```

---

## Task 14: Wire pages into MainWindow + navigation

**Files:**
- Modify: `src/school_test_engine/ui/main_window.py`

- [ ] **Step 1: Add page instances + navigation methods**

Edit `src/school_test_engine/ui/main_window.py`:

Add imports at the top (after the existing page imports):

```python
from .pages.events import EventsPage
from .pages.grades import GradesPage
```

In `__init__`, after `self.history_page = HistoryPage(self, conn)`, add:

```python
        self.events_page = EventsPage(self, conn)
        self.grades_page = GradesPage(self, conn)
```

In the page-registration loop, append the two new pages to the tuple so they are added to the stack:

```python
        for page in (
            self.profile_picker_page,
            self.profile_manager_page,
            self.menu_page,
            self.library_page,
            self.runner_page,
            self.review_page,
            self.results_page,
            self.import_page,
            self.gaps_page,
            self.history_page,
            self.events_page,
            self.grades_page,
        ):
            self.stack.addWidget(page)
```

Add two new navigation methods after `show_history`:

```python
    def show_events(self) -> None:
        self.events_page.reload()
        self.stack.setCurrentWidget(self.events_page)

    def show_grades(self) -> None:
        self.grades_page.reload()
        self.stack.setCurrentWidget(self.grades_page)
```

- [ ] **Step 2: Smoke test by launching the app**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && ./run.sh`
Expected: App opens to profile picker as before (no regression). Navigation to events/grades only via top-bar after Task 15.
Close the app after verifying it starts cleanly.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/main_window.py
git commit -m "feat(phase7): wire EventsPage and GradesPage into MainWindow stack"
```

---

## Task 15: Adaptive MenuPage — KA-Strip + Top-Bar icons

**Files:**
- Modify: `src/school_test_engine/ui/pages/menu.py`

- [ ] **Step 1: Rewrite MenuPage with adaptive layout**

Replace the body of `src/school_test_engine/ui/pages/menu.py` (keeping the helper `_make_action_card`, `_ProfileChip`, and the `LOGOMARK_PATH` constant) with the following structure for `MenuPage`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...cockpit import service as cockpit
from ...storage import users_repo
from .._layouts import row_get
from ..design import Color, FontFamily, Semantic
from ..widgets.avatar_badge import round_pixmap
from ..widgets.clickable_card import ClickableCard
from ..widgets.exam_card import ExamCard
from ..dialogs.assessment_dialog import AssessmentDialog
from ..dialogs.event_dialog import EventDialog
from ...storage import events_repo, assessments_repo


LOGOMARK_PATH = Path(__file__).resolve().parents[3].parent / "assets" / "logomark.svg"


class MenuPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

        outer = QVBoxLayout(self)
        outer.setSpacing(20)
        outer.setContentsMargins(48, 36, 48, 36)
        self._outer = outer

        # Top bar
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        if LOGOMARK_PATH.exists():
            logo = QSvgWidget(str(LOGOMARK_PATH))
            logo.setFixedSize(QSize(36, 36))
            top_row.addWidget(logo)
        wordmark = QLabel("die <i>Kessler</i> Übungstests")
        wordmark.setFont(QFont(FontFamily.DISPLAY, 14, QFont.Weight.Normal))
        wordmark.setStyleSheet(f"color: {Color.PAPER_700};")
        top_row.addWidget(wordmark)
        top_row.addStretch(1)

        # New top-bar icon buttons
        events_btn = QPushButton("📅 Termine")
        events_btn.setObjectName("topBarAction")
        events_btn.clicked.connect(self.window.show_events)
        top_row.addWidget(events_btn)

        grades_btn = QPushButton("📊 Noten")
        grades_btn.setObjectName("topBarAction")
        grades_btn.clicked.connect(self.window.show_grades)
        top_row.addWidget(grades_btn)

        self.chip = _ProfileChip()
        self.chip.switch_clicked.connect(self._switch_profile)
        top_row.addWidget(self.chip)
        outer.addLayout(top_row)

        # Eyebrow + Greeting
        self.eyebrow = QLabel("HEUTE")
        self.eyebrow.setObjectName("eyebrow")
        self.eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.eyebrow)

        self.greeting = QLabel("Hallo")
        self.greeting.setObjectName("title")
        self.greeting.setFont(QFont(FontFamily.DISPLAY, 36, QFont.Weight.Normal))
        self.greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.greeting)
        outer.addSpacing(12)

        # Dynamic content area — rebuilt on reload()
        self._dynamic_container = QWidget()
        self._dynamic_layout = QVBoxLayout(self._dynamic_container)
        self._dynamic_layout.setSpacing(16)
        self._dynamic_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._dynamic_container)
        outer.addStretch(1)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reload(self) -> None:
        uid = self.window.active_user_id
        if uid is None:
            return
        user = users_repo.get_user(self.window.conn, uid)
        if user is None:
            return
        self.chip.set_user(user["avatar"], user["name"], row_get(user, "avatar_image"))
        self.greeting.setText(f"Hallo, {user['name']}")

        # Rebuild dynamic content
        while self._dynamic_layout.count():
            item = self._dynamic_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        events = cockpit.upcoming_events_for_menu(self.window.conn, uid, today=date.today())
        if events:
            self._build_ka_hero(events)
            self._build_compact_grid()
        else:
            self._build_empty_state()
            self._build_full_grid()

    def _switch_profile(self) -> None:
        self.window.show_profile_picker()

    # ------------------------------------------------------------------
    # Layout variants
    # ------------------------------------------------------------------

    def _build_ka_hero(self, events) -> None:
        eyebrow = QLabel("NÄCHSTE KLASSENARBEITEN")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dynamic_layout.addWidget(eyebrow)

        strip = QHBoxLayout()
        strip.setSpacing(14)
        strip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for ev in events:
            card = ExamCard(ev)
            card.enter_grade_clicked.connect(self._on_enter_grade)
            card.edit_clicked.connect(self._on_edit_event)
            strip.addWidget(card)
        wrap = QWidget()
        wrap.setLayout(strip)
        self._dynamic_layout.addWidget(wrap)

    def _build_empty_state(self) -> None:
        f = QFrame()
        f.setObjectName("emptyEvents")
        h = QHBoxLayout(f)
        h.setContentsMargins(20, 16, 20, 16)
        h.setSpacing(12)
        lbl = QLabel("Keine Klassenarbeiten geplant.")
        lbl.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 11pt;")
        h.addWidget(lbl)
        h.addStretch(1)
        btn = QPushButton("+ Termin")
        btn.setObjectName("text")
        btn.clicked.connect(self._on_add_event_from_menu)
        h.addWidget(btn)
        self._dynamic_layout.addWidget(f)

    def _build_compact_grid(self) -> None:
        """Quick-access row when KAs are present — single row of 4 small tiles."""
        grid_wrap = QHBoxLayout()
        grid_wrap.addStretch(1)
        container = QWidget()
        container.setMaximumWidth(820)
        row = QHBoxLayout(container)
        row.setSpacing(12)
        row.setContentsMargins(0, 0, 0, 0)

        items = [
            ("LIBRARY", "Bibliothek", self.window.show_library),
            ("HAKT", "Lücken", self.window.show_gaps),
            ("RÜCKBLICK", "Verlauf", self.window.show_history),
            ("IMPORT", "Test importieren", self.window.show_import),
        ]
        for eyebrow_text, title, action in items:
            tile = _make_compact_tile(eyebrow_text, title)
            tile.clicked.connect(action)
            row.addWidget(tile)
        grid_wrap.addWidget(container)
        grid_wrap.addStretch(1)
        self._dynamic_layout.addLayout(grid_wrap)

    def _build_full_grid(self) -> None:
        grid_wrap = QHBoxLayout()
        grid_wrap.addStretch(1)
        grid_container = QWidget()
        grid_container.setMaximumWidth(820)
        grid = QGridLayout(grid_container)
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)

        start = _make_action_card("ÜBEN", "Test starten", "Wähle einen Test aus deiner Bibliothek")
        start.clicked.connect(self.window.show_library)
        grid.addWidget(start, 0, 0)

        imp = _make_action_card("AUFGABEN", "Test importieren", "Neue Fragen aus einer JSON-Datei einlesen")
        imp.clicked.connect(self.window.show_import)
        grid.addWidget(imp, 0, 1)

        gaps = _make_action_card("ANALYSE", "Was noch hakt", "Themen sortiert nach Schwäche — mit Üben-Knopf")
        gaps.clicked.connect(self.window.show_gaps)
        grid.addWidget(gaps, 1, 0)

        hist = _make_action_card("RÜCKBLICK", "Bisherige Versuche", "Alle Tests mit Note und Datum")
        hist.clicked.connect(self.window.show_history)
        grid.addWidget(hist, 1, 1)

        grid_wrap.addWidget(grid_container)
        grid_wrap.addStretch(1)
        self._dynamic_layout.addLayout(grid_wrap)

    # ------------------------------------------------------------------
    # ExamCard actions
    # ------------------------------------------------------------------

    def _on_enter_grade(self, event_id: int) -> None:
        from PySide6.QtWidgets import QDialog
        ev = events_repo.get(self.window.conn, event_id)
        if ev is None:
            return
        dlg = AssessmentDialog(
            self, prefill_subject=ev["subject"], prefill_event_id=event_id
        )
        # Prefill date with KA date
        from PySide6.QtCore import QDate
        d = ev["event_date"]
        dlg.date_edit.setDate(QDate(int(d[:4]), int(d[5:7]), int(d[8:10])))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.data()
            assessments_repo.create(
                self.window.conn, self.window.active_user_id,
                data["subject"], data["category"], data["assessment_date"],
                grade=data["grade"], points=data["points"], max_points=data["max_points"],
                note=data["note"], scheduled_event_id=event_id,
            )
            self.reload()

    def _on_edit_event(self, event_id: int) -> None:
        from PySide6.QtWidgets import QDialog
        ev = events_repo.get(self.window.conn, event_id)
        if ev is None:
            return
        dlg = EventDialog(self, initial=ev)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.is_delete():
            events_repo.delete(self.window.conn, event_id)
        else:
            data = dlg.data()
            events_repo.update(
                self.window.conn, event_id,
                subject=data["subject"], kind=data["kind"], event_date=data["event_date"],
                topics=data["topics"], note=data["note"],
            )
        self.reload()

    def _on_add_event_from_menu(self) -> None:
        from PySide6.QtWidgets import QDialog
        dlg = EventDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.data()
            events_repo.create(
                self.window.conn, self.window.active_user_id,
                data["subject"], data["kind"], data["event_date"],
                topics=data["topics"], note=data["note"],
            )
            self.reload()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


class _ProfileChip(QFrame):
    """Kompakte Anzeige des aktiven Profils mit 'Wechseln'-Button."""

    switch_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("profileChip")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 4, 6, 4)
        h.setSpacing(8)

        self.avatar = QLabel("👤")
        self.avatar.setObjectName("profileChipAvatar")
        self.avatar.setFixedSize(28, 28)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self.avatar)

        self.name = QLabel("…")
        self.name.setObjectName("profileChipName")
        h.addWidget(self.name)

        switch = QPushButton("Wechseln")
        switch.setObjectName("text")
        switch.clicked.connect(self.switch_clicked)
        h.addWidget(switch)

    def set_user(self, avatar: str, name: str, image_bytes: bytes | None = None) -> None:
        if image_bytes:
            pm = QPixmap()
            if pm.loadFromData(image_bytes):
                self.avatar.setPixmap(round_pixmap(pm, 28))
                self.avatar.setText("")
                self.name.setText(name)
                return
        self.avatar.clear()
        self.avatar.setText(avatar)
        self.name.setText(name)


def _make_action_card(eyebrow_text: str, title_text: str, description: str) -> ClickableCard:
    card = ClickableCard(object_name="actionCard")
    card.setMinimumSize(340, 150)
    card.setMaximumHeight(180)
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(22, 18, 22, 16)
    layout.setSpacing(6)
    eyebrow = QLabel(eyebrow_text)
    eyebrow.setObjectName("eyebrow")
    layout.addWidget(eyebrow)
    title = QLabel(title_text)
    title.setObjectName("h2")
    title.setFont(QFont(FontFamily.DISPLAY, 18, QFont.Weight.Medium))
    title.setWordWrap(True)
    title.setStyleSheet(f"color: {Semantic.FG};")
    layout.addWidget(title)
    desc = QLabel(description)
    desc.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
    desc.setWordWrap(True)
    layout.addWidget(desc)
    layout.addStretch(1)
    arrow_row = QHBoxLayout()
    arrow_row.addStretch(1)
    arrow = QLabel("→")
    arrow.setStyleSheet(f"color: {Semantic.ACCENT}; font-size: 16pt; font-weight: 600;")
    arrow_row.addWidget(arrow)
    layout.addLayout(arrow_row)
    return card


def _make_compact_tile(eyebrow_text: str, title_text: str) -> ClickableCard:
    card = ClickableCard(object_name="compactTile")
    card.setMinimumSize(180, 88)
    card.setMaximumHeight(100)
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    v = QVBoxLayout(card)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(2)
    eyebrow = QLabel(eyebrow_text)
    eyebrow.setObjectName("eyebrow")
    v.addWidget(eyebrow)
    title = QLabel(title_text)
    title.setFont(QFont(FontFamily.DISPLAY, 14, QFont.Weight.Medium))
    title.setStyleSheet(f"color: {Semantic.FG};")
    v.addWidget(title)
    v.addStretch(1)
    return card
```

- [ ] **Step 2: Smoke test by launching the app**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && ./run.sh`

Verify manually (in order):
1. Profile picker opens; click Clemens (or Standard).
2. Main menu shows empty-state row "Keine Klassenarbeiten geplant" + classic 2×2 grid.
3. Top-bar has "📅 Termine" and "📊 Noten" buttons left of profile chip.
4. Click "📅 Termine" → EventsPage opens. Add a KA in 5 days (Mathe, „Funktionen“) → save.
5. Click ← Zurück → main menu now shows KA-Strip with the new card on top + compact tile row below.
6. Click "Note eintragen" on the ExamCard → AssessmentDialog opens with Mathe + date prefilled. Enter note 2 → save.
7. Main menu: ExamCard now shows "Note erfasst ✓" pill instead of action button.
8. Click "📊 Noten" → GradesPage, Mathe tab active, hero shows 2,00. Click the note → edit dialog opens, "Bearbeiten" button works.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/pages/menu.py
git commit -m "feat(phase7): adaptive MenuPage with KA-Strip + top-bar Termine/Noten"
```

---

## Task 16: Add CSS for new objects in style.qss

**Files:**
- Modify: `src/school_test_engine/ui/style.qss`

- [ ] **Step 1: Append new style rules**

Append the following block to `src/school_test_engine/ui/style.qss`:

```css
/* ----- Phase 7: Schul-Cockpit ----- */

/* Top-bar Termine/Noten buttons */
QPushButton#topBarAction {
    background: transparent;
    color: #4a4538;
    border: 1px solid #d8cdb8;
    padding: 4px 12px;
    border-radius: 14px;
    font-size: 10pt;
}
QPushButton#topBarAction:hover {
    background: #f4efe6;
}

/* ExamCard (hero KA card on menu) */
ClickableCard#examCard {
    background: #fbf6ec;
    border: 1px solid #ead9be;
    border-radius: 14px;
}
ClickableCard#examCard:hover {
    background: #f6efde;
}

/* Compact tile (row of small tiles when KAs present) */
ClickableCard#compactTile {
    background: #fbf6ec;
    border: 1px solid #e6dac0;
    border-radius: 12px;
}
ClickableCard#compactTile:hover {
    background: #f3e9cf;
}

/* Empty-state row on menu */
QFrame#emptyEvents {
    background: transparent;
    border: 1px dashed #d8cdb8;
    border-radius: 12px;
}

/* Event list card (Termine page) */
ClickableCard#eventListCard {
    background: #fbf6ec;
    border: 1px solid #ead9be;
    border-radius: 12px;
}
ClickableCard#eventListCard[dimmed="true"] {
    background: #f4efe6;
    border: 1px solid #e1d7c1;
}

/* Subject tab buttons on Grades page */
QPushButton#subjectTab {
    background: transparent;
    color: #4a4538;
    border: 1px solid #d8cdb8;
    padding: 5px 14px;
    border-radius: 14px;
    font-size: 10pt;
}
QPushButton#subjectTab:checked {
    background: #3e552d;
    color: #f6f1e6;
    border-color: #3e552d;
}
QPushButton#subjectTab:hover:!checked {
    background: #f4efe6;
}

/* Grade hero card on Grades page */
QFrame#gradeHero {
    background: #fbf6ec;
    border: 1px solid #ead9be;
    border-radius: 16px;
}

/* Assessment card on Grades page */
QFrame#assessmentCard {
    background: #fbf6ec;
    border: 1px solid #ead9be;
    border-radius: 12px;
}

/* Comparison card inside assessment card */
QFrame#comparisonCard {
    background: #f4efe6;
    border: 1px solid #d8cdb8;
    border-radius: 10px;
}

/* Danger button (delete in dialogs) */
QPushButton#danger {
    background: transparent;
    color: #7e3b39;
    border: 1px solid #c9a5a2;
    padding: 5px 14px;
    border-radius: 10px;
}
QPushButton#danger:hover {
    background: #f6dcdb;
}
```

- [ ] **Step 2: Smoke test by relaunching the app**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && ./run.sh`
Manually verify:
- ExamCards have warm-cream background with subtle border.
- Top-bar buttons "📅 Termine" / "📊 Noten" have outlined pill shape.
- On Grades page, subject tabs highlight tea-700 (dark green) when selected.
- Past events on Termine page appear dimmer than upcoming ones.
- AssessmentDialog: 1–6 grade buttons fill with `note_color` when selected.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/style.qss
git commit -m "feat(phase7): QSS for cockpit widgets (exam cards, tabs, grade hero, comparison)"
```

---

## Task 17: User isolation regression test

**Files:**
- Modify: `tests/test_user_isolation.py` (or create `tests/test_cockpit_isolation.py` if cleaner)

- [ ] **Step 1: Write isolation tests**

Create `tests/test_cockpit_isolation.py`:

```python
import pytest

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import events_repo, assessments_repo


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_two_users_dont_see_each_others_events(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    events_repo.create(conn, a, "Mathe", "klassenarbeit", "2026-06-01", topics=[])
    events_repo.create(conn, b, "Bio", "klassenarbeit", "2026-06-02", topics=[])
    assert len(events_repo.list_all(conn, a)) == 1
    assert len(events_repo.list_all(conn, b)) == 1
    assert events_repo.list_all(conn, a)[0]["subject"] == "Mathe"


def test_two_users_dont_see_each_others_assessments(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    assessments_repo.create(conn, a, "Mathe", "schriftlich", "2026-06-01", grade=2.0)
    assessments_repo.create(conn, b, "Mathe", "schriftlich", "2026-06-02", grade=4.0)
    assert assessments_repo.list_all(conn, a)[0]["grade"] == 2.0
    assert assessments_repo.list_all(conn, b)[0]["grade"] == 4.0


def test_delete_user_cascade_removes_events_and_assessments(conn):
    uid = users_repo.create_user(conn, "Wegmacher")
    eid = events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-06-01", topics=[])
    assessments_repo.create(conn, uid, "Mathe", "schriftlich", "2026-06-01", grade=2.0, scheduled_event_id=eid)
    users_repo.delete_user(conn, uid)
    assert conn.execute("SELECT COUNT(*) FROM scheduled_events WHERE user_id = ?", (uid,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM assessments WHERE user_id = ?", (uid,)).fetchone()[0] == 0
```

- [ ] **Step 2: Update users_repo.delete_user to also remove cockpit rows**

The existing `users_repo.delete_user` only removes tests/attempts/answers because the FK CASCADE on `users` was not declared in migration 004 (history-of-the-codebase). Migration 006 *does* declare `ON DELETE CASCADE`, so this should already work — but only if `PRAGMA foreign_keys = ON` is set on the connection. `connect()` already enables it.

Verify by running the test. If it fails, edit `src/school_test_engine/storage/users_repo.py` `delete_user`:

Add before the `DELETE FROM users` line:

```python
    conn.execute("DELETE FROM assessments WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM scheduled_events WHERE user_id = ?", (user_id,))
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_cockpit_isolation.py -v`
Expected: 3 PASS.

- [ ] **Step 4: Run the entire test suite**

Run: `pytest -v`
Expected: All existing tests still pass; new cockpit tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_cockpit_isolation.py src/school_test_engine/storage/users_repo.py
git commit -m "test(phase7): user-isolation for events + assessments; cascade on user delete"
```

---

## Task 18: End-to-end smoke test (manual)

**Files:** none

- [ ] **Step 1: Run the manual smoke test**

The full happy path that proves Phase 7 works end-to-end. Run `./run.sh` and walk through this sequence on a fresh user profile:

1. Profile-Picker → create a fresh user "Smoke" → enter main menu.
2. Main menu shows empty state "Keine Klassenarbeiten geplant" + 2×2 grid (Library, Lücken, Verlauf, Import).
3. Top-bar: "📅 Termine" → create event "Mathe / Klassenarbeit / 2026-05-19 / Funktionen, Gleichungen" → save.
4. Top-bar: "📅 Termine" again → list shows one entry, future-styled.
5. ← Zurück → main menu now shows ExamCard for Mathe with "in 7 Tagen" countdown.
6. Library → import a Mathe test (use one of the JSON fixtures in `examples/`).
7. Run the test, finish with note 3 → results.
8. ← Hauptmenü → ExamCard still there.
9. Import a second Mathe test, run it, finish with note 2.
10. Main menu → click "Note eintragen" on ExamCard → dialog opens with Mathe + 2026-05-19 prefilled.
11. Enter grade 2 → save.
12. Main menu: ExamCard now shows "Note erfasst ✓".
13. Top-bar: "📊 Noten" → Mathe tab → hero shows 2,00 ; one assessment card with comparison block:
    - App-Übungen avg = 2.5 (note 3 and note 2 averaged)
    - echte Note = 2
    - delta_label = "Du warst in der KA besser als in App-Übungen ↑" (or similar)
14. Click "Bearbeiten" on the assessment → change grade to 3 → save → comparison updates.
15. Profile-Picker → delete "Smoke" → re-enter Picker, ensure no remnants.

If any step fails, debug, fix, and re-run from the failing step.

- [ ] **Step 2: Final commit (optional)**

If any small fixes were made during smoke testing:

```bash
git add -A
git commit -m "fix(phase7): smoke-test polish"
```

---

## Self-Review (already done while writing)

**Spec coverage:**
- §2 Datenmodell → Task 1 ✓
- §3.1 Repos → Tasks 2, 3 ✓
- §3.2 Service-Modul → Tasks 4, 5, 6 ✓
- §3.3 Widgets → Tasks 7, 8, 9 ✓
- §3.3 Dialoge → Tasks 10, 11 ✓
- §3.3 New Pages → Tasks 12, 13 ✓
- §3.3 Adaptive Hauptmenü + Top-Bar → Task 15 ✓
- §4 Vergleichs-Logik → Task 5 (comparison_for_assessment + tests) ✓
- §5 Zeugnis-Schätzung → Task 6 (subject_grade_average) + GradesPage hero (Task 13) ✓
- §6 Edge cases → covered in Task 5 tests + Task 17 isolation tests
- §7 Tests → present throughout
- §9 Akzeptanzkriterien → Task 18 manual smoke checks all 10 criteria

**Type consistency:** `EventCardData`, `ComparisonData`, `SubjectAverage`, `AggregateComparison` defined once each in `cockpit/service.py`, used consistently by widgets/pages.

**Placeholder scan:** No TBDs. Every step has either complete code or a runnable command.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-phase-7-schul-cockpit.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

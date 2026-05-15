# Phase 15 — iCal-Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sync Clemens' Klassenarbeiten and Lernkontrollen automatically from the Schulportal-Hessen iCal feed into `scheduled_events`. Idempotent, UID-keyed, with update-on-change, delete-only-without-note semantics. Manual button on the Events-Page plus silent auto-sync on profile switch (24h throttle).

**Architecture:** New domain package `ical_sync/` with bottom-up pipeline (`fetcher` → `parser` → `classifier` → `extractor` → `service`). One migration (`011_phase15_ical_sync.sql`) adds three columns to `users` and two to `scheduled_events` plus a partial unique index. `icalendar` is added as a new top-level dep. UI: `QPlainTextEdit` field in profile-edit-page, sync button + status label on events-page. Threading via `QThread`-wrapped `SyncWorker` with dependency-injectable sync runner for tests.

**Tech Stack:** PySide6 (Qt6), Python 3.11+, SQLite, pytest with `QT_QPA_PLATFORM=offscreen`, urllib.request (stdlib HTTP), icalendar (new dep).

**Spec:** `docs/superpowers/specs/2026-05-15-phase-15-ical-sync-design.md`

---

## File Structure

### Created
- `src/school_test_engine/storage/migrations/011_phase15_ical_sync.sql`
- `src/school_test_engine/ical_sync/__init__.py`
- `src/school_test_engine/ical_sync/fetcher.py`
- `src/school_test_engine/ical_sync/parser.py`
- `src/school_test_engine/ical_sync/classifier.py`
- `src/school_test_engine/ical_sync/subject_map.py`
- `src/school_test_engine/ical_sync/extractor.py`
- `src/school_test_engine/ical_sync/service.py`
- `src/school_test_engine/ui/sync_worker.py`
- `tests/fixtures/schulkalender_mini.ics`
- `tests/test_migration_011.py`
- `tests/test_subjects_all.py`
- `tests/ical_sync/__init__.py`
- `tests/ical_sync/test_fetcher.py`
- `tests/ical_sync/test_parser.py`
- `tests/ical_sync/test_classifier.py`
- `tests/ical_sync/test_subject_map.py`
- `tests/ical_sync/test_extractor.py`
- `tests/ical_sync/test_service.py`
- `tests/test_events_page_sync.py`
- `tests/test_profile_edit_ical_field.py`

### Modified
- `pyproject.toml` — add `icalendar` dep
- `src/school_test_engine/ui/_subjects.py` — extend `SUBJECTS_ALL`
- `src/school_test_engine/storage/users_repo.py` — three new sentinel kwargs
- `src/school_test_engine/storage/events_repo.py` — `external_uid`/`external_source` on `create`, new `list_with_external_uid` + `update_by_external_uid`
- `src/school_test_engine/ui/pages/profile_edit.py` — Schulkalender-Section with `QPlainTextEdit`
- `src/school_test_engine/ui/pages/events.py` — sync button + status label + toast
- `src/school_test_engine/ui/main_window.py` — `events_synced` signal + `_maybe_trigger_background_sync`
- `src/school_test_engine/ui/pages/menu.py` — connect to `events_synced`
- `src/school_test_engine/ui/pages/grades.py` — connect to `events_synced`

---

## Task Overview

1. Migration 011 + schema test
2. Extend `SUBJECTS_ALL` (`ui/_subjects.py`)
3. `users_repo` — three new sentinel kwargs
4. `events_repo` — extended `create`, `list_with_external_uid`, `update_by_external_uid`
5. Add `icalendar` dep to pyproject + smoke test
6. `fetcher.py` — HTTP layer with `FeedFetchError`
7. `parser.py` — VEVENT → `RawVEvent` dataclass
8. `classifier.py` — `is_klausur_event`
9. `subject_map.py` — `DEFAULT_SUBJECT_MAP` + `map_subject`
10. `extractor.py` — `RawVEvent` → `EventRecord`
11. `service.py` — `sync_feed`, `_diff`, `_apply`, `SyncResult`
12. `ical_sync/__init__.py` — public API surface
13. `SyncWorker` (`ui/sync_worker.py`)
14. ProfileEditPage — iCal-Feed-URL field
15. EventsPage — sync button + status + toast + injectable runner
16. MainWindow — `events_synced` signal + auto-sync hook + page wiring
17. Final acceptance check

---

### Task 1: Migration 011 + schema test

**Files:**
- Create: `src/school_test_engine/storage/migrations/011_phase15_ical_sync.sql`
- Test: `tests/test_migration_011.py`

- [ ] **Step 1: Write the failing schema test**

```python
# tests/test_migration_011.py
"""Phase 15: schema migration adds iCal-sync columns + index."""
from __future__ import annotations

import sqlite3

from school_test_engine.storage import run_migrations


def _columns(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _index_names(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA index_list({table})")}


def test_users_has_ical_columns(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    cols = _columns(conn, "users")
    assert "ical_feed_url" in cols
    assert "ical_last_sync_at" in cols
    assert "ical_last_sync_summary" in cols


def test_scheduled_events_has_external_columns(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    cols = _columns(conn, "scheduled_events")
    assert "external_uid" in cols
    assert "external_source" in cols


def test_unique_index_on_external_uid(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    assert "idx_events_external_uid" in _index_names(conn, "scheduled_events")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_011.py -v`
Expected: FAIL (KeyError or "ical_feed_url" not in cols).

- [ ] **Step 3: Write the migration SQL**

```sql
-- src/school_test_engine/storage/migrations/011_phase15_ical_sync.sql
ALTER TABLE users ADD COLUMN ical_feed_url TEXT;
ALTER TABLE users ADD COLUMN ical_last_sync_at TEXT;
ALTER TABLE users ADD COLUMN ical_last_sync_summary TEXT;

ALTER TABLE scheduled_events ADD COLUMN external_uid TEXT;
ALTER TABLE scheduled_events ADD COLUMN external_source TEXT;

CREATE UNIQUE INDEX idx_events_external_uid
  ON scheduled_events(user_id, external_uid)
  WHERE external_uid IS NOT NULL;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migration_011.py -v`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/migrations/011_phase15_ical_sync.sql tests/test_migration_011.py
git commit -m "feat(phase15): migration 011 adds iCal-sync columns + unique index"
```

---

### Task 2: Extend SUBJECTS_ALL

**Files:**
- Modify: `src/school_test_engine/ui/_subjects.py`
- Test: `tests/test_subjects_all.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_subjects_all.py
"""Phase 15: SUBJECTS_ALL is extended to cover Clemens' Realschule subjects."""
from __future__ import annotations

from school_test_engine.ui._subjects import SUBJECTS_ALL


def test_includes_main_subjects():
    for s in ["Mathe", "Englisch", "Deutsch"]:
        assert s in SUBJECTS_ALL


def test_includes_natural_sciences():
    for s in ["Bio", "Physik", "Chemie"]:
        assert s in SUBJECTS_ALL


def test_includes_humanities_and_others():
    for s in ["Geschichte", "Geographie", "Politik und Wirtschaft", "Religion", "Musik"]:
        assert s in SUBJECTS_ALL


def test_eleven_subjects_total():
    assert len(SUBJECTS_ALL) == 11
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_subjects_all.py -v`
Expected: FAIL on "Deutsch" not in SUBJECTS_ALL.

- [ ] **Step 3: Extend SUBJECTS_ALL**

Replace the contents of `src/school_test_engine/ui/_subjects.py`:

```python
SUBJECTS_ALL = [
    "Mathe", "Englisch", "Deutsch",
    "Bio", "Physik", "Chemie",
    "Geschichte", "Geographie", "Politik und Wirtschaft",
    "Religion", "Musik",
]
```

- [ ] **Step 4: Run all tests**

Run: `pytest -x`
Expected: all 283+ green plus the 4 new ones. Other tests that filter SUBJECTS_ALL should still pass because the list is purely additive.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/_subjects.py tests/test_subjects_all.py
git commit -m "feat(phase15): extend SUBJECTS_ALL with Deutsch, Geographie, PoWi, Religion, Musik"
```

---

### Task 3: users_repo — three new sentinel kwargs

**Files:**
- Modify: `src/school_test_engine/storage/users_repo.py`
- Test: extend the existing migration test inline

- [ ] **Step 1: Write the failing test**

Add to `tests/test_migration_011.py`:

```python
import pytest
from school_test_engine.storage import users_repo


def test_users_repo_update_user_persists_ical_fields(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    uid = users_repo.create_user(conn, name="Test")
    users_repo.update_user(
        conn, uid,
        ical_feed_url="https://example.com/feed",
        ical_last_sync_at="2026-05-15T10:00:00",
        ical_last_sync_summary='{"added":1}',
    )
    row = users_repo.get_user(conn, uid)
    assert row["ical_feed_url"] == "https://example.com/feed"
    assert row["ical_last_sync_at"] == "2026-05-15T10:00:00"
    assert row["ical_last_sync_summary"] == '{"added":1}'


def test_users_repo_update_user_clears_ical_fields_with_none(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    run_migrations(conn)
    uid = users_repo.create_user(conn, name="Test")
    users_repo.update_user(conn, uid, ical_feed_url="https://x.com/feed")
    users_repo.update_user(conn, uid, ical_feed_url=None)
    row = users_repo.get_user(conn, uid)
    assert row["ical_feed_url"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_011.py::test_users_repo_update_user_persists_ical_fields -v`
Expected: FAIL (TypeError: unexpected keyword argument 'ical_feed_url').

- [ ] **Step 3: Extend update_user signature**

In `src/school_test_engine/storage/users_repo.py`, locate the `update_user` function. Add three new sentinel parameters after `show_keyboard_hints` and the matching field-builder lines (use `_SENTINEL` like the existing nullable kwargs):

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
) -> None:
    # ... existing field-builder code ...
    if ical_feed_url is not _SENTINEL:
        fields.append("ical_feed_url = ?"); values.append(ical_feed_url)
    if ical_last_sync_at is not _SENTINEL:
        fields.append("ical_last_sync_at = ?"); values.append(ical_last_sync_at)
    if ical_last_sync_summary is not _SENTINEL:
        fields.append("ical_last_sync_summary = ?"); values.append(ical_last_sync_summary)
    # ... rest unchanged ...
```

Insert the three new `if`-blocks right before the `if not fields: return` check.

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_migration_011.py -v`
Expected: 5 PASSED.

Run full suite: `pytest`
Expected: 287+ green.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/users_repo.py tests/test_migration_011.py
git commit -m "feat(phase15): users_repo.update_user accepts ical_feed_url/last_sync_at/summary"
```

---

### Task 4: events_repo — extended create + new helpers

**Files:**
- Modify: `src/school_test_engine/storage/events_repo.py`
- Test: `tests/test_events_repo.py` (extend existing)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_events_repo.py`:

```python
def test_create_persists_external_uid_and_source(conn, user_id):
    eid = events_repo.create(
        conn, user_id, "Mathe", "klassenarbeit", "2026-06-01",
        external_uid="abc-klausur-1@host", external_source="schulportal_hessen",
    )
    row = events_repo.get(conn, eid)
    assert row["external_uid"] == "abc-klausur-1@host"
    assert row["external_source"] == "schulportal_hessen"


def test_list_with_external_uid_returns_only_synced_events(conn, user_id):
    events_repo.create(conn, user_id, "Mathe", "klassenarbeit", "2026-06-01")  # manual
    events_repo.create(
        conn, user_id, "Englisch", "klassenarbeit", "2026-06-08",
        external_uid="x-klausur-1@h", external_source="schulportal_hessen",
    )
    rows = events_repo.list_with_external_uid(conn, user_id)
    assert len(rows) == 1
    assert rows[0]["external_uid"] == "x-klausur-1@h"


def test_update_by_external_uid_changes_only_synced_fields(conn, user_id):
    eid = events_repo.create(
        conn, user_id, "Englisch", "klassenarbeit", "2026-06-08",
        topics=["Vocab", "Grammar"], note="manuell ergänzt",
        external_uid="x-klausur-1@h", external_source="schulportal_hessen",
    )
    events_repo.update_by_external_uid(
        conn, user_id, "x-klausur-1@h",
        subject="Englisch", kind="klassenarbeit", event_date="2026-06-15",
    )
    row = events_repo.get(conn, eid)
    assert row["event_date"] == "2026-06-15"
    # Topics + note must be untouched:
    import json
    assert json.loads(row["topics"]) == ["Vocab", "Grammar"]
    assert row["note"] == "manuell ergänzt"
```

Add at the top of the test file (if not already present):

```python
import pytest
from school_test_engine.storage import events_repo, run_migrations, users_repo


@pytest.fixture
def user_id(conn):
    return users_repo.create_user(conn, name="Tester")
```

If a `conn` fixture is already in the file, reuse it; otherwise add it next to `user_id`:

```python
@pytest.fixture
def conn(tmp_path):
    import sqlite3
    db = tmp_path / "t.db"
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    run_migrations(c)
    yield c
    c.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_events_repo.py -v`
Expected: 3 new tests FAIL (unexpected kwarg `external_uid`).

- [ ] **Step 3: Extend events_repo**

In `src/school_test_engine/storage/events_repo.py`:

```python
def create(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str,
    kind: str,
    event_date: str,
    *,
    topics: Iterable[str] | None = None,
    note: str | None = None,
    external_uid: str | None = None,
    external_source: str | None = None,
) -> int:
    topics_json = json.dumps(list(topics) if topics else [])
    cur = conn.execute(
        """
        INSERT INTO scheduled_events
            (user_id, subject, kind, event_date, topics, note, external_uid, external_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, subject, kind, event_date, topics_json, note, external_uid, external_source),
    )
    conn.commit()
    eid = cur.lastrowid
    assert eid is not None
    return eid


def list_with_external_uid(
    conn: sqlite3.Connection, user_id: int
) -> list[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT * FROM scheduled_events
        WHERE user_id = ? AND external_uid IS NOT NULL
        """,
        (user_id,),
    )
    return cur.fetchall()


def update_by_external_uid(
    conn: sqlite3.Connection,
    user_id: int,
    external_uid: str,
    *,
    subject: str,
    kind: str,
    event_date: str,
) -> None:
    conn.execute(
        """
        UPDATE scheduled_events
        SET subject = ?, kind = ?, event_date = ?
        WHERE user_id = ? AND external_uid = ?
        """,
        (subject, kind, event_date, user_id, external_uid),
    )
    conn.commit()
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_events_repo.py -v`
Expected: all green (existing + 3 new).

Full: `pytest`
Expected: 290+ green.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/events_repo.py tests/test_events_repo.py
git commit -m "feat(phase15): events_repo supports external_uid + list/update by it"
```

---

### Task 5: Add icalendar dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dep**

Open `pyproject.toml`. In the `dependencies = [...]` block, add `"icalendar>=5.0"`:

```toml
dependencies = [
    "PySide6>=6.7",
    "pydantic>=2.6",
    "icalendar>=5.0",
]
```

- [ ] **Step 2: Install it**

Run: `pip install -e .`
Expected: icalendar installed alongside its `pytz` transitive dep.

- [ ] **Step 3: Smoke-test the import**

Run: `python -c "import icalendar; print(icalendar.__version__)"`
Expected: a version number prints (e.g. `5.0.11`).

- [ ] **Step 4: Run full test suite**

Run: `pytest`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build(phase15): add icalendar dependency"
```

---

### Task 6: ical_sync/fetcher.py — HTTP layer

**Files:**
- Create: `src/school_test_engine/ical_sync/__init__.py` (empty placeholder)
- Create: `src/school_test_engine/ical_sync/fetcher.py`
- Create: `tests/ical_sync/__init__.py` (empty)
- Test: `tests/ical_sync/test_fetcher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ical_sync/test_fetcher.py
"""Phase 15: fetcher wraps urllib with FeedFetchError translation."""
from __future__ import annotations

import urllib.error

import pytest

from school_test_engine.ical_sync import fetcher


def test_fetch_feed_returns_bytes(monkeypatch):
    class _FakeResponse:
        status = 200
        def read(self):
            return b"BEGIN:VCALENDAR\nEND:VCALENDAR\n"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def _fake_urlopen(req, timeout):
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    result = fetcher.fetch_feed("https://x.example/feed")
    assert result.startswith(b"BEGIN:VCALENDAR")


def test_fetch_feed_raises_on_non_200(monkeypatch):
    class _FakeResponse:
        status = 401
        def read(self):
            return b""
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda r, timeout: _FakeResponse())
    with pytest.raises(fetcher.FeedFetchError) as e:
        fetcher.fetch_feed("https://x.example/feed")
    assert "401" in str(e.value)


def test_fetch_feed_translates_urlerror(monkeypatch):
    def _raise(req, timeout):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    with pytest.raises(fetcher.FeedFetchError) as e:
        fetcher.fetch_feed("https://x.example/feed")
    assert "Netzwerk-Fehler" in str(e.value)


def test_fetch_feed_translates_timeout(monkeypatch):
    def _raise(req, timeout):
        raise TimeoutError()

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    with pytest.raises(fetcher.FeedFetchError) as e:
        fetcher.fetch_feed("https://x.example/feed")
    assert "Timeout" in str(e.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ical_sync/test_fetcher.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create the empty package + write fetcher**

```python
# src/school_test_engine/ical_sync/__init__.py
# (empty — public API surface comes later in Task 12)
```

```python
# tests/ical_sync/__init__.py
# (empty)
```

```python
# src/school_test_engine/ical_sync/fetcher.py
"""HTTP layer for fetching iCal feeds. Translates urllib errors into FeedFetchError."""
from __future__ import annotations

import urllib.error
import urllib.request


class FeedFetchError(Exception):
    """Raised for any failure during feed download — network, HTTP status, timeout."""


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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ical_sync/test_fetcher.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ical_sync/__init__.py src/school_test_engine/ical_sync/fetcher.py tests/ical_sync/__init__.py tests/ical_sync/test_fetcher.py
git commit -m "feat(phase15): fetcher.fetch_feed with FeedFetchError translation"
```

---

### Task 7: ical_sync/parser.py — VEVENT extraction

**Files:**
- Create: `src/school_test_engine/ical_sync/parser.py`
- Create: `tests/fixtures/schulkalender_mini.ics`
- Test: `tests/ical_sync/test_parser.py`

- [ ] **Step 1: Write the fixture**

```
# tests/fixtures/schulkalender_mini.ics
BEGIN:VCALENDAR
VERSION:2.0
PRODID:Schulportal Hessen | PaedOrg | start.schulportal.hessen.de
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:Test Mini Feed
X-WR-TIMEZONE:Europe/Berlin
BEGIN:VEVENT
DTSTAMP:20260515T080000
DTSTART;VALUE=DATE:20250707
DTEND;VALUE=DATE:20250816
SUMMARY:Sommerferien
DESCRIPTION:
CATEGORIES:Ferien
UID:20240409T113106-3788@6115.start.schulportal.hessen.de
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20260515T080000
DTSTART;TZID=Europe/Berlin:20260310T093500
DTEND;TZID=Europe/Berlin:20260310T110500
SUMMARY:Mathematik R8b Arbeit
DESCRIPTION:Arbeit in Mathematik R8b (082M07-R)
CATEGORIES:Arbeiten
UID:20010101T000001-klausur-9084-14627-2026-03-10@6115.start.schulportal.hessen.de
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20260515T080000
DTSTART;TZID=Europe/Berlin:20260417T112500
DTEND;TZID=Europe/Berlin:20260417T125500
SUMMARY:Religion - evangelisch Lernkontrolle
DESCRIPTION:Lernkontrolle in Religion - evangelisch (REV8_GcRab01-)
CATEGORIES:Arbeiten
UID:20010101T000001-klausur-9064-14535-2026-04-17@6115.start.schulportal.hessen.de
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20260515T080000
DTSTART;TZID=Europe/Berlin:20260428T112500
DTEND;TZID=Europe/Berlin:20260428T125500
SUMMARY:Mathematikwettbewerb Klassenstufe 8
DESCRIPTION:
CATEGORIES:Arbeiten
UID:20250920T153052-5927@6115.start.schulportal.hessen.de
END:VEVENT
END:VCALENDAR
```

The fixture has four events: one Ferien, two KAs (Mathe + Religion), one non-KA in `CATEGORIES:Arbeiten` (Mathewettbewerb has no `-klausur-` in UID — confirms classifier doesn't fall back to category).

- [ ] **Step 2: Write the failing test**

```python
# tests/ical_sync/test_parser.py
"""Phase 15: parser turns ICS bytes into RawVEvent dataclasses."""
from __future__ import annotations

from pathlib import Path

import pytest

from school_test_engine.ical_sync import parser


FIXTURE = Path(__file__).parent.parent / "fixtures" / "schulkalender_mini.ics"


def test_parse_returns_all_vevents():
    events = parser.parse_events(FIXTURE.read_bytes())
    assert len(events) == 4


def test_parse_extracts_uid_summary_description():
    events = parser.parse_events(FIXTURE.read_bytes())
    mathe = next(e for e in events if "Mathematik R8b" in e.summary)
    assert "klausur-9084" in mathe.uid
    assert mathe.summary == "Mathematik R8b Arbeit"
    assert mathe.description == "Arbeit in Mathematik R8b (082M07-R)"


def test_parse_dtstart_date_only_returns_iso_date():
    events = parser.parse_events(FIXTURE.read_bytes())
    sommer = next(e for e in events if e.summary == "Sommerferien")
    assert sommer.dtstart_date == "2025-07-07"


def test_parse_dtstart_with_tz_returns_iso_date():
    events = parser.parse_events(FIXTURE.read_bytes())
    mathe = next(e for e in events if "Mathematik R8b" in e.summary)
    assert mathe.dtstart_date == "2026-03-10"


def test_parse_extracts_categories():
    events = parser.parse_events(FIXTURE.read_bytes())
    sommer = next(e for e in events if e.summary == "Sommerferien")
    assert "Ferien" in sommer.categories


def test_parse_invalid_bytes_raises():
    with pytest.raises(ValueError):
        parser.parse_events(b"not an iCal file")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/ical_sync/test_parser.py -v`
Expected: FAIL (ModuleNotFoundError on `parser`).

- [ ] **Step 4: Write the parser**

```python
# src/school_test_engine/ical_sync/parser.py
"""Wrap the icalendar library and emit stdlib-only RawVEvent dataclasses.

This isolates the rest of the app from the icalendar API — if the library
ever needs to be swapped, only this file changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import icalendar


@dataclass(frozen=True)
class RawVEvent:
    uid: str
    summary: str
    description: str
    dtstart_date: str          # always ISO YYYY-MM-DD, normalized
    categories: tuple[str, ...]


def parse_events(ics_bytes: bytes) -> list[RawVEvent]:
    """Parse ics bytes. Raises ValueError when input is not a valid iCal."""
    try:
        cal = icalendar.Calendar.from_ical(ics_bytes)
    except ValueError:
        raise
    except Exception as e:    # icalendar throws various lower-level exceptions
        raise ValueError(f"Invalid iCal data: {e}") from e

    out: list[RawVEvent] = []
    for comp in cal.walk("VEVENT"):
        dtstart = comp.get("DTSTART")
        if dtstart is None:
            continue
        dt = dtstart.dt
        iso_date = (
            dt.date().isoformat() if isinstance(dt, datetime) else dt.isoformat()
        )
        out.append(RawVEvent(
            uid=str(comp.get("UID", "")),
            summary=str(comp.get("SUMMARY", "")),
            description=str(comp.get("DESCRIPTION", "")),
            dtstart_date=iso_date,
            categories=_categories(comp),
        ))
    return out


def _categories(comp) -> tuple[str, ...]:
    cat = comp.get("CATEGORIES")
    if cat is None:
        return ()
    # icalendar returns a vCategory object — its .cats attribute holds the list
    if hasattr(cat, "cats"):
        return tuple(str(c) for c in cat.cats)
    return (str(cat),)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/ical_sync/test_parser.py -v`
Expected: 6 PASSED.

If `test_parse_invalid_bytes_raises` fails because `icalendar` doesn't throw `ValueError` for `b"not an iCal file"` but returns an empty Calendar, swap the input for something that triggers a parse error like `b"BEGIN:VCALENDAR\nINVALID"`. Run again and confirm green.

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ical_sync/parser.py tests/fixtures/schulkalender_mini.ics tests/ical_sync/test_parser.py
git commit -m "feat(phase15): parser.parse_events wraps icalendar into RawVEvent"
```

---

### Task 8: ical_sync/classifier.py

**Files:**
- Create: `src/school_test_engine/ical_sync/classifier.py`
- Test: `tests/ical_sync/test_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ical_sync/test_classifier.py
"""Phase 15: classifier detects '-klausur-' marker in UID."""
from __future__ import annotations

from school_test_engine.ical_sync.classifier import is_klausur_event
from school_test_engine.ical_sync.parser import RawVEvent


def _ev(uid: str) -> RawVEvent:
    return RawVEvent(uid=uid, summary="", description="", dtstart_date="2026-01-01", categories=())


def test_klausur_uid_returns_true():
    e = _ev("20010101T000001-klausur-9084-14627-2026-03-10@6115.start.schulportal.hessen.de")
    assert is_klausur_event(e) is True


def test_ferien_uid_returns_false():
    e = _ev("20240409T113106-3788@6115.start.schulportal.hessen.de")
    assert is_klausur_event(e) is False


def test_empty_uid_returns_false():
    e = _ev("")
    assert is_klausur_event(e) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ical_sync/test_classifier.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write the classifier**

```python
# src/school_test_engine/ical_sync/classifier.py
"""Identify Klassenarbeit/Lernkontrolle events by their UID marker.

The Schulportal-Hessen feed encodes school assessments with a stable
'-klausur-' substring in the UID. This is more reliable than parsing
CATEGORIES (which mixes AGs and assessments) or SUMMARY (which has
heterogeneous prose).
"""
from __future__ import annotations

from .parser import RawVEvent

_KLAUSUR_MARKER = "-klausur-"


def is_klausur_event(event: RawVEvent) -> bool:
    return _KLAUSUR_MARKER in event.uid
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ical_sync/test_classifier.py -v`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ical_sync/classifier.py tests/ical_sync/test_classifier.py
git commit -m "feat(phase15): classifier.is_klausur_event matches UID marker"
```

---

### Task 9: ical_sync/subject_map.py

**Files:**
- Create: `src/school_test_engine/ical_sync/subject_map.py`
- Test: `tests/ical_sync/test_subject_map.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ical_sync/test_subject_map.py
"""Phase 15: subject_map normalizes feed-side subject strings to app-side."""
from __future__ import annotations

from school_test_engine.ical_sync.subject_map import map_subject


def test_mathematik_maps_to_mathe():
    assert map_subject("Mathematik") == "Mathe"


def test_religion_variants_map_to_religion():
    assert map_subject("Religion - evangelisch") == "Religion"
    assert map_subject("Religion - katholisch") == "Religion"
    assert map_subject("Religion - ethisch") == "Religion"
    assert map_subject("Ethik") == "Religion"


def test_erdkunde_maps_to_geographie():
    assert map_subject("Erdkunde") == "Geographie"


def test_powi_maps_to_politik_und_wirtschaft():
    assert map_subject("PoWi") == "Politik und Wirtschaft"
    assert map_subject("Sozialkunde") == "Politik und Wirtschaft"


def test_unknown_subject_passthrough():
    assert map_subject("Englisch") == "Englisch"
    assert map_subject("Deutsch") == "Deutsch"
    assert map_subject("Musik") == "Musik"


def test_strips_whitespace():
    assert map_subject("  Mathematik  ") == "Mathe"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ical_sync/test_subject_map.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write subject_map**

```python
# src/school_test_engine/ical_sync/subject_map.py
"""Map raw subject strings from the iCal feed to the app's canonical names.

Unknown subjects pass through unchanged — the UI Subject-Combo is editable,
so unmapped names land in the DB as-is and the user can rename later.
"""
from __future__ import annotations

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
    cleaned = raw.strip()
    return DEFAULT_SUBJECT_MAP.get(cleaned, cleaned)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ical_sync/test_subject_map.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ical_sync/subject_map.py tests/ical_sync/test_subject_map.py
git commit -m "feat(phase15): subject_map.map_subject with default Hessen mappings"
```

---

### Task 10: ical_sync/extractor.py

**Files:**
- Create: `src/school_test_engine/ical_sync/extractor.py`
- Test: `tests/ical_sync/test_extractor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ical_sync/test_extractor.py
"""Phase 15: extractor parses DESCRIPTION into (subject, kind) + applies subject_map."""
from __future__ import annotations

from school_test_engine.ical_sync.extractor import EventRecord, to_event_record
from school_test_engine.ical_sync.parser import RawVEvent


def _ev(description: str, uid: str = "x-klausur-1@h") -> RawVEvent:
    return RawVEvent(
        uid=uid, summary="", description=description,
        dtstart_date="2026-03-10", categories=(),
    )


def test_arbeit_in_mathematik_yields_klassenarbeit_mathe():
    rec = to_event_record(_ev("Arbeit in Mathematik R8b (082M07-R)"))
    assert rec is not None
    assert rec.kind == "klassenarbeit"
    assert rec.subject == "Mathe"
    assert rec.event_date == "2026-03-10"


def test_lernkontrolle_in_chemie_yields_test_chemie():
    rec = to_event_record(_ev("Lernkontrolle in Chemie R8b (082CH02-R)"))
    assert rec is not None
    assert rec.kind == "test"
    assert rec.subject == "Chemie"


def test_klausur_yields_klausur_kind():
    rec = to_event_record(_ev("Klausur in Mathematik Q1 (Q1M01-G)"))
    assert rec is not None
    assert rec.kind == "klausur"


def test_religion_evangelisch_is_mapped_to_religion():
    rec = to_event_record(_ev("Lernkontrolle in Religion - evangelisch (REV8_GcRab01-)"))
    assert rec is not None
    assert rec.subject == "Religion"


def test_unknown_description_format_returns_none():
    rec = to_event_record(_ev("Some unrelated text"))
    assert rec is None


def test_empty_description_returns_none():
    rec = to_event_record(_ev(""))
    assert rec is None


def test_record_keeps_full_uid():
    rec = to_event_record(_ev(
        "Arbeit in Mathematik R8b (082M07-R)",
        uid="20010101T000001-klausur-9084-14627-2026-03-10@6115.start.schulportal.hessen.de",
    ))
    assert rec is not None
    assert rec.external_uid.endswith("@6115.start.schulportal.hessen.de")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ical_sync/test_extractor.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write extractor**

```python
# src/school_test_engine/ical_sync/extractor.py
"""Turn a RawVEvent into an EventRecord by parsing DESCRIPTION.

DESCRIPTION format from Schulportal-Hessen:
    "Arbeit in Mathematik R8b (082M07-R)"
    "Lernkontrolle in Chemie R8b (082CH02-R)"
    "Klausur in Mathematik Q1 (Q1M01-G)"
    "Lernkontrolle in Religion - evangelisch (REV8_GcRab01-)"

If DESCRIPTION doesn't match, we return None (caller increments `skipped`).
No SUMMARY-fallback — YAGNI until evidence demands it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .parser import RawVEvent
from .subject_map import map_subject


@dataclass(frozen=True)
class EventRecord:
    external_uid: str
    subject: str         # post-mapping (e.g. "Mathe", not "Mathematik")
    kind: str            # 'klassenarbeit' | 'klausur' | 'test'
    event_date: str      # ISO YYYY-MM-DD


_DESC_PATTERN = re.compile(
    r"^(?P<kind_label>Arbeit|Lernkontrolle|Klausur)\s+in\s+"
    r"(?P<subject>.+?)"
    r"(?:\s+R\d+[a-z]?|\s+Q\d+)?"     # optional class designator
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
        return None
    return EventRecord(
        external_uid=event.uid,
        subject=map_subject(m.group("subject").strip()),
        kind=_KIND_MAP[m.group("kind_label")],
        event_date=event.dtstart_date,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ical_sync/test_extractor.py -v`
Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ical_sync/extractor.py tests/ical_sync/test_extractor.py
git commit -m "feat(phase15): extractor.to_event_record parses DESCRIPTION + applies subject_map"
```

---

### Task 11: ical_sync/service.py — diff + apply + sync_feed

**Files:**
- Create: `src/school_test_engine/ical_sync/service.py`
- Test: `tests/ical_sync/test_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ical_sync/test_service.py
"""Phase 15: service.sync_feed orchestrates fetch + parse + diff + apply."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from school_test_engine.ical_sync import service
from school_test_engine.ical_sync.fetcher import FeedFetchError
from school_test_engine.storage import assessments_repo, events_repo, run_migrations, users_repo


FIXTURE = Path(__file__).parent.parent / "fixtures" / "schulkalender_mini.ics"


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def user_with_feed(conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x.example/feed")
    return uid


def _make_fetcher(ics_bytes: bytes):
    return lambda url, timeout=10.0: ics_bytes


def test_sync_inserts_klausuren_only(conn, user_with_feed, monkeypatch):
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    result = service.sync_feed(conn, user_with_feed)
    assert result.error is None
    assert result.added == 2          # 2 klausur-events in fixture
    assert result.updated == 0
    assert result.deleted == 0
    rows = events_repo.list_with_external_uid(conn, user_with_feed)
    subjects = sorted(r["subject"] for r in rows)
    assert subjects == ["Mathe", "Religion"]


def test_sync_is_idempotent(conn, user_with_feed, monkeypatch):
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    service.sync_feed(conn, user_with_feed)
    result = service.sync_feed(conn, user_with_feed)
    assert result.added == 0
    assert result.updated == 0
    assert result.deleted == 0


def test_sync_updates_changed_date_keeps_topics(conn, user_with_feed, monkeypatch):
    # First sync — establish baseline
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    service.sync_feed(conn, user_with_feed)
    # User adds topics manually to the Mathe-KA
    mathe = next(r for r in events_repo.list_with_external_uid(conn, user_with_feed) if r["subject"] == "Mathe")
    events_repo.update(conn, mathe["id"], topics=["Lineare Gleichungen", "Brüche"])
    # Second sync with date shifted in fixture content
    shifted = FIXTURE.read_bytes().replace(b"20260310", b"20260317")
    monkeypatch.setattr(service, "_fetch", _make_fetcher(shifted))
    result = service.sync_feed(conn, user_with_feed)
    assert result.updated == 1
    mathe_after = next(r for r in events_repo.list_with_external_uid(conn, user_with_feed) if r["subject"] == "Mathe")
    assert mathe_after["event_date"] == "2026-03-17"
    assert json.loads(mathe_after["topics"]) == ["Lineare Gleichungen", "Brüche"]


def test_sync_deletes_removed_event_without_note(conn, user_with_feed, monkeypatch):
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    service.sync_feed(conn, user_with_feed)
    # Now remove the Religion-KA from feed entirely
    reduced = FIXTURE.read_bytes()
    # Delete the entire Religion VEVENT block from the bytes
    start = reduced.find(b"BEGIN:VEVENT\nDTSTAMP:20260515T080000\nDTSTART;TZID=Europe/Berlin:20260417")
    end = reduced.find(b"END:VEVENT", start) + len(b"END:VEVENT\n")
    reduced = reduced[:start] + reduced[end:]
    monkeypatch.setattr(service, "_fetch", _make_fetcher(reduced))
    result = service.sync_feed(conn, user_with_feed)
    assert result.deleted == 1
    rows = events_repo.list_with_external_uid(conn, user_with_feed)
    assert len(rows) == 1


def test_sync_keeps_removed_event_with_note(conn, user_with_feed, monkeypatch):
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    service.sync_feed(conn, user_with_feed)
    # Attach an assessment to the Religion-KA
    religion = next(r for r in events_repo.list_with_external_uid(conn, user_with_feed) if r["subject"] == "Religion")
    assessments_repo.create(
        conn, user_with_feed, subject="Religion",
        grade=2.0, category="schriftlich",
        date="2026-04-17", event_id=religion["id"],
    )
    # Now remove Religion from the feed
    reduced = FIXTURE.read_bytes()
    start = reduced.find(b"BEGIN:VEVENT\nDTSTAMP:20260515T080000\nDTSTART;TZID=Europe/Berlin:20260417")
    end = reduced.find(b"END:VEVENT", start) + len(b"END:VEVENT\n")
    reduced = reduced[:start] + reduced[end:]
    monkeypatch.setattr(service, "_fetch", _make_fetcher(reduced))
    result = service.sync_feed(conn, user_with_feed)
    assert result.deleted == 0
    rows = events_repo.list_with_external_uid(conn, user_with_feed)
    assert len(rows) == 2  # both still present


def test_sync_returns_error_on_network_failure(conn, user_with_feed, monkeypatch):
    def _raise(url, timeout=10.0):
        raise FeedFetchError("Netzwerk-Fehler: no route")
    monkeypatch.setattr(service, "_fetch", _raise)
    result = service.sync_feed(conn, user_with_feed)
    assert result.error is not None
    assert "Netzwerk-Fehler" in result.error
    # Persisted summary holds the error
    row = users_repo.get_user(conn, user_with_feed)
    assert row["ical_last_sync_summary"] is not None
    assert "Netzwerk-Fehler" in row["ical_last_sync_summary"]


def test_sync_no_url_returns_error(conn):
    uid = users_repo.create_user(conn, name="NoFeed")
    result = service.sync_feed(conn, uid)
    assert "Keine Feed-URL" in (result.error or "")


def test_sync_persists_last_sync_at_on_success(conn, user_with_feed, monkeypatch):
    monkeypatch.setattr(service, "_fetch", _make_fetcher(FIXTURE.read_bytes()))
    service.sync_feed(conn, user_with_feed)
    row = users_repo.get_user(conn, user_with_feed)
    assert row["ical_last_sync_at"] is not None
    assert row["ical_last_sync_at"].startswith("20")  # ISO date prefix
```

- [ ] **Step 2: Check `assessments_repo.create` signature**

Run: `grep -A 10 "^def create" src/school_test_engine/storage/assessments_repo.py`

Note the actual argument names. The test fixture above uses `subject=, grade=, category=, date=, event_id=`. Adjust the test's `assessments_repo.create(...)` call if the real signature differs (e.g. `assessment_date=` instead of `date=`).

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/ical_sync/test_service.py -v`
Expected: FAIL (ModuleNotFoundError on `service`).

- [ ] **Step 4: Write service**

```python
# src/school_test_engine/ical_sync/service.py
"""Orchestrate fetch → parse → classify → extract → diff → apply.

`_fetch` is a module-level indirection so tests can monkeypatch it cleanly
without touching urllib.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from ..storage import assessments_repo, events_repo, users_repo
from . import classifier, extractor, fetcher, parser
from .extractor import EventRecord
from .fetcher import FeedFetchError


@dataclass(frozen=True)
class SyncResult:
    added: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0
    error: str | None = None
    synced_at: str = ""


# Indirection for tests
_fetch = fetcher.fetch_feed


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


def _diff(conn, user_id, feed_records: list[EventRecord]):
    feed_by_uid = {r.external_uid: r for r in feed_records}
    db_rows = events_repo.list_with_external_uid(conn, user_id)
    db_by_uid = {r["external_uid"]: r for r in db_rows}

    adds = [r for uid, r in feed_by_uid.items() if uid not in db_by_uid]
    updates = [
        (r, db_by_uid[r.external_uid])
        for uid, r in feed_by_uid.items()
        if uid in db_by_uid and _has_changes(r, db_by_uid[uid])
    ]
    delete_candidates = [row for uid, row in db_by_uid.items() if uid not in feed_by_uid]
    deletes = [
        row for row in delete_candidates
        if assessments_repo.find_by_event(conn, row["id"]) is None
    ]
    return adds, updates, deletes


def _has_changes(rec: EventRecord, db_row) -> bool:
    return (
        rec.event_date != db_row["event_date"]
        or rec.subject != db_row["subject"]
        or rec.kind != db_row["kind"]
    )


def _apply(conn, user_id, adds, updates, deletes):
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


def _persist_summary(conn, user_id, added, updated, deleted, skipped) -> SyncResult:
    now = datetime.now().isoformat(timespec="seconds")
    summary_json = json.dumps({
        "added": added, "updated": updated, "deleted": deleted, "skipped": skipped, "error": None,
    })
    users_repo.update_user(
        conn, user_id,
        ical_last_sync_at=now,
        ical_last_sync_summary=summary_json,
    )
    return SyncResult(added=added, updated=updated, deleted=deleted, skipped=skipped, synced_at=now)


def _persist_error(conn, user_id, error_msg: str) -> SyncResult:
    now = datetime.now().isoformat(timespec="seconds")
    summary_json = json.dumps({"added": 0, "updated": 0, "deleted": 0, "skipped": 0, "error": error_msg})
    users_repo.update_user(
        conn, user_id,
        ical_last_sync_at=now,
        ical_last_sync_summary=summary_json,
    )
    return SyncResult(error=error_msg, synced_at=now)
```

- [ ] **Step 5: Run service tests**

Run: `pytest tests/ical_sync/test_service.py -v`
Expected: 8 PASSED.

If `assessments_repo.create` signature doesn't match the test, adjust the test call (only). Don't refactor the repo.

- [ ] **Step 6: Run full suite**

Run: `pytest`
Expected: 308+ green.

- [ ] **Step 7: Commit**

```bash
git add src/school_test_engine/ical_sync/service.py tests/ical_sync/test_service.py
git commit -m "feat(phase15): service.sync_feed with diff/apply + idempotent UID matching"
```

---

### Task 12: Public API surface

**Files:**
- Modify: `src/school_test_engine/ical_sync/__init__.py`

- [ ] **Step 1: Export public symbols**

Replace the empty `__init__.py`:

```python
# src/school_test_engine/ical_sync/__init__.py
"""iCal-Sync domain package — public API."""
from .fetcher import FeedFetchError
from .service import SyncResult, sync_feed

__all__ = ["FeedFetchError", "SyncResult", "sync_feed"]
```

- [ ] **Step 2: Smoke-test imports**

Run: `python -c "from school_test_engine.ical_sync import sync_feed, SyncResult, FeedFetchError; print('ok')"`
Expected: `ok`

Run: `pytest`
Expected: still 308+ green.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ical_sync/__init__.py
git commit -m "feat(phase15): expose sync_feed/SyncResult/FeedFetchError as public API"
```

---

### Task 13: SyncWorker (ui/sync_worker.py)

**Files:**
- Create: `src/school_test_engine/ui/sync_worker.py`

- [ ] **Step 1: Write the worker (no test — covered via DI in Task 15)**

```python
# src/school_test_engine/ui/sync_worker.py
"""QThread-friendly wrapper around ical_sync.service.sync_feed.

The worker opens its own SQLite connection inside `run()` because the
default-mode SQLite connection is not thread-safe to share. The result is
emitted via the `finished` signal on the originating thread.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..ical_sync import sync_feed


class SyncWorker(QObject):
    finished = Signal(object)  # emits a SyncResult

    def __init__(self, db_path: Path | str, user_id: int):
        super().__init__()
        self.db_path = Path(db_path)
        self.user_id = user_id

    def run(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            result = sync_feed(conn, self.user_id)
        finally:
            conn.close()
        self.finished.emit(result)
```

- [ ] **Step 2: Smoke-test import**

Run: `python -c "from school_test_engine.ui.sync_worker import SyncWorker; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/sync_worker.py
git commit -m "feat(phase15): SyncWorker — QObject wrapper opens own DB connection per thread"
```

---

### Task 14: ProfileEditPage — iCal-Feed-URL field

**Files:**
- Modify: `src/school_test_engine/ui/pages/profile_edit.py`
- Test: `tests/test_profile_edit_ical_field.py`

- [ ] **Step 1: Read current profile_edit.py**

Run: `wc -l src/school_test_engine/ui/pages/profile_edit.py`
Then `grep -n "school_year_edit\|school_name_edit\|style_edit\|_save" src/school_test_engine/ui/pages/profile_edit.py`

Confirm two anchors:
- The end of the Schul-Kontext-section (after `school_year_edit` setup).
- The `_save()` method that calls `users_repo.update_user`.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_profile_edit_ical_field.py
"""Phase 15: ProfileEditPage has an iCal-Feed-URL field that persists to users.ical_feed_url."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from school_test_engine.storage import run_migrations, users_repo
from school_test_engine.ui.pages.profile_edit import ProfileEditPage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    run_migrations(c)
    yield c
    c.close()


class _StubWindow:
    def __init__(self, conn):
        self.conn = conn
        self.active_user_id = None
        self.navigated_back = False
    def _navigate_back(self):
        self.navigated_back = True
    def show_picker(self):
        self._navigate_back()
    def show_profile_manager(self):
        self._navigate_back()
    def show_menu(self):
        self._navigate_back()


def test_page_persists_ical_feed_url(app, conn, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    uid = users_repo.create_user(conn, name="Clemens")
    win = _StubWindow(conn)
    page = ProfileEditPage(win, user_id=uid, return_to="manager")
    page.ical_feed_url_edit.setPlainText("https://start.schulportal.hessen.de/feed?t=abc")
    page._save()
    row = users_repo.get_user(conn, uid)
    assert row["ical_feed_url"] == "https://start.schulportal.hessen.de/feed?t=abc"


def test_page_loads_existing_ical_feed_url(app, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x.example/feed")
    win = _StubWindow(conn)
    page = ProfileEditPage(win, user_id=uid, return_to="manager")
    assert page.ical_feed_url_edit.toPlainText() == "https://x.example/feed"


def test_page_clears_ical_feed_url_when_emptied(app, conn, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x.example/feed")
    win = _StubWindow(conn)
    page = ProfileEditPage(win, user_id=uid, return_to="manager")
    page.ical_feed_url_edit.setPlainText("")
    page._save()
    row = users_repo.get_user(conn, uid)
    assert row["ical_feed_url"] is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_profile_edit_ical_field.py -v`
Expected: FAIL (`AttributeError: ical_feed_url_edit`).

- [ ] **Step 4: Add the field to ProfileEditPage**

In `src/school_test_engine/ui/pages/profile_edit.py`:

Add the import (if not already there):

```python
from PySide6.QtWidgets import QPlainTextEdit
```

Locate the form construction. After the Schul-Kontext-section closes (look for the last `addRow("Schuljahr:", ...)` or similar), add a new section:

```python
# --- Schulkalender ---
from school_test_engine.ui.design import tokens  # if not yet imported
form.addRow(_section_label("Schulkalender"))

self.ical_feed_url_edit = QPlainTextEdit()
self.ical_feed_url_edit.setPlaceholderText(
    "https://start.schulportal.hessen.de/kalender.php?..."
)
self.ical_feed_url_edit.setMaximumHeight(80)
form.addRow("iCal-Feed-URL:", self.ical_feed_url_edit)

hint = QLabel("Findest du im Schulportal unter „Kalender → Export → iCal\".")
hint.setStyleSheet("color: #b3a98e; font-size: 9pt;")
hint.setWordWrap(True)
form.addRow("", hint)
```

If a `_section_label` helper doesn't exist in this file, just use `QLabel(...)` styled with the eyebrow class — match what's currently used for the "Schul-Kontext"-section header.

In the load-from-DB block (where existing fields are filled), add:

```python
self.ical_feed_url_edit.setPlainText(user_row["ical_feed_url"] or "")
```

In `_save()`, in the `users_repo.update_user(...)` call, add the new kwarg. The URL is stripped; empty becomes `None` to clear:

```python
raw_url = self.ical_feed_url_edit.toPlainText().strip()
users_repo.update_user(
    conn, self.user_id,
    # ... existing kwargs ...
    ical_feed_url=(raw_url if raw_url else None),
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_profile_edit_ical_field.py -v`
Expected: 3 PASSED.

Run all profile_edit tests: `pytest tests/ -k "profile_edit" -v`
Expected: all green (existing + new).

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/pages/profile_edit.py tests/test_profile_edit_ical_field.py
git commit -m "feat(phase15): ProfileEditPage gets iCal-Feed-URL field"
```

---

### Task 15: EventsPage — Sync button, status, toast, injectable runner

**Files:**
- Modify: `src/school_test_engine/ui/pages/events.py`
- Test: `tests/test_events_page_sync.py`

- [ ] **Step 1: Read current events.py**

Run: `wc -l src/school_test_engine/ui/pages/events.py`
Then: `grep -n "class EventsPage\|_build_header\|def reload" src/school_test_engine/ui/pages/events.py`

Locate three anchors: class signature, the header-construction code, and the reload-method.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_events_page_sync.py
"""Phase 15: EventsPage has a Sync button + injectable runner + status label."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.ical_sync.service import SyncResult
from school_test_engine.storage import run_migrations, users_repo
from school_test_engine.ui.pages.events import EventsPage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    run_migrations(c)
    yield c
    c.close()


class _StubWindow:
    def __init__(self, conn):
        self.conn = conn
        self.active_user_id = None


def test_sync_button_calls_runner(app, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x/feed")
    win = _StubWindow(conn)
    win.active_user_id = uid
    calls: list = []
    def fake_runner(callback):
        calls.append("called")
        callback(SyncResult(added=3))
    page = EventsPage(win, sync_runner=fake_runner)
    page.sync_button.click()
    assert calls == ["called"]


def test_sync_button_disabled_during_run(app, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x/feed")
    win = _StubWindow(conn)
    win.active_user_id = uid
    captured: list = []
    def fake_runner(callback):
        captured.append(callback)
    page = EventsPage(win, sync_runner=fake_runner)
    page.sync_button.click()
    assert not page.sync_button.isEnabled()
    captured[0](SyncResult(added=3))
    assert page.sync_button.isEnabled()


def test_sync_result_shows_counts(app, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x/feed")
    win = _StubWindow(conn)
    win.active_user_id = uid
    page = EventsPage(win, sync_runner=lambda cb: cb(SyncResult(added=3, updated=1)))
    page.sync_button.click()
    text = page.sync_status_label.text()
    assert "3 neu" in text
    assert "1 verschoben" in text


def test_sync_result_shows_error(app, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    users_repo.update_user(conn, uid, ical_feed_url="https://x/feed")
    win = _StubWindow(conn)
    win.active_user_id = uid
    page = EventsPage(win, sync_runner=lambda cb: cb(SyncResult(error="Timeout")))
    page.sync_button.click()
    assert "Timeout" in page.sync_status_label.text()


def test_sync_button_hidden_when_no_url(app, conn):
    uid = users_repo.create_user(conn, name="Clemens")
    # No ical_feed_url set
    win = _StubWindow(conn)
    win.active_user_id = uid
    page = EventsPage(win)
    assert not page.sync_button.isEnabled() or not page.sync_button.isVisible()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_events_page_sync.py -v`
Expected: FAIL (AttributeError: `sync_button`).

- [ ] **Step 4: Extend EventsPage**

In `src/school_test_engine/ui/pages/events.py`:

Add imports at the top:

```python
from PySide6.QtCore import QThread
from ..sync_worker import SyncWorker
from ...ical_sync import SyncResult
from ...config import db_path
from ...storage import users_repo
```

Extend `__init__` to accept the runner. Inside the constructor body, after super().__init__:

```python
def __init__(self, window, *, sync_runner=None):
    super().__init__()
    self.window = window
    self._sync_runner = sync_runner   # None = use default QThread runner
    self._sync_thread: QThread | None = None
    self._sync_worker: SyncWorker | None = None
    # ... existing setup code ...
```

In the header construction (where `+ Neuer Termin` button lives), add the Sync button + status label. Example pattern:

```python
self.sync_button = QPushButton("↻ Synchronisieren")
self.sync_button.setObjectName("text")
self.sync_button.clicked.connect(self._start_sync)
header_row.addWidget(self.sync_button)

self.sync_status_label = QLabel("")
self.sync_status_label.setStyleSheet("color: #6e6457; font-size: 9pt;")
self.sync_status_label.setWordWrap(True)
# Layout: place beneath the button row
outer_layout.addWidget(self.sync_status_label)
```

(Adjust the exact layout objects to match what's already in `events.py` — `header_row` and `outer_layout` are example names.)

Add new methods to `EventsPage`:

```python
def _has_feed_url(self) -> bool:
    uid = self.window.active_user_id
    if not uid:
        return False
    row = users_repo.get_user(self.window.conn, uid)
    return bool(row and row["ical_feed_url"])

def _update_sync_button_visibility(self) -> None:
    enabled = self._has_feed_url()
    self.sync_button.setEnabled(enabled and self._sync_thread is None)
    if not enabled:
        self.sync_status_label.setText("Schulkalender nicht verknüpft")
    else:
        self._refresh_status_from_db()

def _refresh_status_from_db(self) -> None:
    import json
    uid = self.window.active_user_id
    row = users_repo.get_user(self.window.conn, uid)
    if not row or not row["ical_last_sync_at"]:
        self.sync_status_label.setText("Noch nicht synchronisiert")
        return
    summary = json.loads(row["ical_last_sync_summary"] or "{}")
    if summary.get("error"):
        self.sync_status_label.setText(f"Letzter Sync fehlgeschlagen: {summary['error']}")
    else:
        parts = []
        if summary.get("added"):  parts.append(f"{summary['added']} neu")
        if summary.get("updated"): parts.append(f"{summary['updated']} verschoben")
        if summary.get("deleted"): parts.append(f"{summary['deleted']} entfernt")
        suffix = " · " + ", ".join(parts) if parts else " · bereits aktuell"
        self.sync_status_label.setText(f"Zuletzt synchronisiert{suffix}")

def _start_sync(self) -> None:
    if self._sync_thread is not None:
        return
    self.sync_button.setEnabled(False)
    self.sync_status_label.setText("Synchronisiere…")
    if self._sync_runner is not None:
        # Test-injected synchronous runner
        self._sync_runner(self._on_sync_done)
    else:
        self._sync_thread = QThread()
        self._sync_worker = SyncWorker(db_path(), self.window.active_user_id)
        self._sync_worker.moveToThread(self._sync_thread)
        self._sync_thread.started.connect(self._sync_worker.run)
        self._sync_worker.finished.connect(self._on_sync_done)
        self._sync_worker.finished.connect(self._sync_thread.quit)
        self._sync_thread.finished.connect(self._sync_thread.deleteLater)
        self._sync_thread.start()

def _on_sync_done(self, result: SyncResult) -> None:
    self._sync_thread = None
    self._sync_worker = None
    self.sync_button.setEnabled(True)
    if result.error:
        self.sync_status_label.setText(f"Sync fehlgeschlagen: {result.error}")
        return
    parts = []
    if result.added:  parts.append(f"{result.added} neu")
    if result.updated: parts.append(f"{result.updated} verschoben")
    if result.deleted: parts.append(f"{result.deleted} entfernt")
    suffix = ", ".join(parts) if parts else "bereits aktuell"
    self.sync_status_label.setText(f"Zuletzt synchronisiert · {suffix}")
    self.reload()
```

At the very end of `__init__` add:

```python
self._update_sync_button_visibility()
```

And in the existing `reload()` method, add at the end:

```python
self._update_sync_button_visibility()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_events_page_sync.py -v`
Expected: 5 PASSED.

- [ ] **Step 6: Run full suite**

Run: `pytest`
Expected: 316+ green.

- [ ] **Step 7: Commit**

```bash
git add src/school_test_engine/ui/pages/events.py tests/test_events_page_sync.py
git commit -m "feat(phase15): EventsPage gets sync button + status label + injectable runner"
```

---

### Task 16: MainWindow — events_synced signal + auto-sync hook + page wiring

**Files:**
- Modify: `src/school_test_engine/ui/main_window.py`
- Modify: `src/school_test_engine/ui/pages/menu.py`
- Modify: `src/school_test_engine/ui/pages/grades.py`
- Modify: `src/school_test_engine/ui/pages/events.py` (emit on sync done)

- [ ] **Step 1: Add events_synced signal + auto-sync helper**

In `src/school_test_engine/ui/main_window.py`, near the other class-level Signals (e.g. `user_changed`), add:

```python
class MainWindow(QMainWindow):
    user_changed = Signal(int)
    events_synced = Signal()    # NEW
    # ...
```

Find `_on_user_changed` (or equivalent — the method called when active_user_id flips). At the end of its body, add:

```python
self._maybe_trigger_background_sync(user_id)
```

Add the new helper plus a private threaded launcher. Place near the bottom of the class:

```python
def _maybe_trigger_background_sync(self, user_id: int) -> None:
    from datetime import datetime, timedelta
    from .sync_worker import SyncWorker
    from PySide6.QtCore import QThread
    from ..config import db_path
    from ..storage import users_repo

    if self._bg_sync_thread is not None:
        return
    row = users_repo.get_user(self.conn, user_id)
    if not row or not row["ical_feed_url"]:
        return
    last = row["ical_last_sync_at"]
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if datetime.now() - last_dt < timedelta(hours=24):
                return
        except ValueError:
            pass  # malformed timestamp → re-sync

    self._bg_sync_thread = QThread()
    self._bg_sync_worker = SyncWorker(db_path(), user_id)
    self._bg_sync_worker.moveToThread(self._bg_sync_thread)
    self._bg_sync_thread.started.connect(self._bg_sync_worker.run)
    self._bg_sync_worker.finished.connect(self._on_bg_sync_done)
    self._bg_sync_worker.finished.connect(self._bg_sync_thread.quit)
    self._bg_sync_thread.finished.connect(self._bg_sync_thread.deleteLater)
    self._bg_sync_thread.start()

def _on_bg_sync_done(self, result) -> None:
    self._bg_sync_thread = None
    self._bg_sync_worker = None
    # Only re-render listeners when something actually changed
    if not result.error and (result.added or result.updated or result.deleted):
        self.events_synced.emit()
```

In `__init__`, initialize the new attributes:

```python
self._bg_sync_thread = None
self._bg_sync_worker = None
```

In `closeEvent`, clean up running threads:

```python
def closeEvent(self, event):
    if self._bg_sync_thread is not None:
        self._bg_sync_thread.quit()
        self._bg_sync_thread.wait(2000)
    super().closeEvent(event)
```

(If `closeEvent` doesn't exist yet, add one with the body above; if it exists, prepend the two lines before its current body.)

- [ ] **Step 2: Have EventsPage emit on successful sync**

In `events.py`'s `_on_sync_done`, add at the bottom of the success branch (before `self.reload()`):

```python
if hasattr(self.window, "events_synced"):
    self.window.events_synced.emit()
```

- [ ] **Step 3: Wire MenuPage to reload on events_synced**

In `src/school_test_engine/ui/pages/menu.py`, locate the `__init__` where `window` is captured. After connecting other signals (e.g. `user_changed`), add:

```python
if hasattr(window, "events_synced"):
    window.events_synced.connect(self.reload)
```

(Ensure `reload` exists; if MenuPage uses a different render method, connect to that instead.)

- [ ] **Step 4: Wire GradesPage to reload on events_synced**

In `src/school_test_engine/ui/pages/grades.py`, same pattern:

```python
if hasattr(window, "events_synced"):
    window.events_synced.connect(self.reload)
```

- [ ] **Step 5: Run all tests**

Run: `pytest`
Expected: still 316+ green. No new tests required — the signal wiring is straight-line Qt plumbing.

- [ ] **Step 6: Manual smoke test**

Run: `./run.sh`
1. Open the Profil-Edit-Seite for any profile, paste the real Schulportal-URL, save.
2. Open Termine-Seite → click "↻ Synchronisieren" → expect 12 KAs to appear, status label updates.
3. Close + reopen the app → on user-selection, auto-sync triggers silently (no UI block).
4. Open Termine again → no second sync within 24h; click manual button → should still work and show "bereits aktuell".

- [ ] **Step 7: Commit**

```bash
git add src/school_test_engine/ui/main_window.py src/school_test_engine/ui/pages/menu.py src/school_test_engine/ui/pages/grades.py src/school_test_engine/ui/pages/events.py
git commit -m "feat(phase15): MainWindow events_synced signal + 24h auto-sync hook"
```

---

### Task 17: Final acceptance

**Files:** none new — verification only.

- [ ] **Step 1: Full test run**

Run: `pytest -v`
Expected: 308 → ~316 PASSED, 0 FAILED. Note exact count.

- [ ] **Step 2: Check git log**

Run: `git log --oneline phase15-start..HEAD` (or just `git log --oneline | head -20`)
Expected: ~13 commits in `feat(phase15)`/`build(phase15)` style.

- [ ] **Step 3: Schema sanity-check on a real db**

Run:
```bash
python -c "
import sqlite3
from school_test_engine.config import db_path
from school_test_engine.storage import run_migrations
c = sqlite3.connect(db_path())
c.row_factory = sqlite3.Row
run_migrations(c)
cols = [r['name'] for r in c.execute('PRAGMA table_info(scheduled_events)')]
print('scheduled_events:', cols)
ucols = [r['name'] for r in c.execute('PRAGMA table_info(users)')]
print('users:', [c for c in ucols if c.startswith('ical_')])
"
```

Expected: `external_uid` and `external_source` in scheduled_events; `ical_feed_url`, `ical_last_sync_at`, `ical_last_sync_summary` in users.

- [ ] **Step 4: Live feed dry-run (optional but recommended)**

Run:
```bash
python -c "
from school_test_engine.config import db_path
from school_test_engine.storage import connect, users_repo
from school_test_engine.ical_sync import sync_feed
conn = connect(db_path())
uid = next(r['id'] for r in users_repo.list_users(conn) if r['ical_feed_url'])
print(sync_feed(conn, uid))
"
```

Expected: `SyncResult(added=12, updated=0, deleted=0, skipped=0, error=None, synced_at='2026-…')` on the first call against the real feed; `(0, 0, 0)` on the second.

- [ ] **Step 5: Update the project_overview memory**

Edit `/home/matthias/.claude/projects/-home-matthias-Dokumente-Claude-ai-projects-school-test-engine/memory/project_overview.md` — append Phase-15-summary to the list of completed phases. Keep the same style as Phase 14.

- [ ] **Step 6: Final commit + tag (optional)**

Nothing left to commit if Steps 1-4 are clean and the memory edit isn't tracked in git. If anything was changed, commit as `chore(phase15): acceptance cleanup`.

---

## Self-Review Notes

**Spec coverage:**
- Section 4 (architecture) → Tasks 6-13 cover every module
- Section 5 (data model) → Tasks 1, 2, 3, 4 cover migration, subjects, repos
- Section 6 (pipeline) → Tasks 6-11 each map to one pipeline module
- Section 7 (UI) → Tasks 14, 15, 16 cover ProfileEdit, Events, MainWindow hook
- Section 8 (error handling) → Tested in Task 11 (`test_sync_returns_error_on_network_failure`) and Task 15 (`test_sync_result_shows_error`)
- Section 9 (edge cases) → Idempotency and update+keep-topics in Task 11; threading lifecycle in Task 16
- Section 10 (testing) → 25 new tests distributed across Tasks 1, 2, 3, 4, 6-11, 14, 15

**Placeholder scan:** No TBD/TODO. All code is concrete. The only conditional steps say "if X then Y" with specific instructions for both paths (e.g. Task 7 Step 5).

**Type consistency:** `SyncResult`, `EventRecord`, `RawVEvent` names used identically across Tasks 7, 10, 11, 12, 13, 15, 16. `_fetch` indirection appears only in Task 11 (service) and is monkeypatched in service tests.

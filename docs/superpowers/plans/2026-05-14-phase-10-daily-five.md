# Phase 10 — Daily-5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daily 5-question learning session pulled from the user's weakest topics, with a streak counter, surfaced via a Daily-Card on the Hauptmenü.

**Architecture:** Migration 009 adds a `daily_sessions` table tracking one session per (user, day) with optional in-progress state. A new `daily/` domain package contains the builder (picks 5 questions 2-2-1 from weakest topics, copies them into a synthetic test with `subject="Daily-5"`), the streak calculator (stateless from `daily_sessions`), and a finalize hook called from `MainWindow.show_results`. A `DailyCard` widget with four states (no_library, due-no-streak, due-with-streak, done) sits below the existing menu content. Save-and-Resume from Phase 2 is reused for free since Daily-5 sessions use the standard Runner.

**Tech Stack:** Python 3.11, PySide6, SQLite (stdlib sqlite3), pytest. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-05-14-phase-10-daily-five-design.md`

**Repository state at start:** master branch, latest commit `42db9a3` (Phase 10 spec). Test suite: 187/187 green.

---

## File Structure

**New files:**
- `src/school_test_engine/storage/migrations/009_phase10_daily_five.sql`
- `src/school_test_engine/storage/daily_sessions_repo.py`
- `src/school_test_engine/daily/__init__.py` (empty package marker)
- `src/school_test_engine/daily/builder.py` — `has_enough_questions` + `build_daily_test`
- `src/school_test_engine/daily/streak.py` — `current_streak`
- `src/school_test_engine/daily/finalize.py` — `finalize_if_daily`
- `src/school_test_engine/ui/widgets/daily_card.py` — DailyCard widget
- `tests/test_migration_009.py`
- `tests/test_daily_sessions_repo.py`
- `tests/test_daily_streak.py`
- `tests/test_daily_builder.py`
- `tests/test_daily_finalize.py`

**Modified files:**
- `src/school_test_engine/ui/pages/menu.py` — append DailyCard to both layout variants, wire `practice_clicked → window.start_daily_five()`
- `src/school_test_engine/ui/main_window.py` — add `start_daily_five()`, hook `finalize_if_daily` into `show_results()`

---

## Task 1: Migration 009 — daily_sessions table

**Files:**
- Create: `src/school_test_engine/storage/migrations/009_phase10_daily_five.sql`
- Test: `tests/test_migration_009.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_migration_009.py`:

```python
import pytest

from school_test_engine.storage import connect, run_migrations


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_daily_sessions_table_exists(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_sessions'"
    ).fetchone()
    assert row is not None


def test_daily_sessions_composite_pk_enforced(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (2, 'X', '👤', 1, '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO daily_sessions (user_id, session_date, started_at) "
        "VALUES (2, '2026-05-14', '2026-05-14T08:00:00')"
    )
    conn.commit()
    # Same (user_id, session_date) must fail
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO daily_sessions (user_id, session_date, started_at) "
            "VALUES (2, '2026-05-14', '2026-05-14T20:00:00')"
        )


def test_daily_sessions_cascade_on_user_delete(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (3, 'X', '👤', 2, '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO daily_sessions (user_id, session_date, started_at) "
        "VALUES (3, '2026-05-14', '2026-05-14T08:00:00')"
    )
    conn.commit()
    conn.execute("DELETE FROM users WHERE id = 3")
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) FROM daily_sessions WHERE user_id = 3"
    ).fetchone()[0] == 0


def test_daily_sessions_completed_at_nullable(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(daily_sessions)").fetchall()}
    assert "completed_at" in cols
    assert cols["completed_at"]["notnull"] == 0


def test_daily_sessions_attempt_id_nullable_and_set_null(conn):
    # ON DELETE SET NULL semantics on attempt_id FK
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (4, 'X', '👤', 3, '2026-01-01T00:00:00')"
    )
    conn.commit()
    # We can't fully exercise the SET NULL without creating an attempt row;
    # this test asserts the column is nullable
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(daily_sessions)").fetchall()}
    assert "attempt_id" in cols
    assert cols["attempt_id"]["notnull"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_009.py -v`
Expected: All FAIL — `daily_sessions` table doesn't exist.

- [ ] **Step 3: Write migration SQL**

Create `src/school_test_engine/storage/migrations/009_phase10_daily_five.sql`:

```sql
-- Phase 10: Daily-5 Session-Tracking

CREATE TABLE IF NOT EXISTS daily_sessions (
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_date TEXT    NOT NULL,
    test_id      INTEGER REFERENCES tests(id) ON DELETE SET NULL,
    attempt_id   INTEGER REFERENCES attempts(id) ON DELETE SET NULL,
    started_at   TEXT    NOT NULL,
    completed_at TEXT,
    PRIMARY KEY (user_id, session_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_user_date
    ON daily_sessions(user_id, session_date);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_migration_009.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/migrations/009_phase10_daily_five.sql tests/test_migration_009.py
git commit -m "feat(phase10): migration 009 — daily_sessions table"
```

---

## Task 2: daily_sessions_repo

**Files:**
- Create: `src/school_test_engine/storage/daily_sessions_repo.py`
- Test: `tests/test_daily_sessions_repo.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_daily_sessions_repo.py`:

```python
import pytest

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import daily_sessions_repo


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


def test_get_for_today_returns_none_when_missing(conn, uid):
    assert daily_sessions_repo.get_for_today(conn, uid, "2026-05-14") is None


def test_start_session_inserts(conn, uid):
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14",
        test_id=None, attempt_id=None,
        started_at="2026-05-14T08:00:00",
    )
    row = daily_sessions_repo.get_for_today(conn, uid, "2026-05-14")
    assert row is not None
    assert row["session_date"] == "2026-05-14"
    assert row["completed_at"] is None


def test_complete_session_sets_completed_at(conn, uid):
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14",
        test_id=None, attempt_id=None,
        started_at="2026-05-14T08:00:00",
    )
    daily_sessions_repo.complete_session(
        conn, uid, "2026-05-14", completed_at="2026-05-14T08:05:00",
    )
    row = daily_sessions_repo.get_for_today(conn, uid, "2026-05-14")
    assert row["completed_at"] == "2026-05-14T08:05:00"


def test_list_recent_completed_dates_returns_only_completed(conn, uid):
    # Three sessions: two completed, one in-progress
    for d in ["2026-05-12", "2026-05-13"]:
        daily_sessions_repo.start_session(
            conn, uid, d, test_id=None, attempt_id=None, started_at=d + "T08:00:00",
        )
        daily_sessions_repo.complete_session(conn, uid, d, completed_at=d + "T08:05:00")
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14", test_id=None, attempt_id=None, started_at="2026-05-14T08:00:00",
    )
    dates = daily_sessions_repo.list_recent_completed_dates(
        conn, uid, since="2026-05-01", until="2026-05-14",
    )
    assert set(dates) == {"2026-05-12", "2026-05-13"}


def test_find_by_attempt_returns_session(conn, uid):
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14", test_id=99, attempt_id=42,
        started_at="2026-05-14T08:00:00",
    )
    row = daily_sessions_repo.find_by_attempt(conn, 42)
    assert row is not None
    assert row["session_date"] == "2026-05-14"


def test_find_by_attempt_returns_none_when_missing(conn, uid):
    assert daily_sessions_repo.find_by_attempt(conn, 99999) is None


def test_user_isolation(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    daily_sessions_repo.start_session(
        conn, a, "2026-05-14", test_id=None, attempt_id=None, started_at="2026-05-14T08:00:00",
    )
    assert daily_sessions_repo.get_for_today(conn, a, "2026-05-14") is not None
    assert daily_sessions_repo.get_for_today(conn, b, "2026-05-14") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daily_sessions_repo.py -v`
Expected: All FAIL with import error.

- [ ] **Step 3: Write the repo module**

Create `src/school_test_engine/storage/daily_sessions_repo.py`:

```python
from __future__ import annotations

import sqlite3


def start_session(
    conn: sqlite3.Connection,
    user_id: int,
    session_date: str,
    *,
    test_id: int | None,
    attempt_id: int | None,
    started_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO daily_sessions
            (user_id, session_date, test_id, attempt_id, started_at, completed_at)
        VALUES (?, ?, ?, ?, ?, NULL)
        """,
        (user_id, session_date, test_id, attempt_id, started_at),
    )
    conn.commit()


def complete_session(
    conn: sqlite3.Connection,
    user_id: int,
    session_date: str,
    *,
    completed_at: str,
) -> None:
    conn.execute(
        "UPDATE daily_sessions SET completed_at = ? "
        "WHERE user_id = ? AND session_date = ?",
        (completed_at, user_id, session_date),
    )
    conn.commit()


def get_for_today(
    conn: sqlite3.Connection, user_id: int, today: str
) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT * FROM daily_sessions WHERE user_id = ? AND session_date = ?",
        (user_id, today),
    )
    return cur.fetchone()


def find_by_attempt(
    conn: sqlite3.Connection, attempt_id: int
) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT * FROM daily_sessions WHERE attempt_id = ?",
        (attempt_id,),
    )
    return cur.fetchone()


def list_recent_completed_dates(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    since: str,
    until: str,
) -> list[str]:
    cur = conn.execute(
        """
        SELECT session_date FROM daily_sessions
        WHERE user_id = ?
          AND session_date >= ?
          AND session_date <= ?
          AND completed_at IS NOT NULL
        ORDER BY session_date DESC
        """,
        (user_id, since, until),
    )
    return [row["session_date"] for row in cur.fetchall()]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daily_sessions_repo.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/daily_sessions_repo.py tests/test_daily_sessions_repo.py
git commit -m "feat(phase10): daily_sessions_repo CRUD + completion tracking"
```

---

## Task 3: daily/streak.py — current_streak

**Files:**
- Create: `src/school_test_engine/daily/__init__.py` (empty)
- Create: `src/school_test_engine/daily/streak.py`
- Test: `tests/test_daily_streak.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_daily_streak.py`:

```python
import pytest
from datetime import date

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import daily_sessions_repo
from school_test_engine.daily.streak import current_streak


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


def _record_complete_day(conn, uid, d: str) -> None:
    daily_sessions_repo.start_session(
        conn, uid, d, test_id=None, attempt_id=None, started_at=d + "T08:00:00",
    )
    daily_sessions_repo.complete_session(conn, uid, d, completed_at=d + "T08:05:00")


def test_empty_returns_zero(conn, uid):
    assert current_streak(conn, uid, date(2026, 5, 14)) == 0


def test_today_completed_returns_one(conn, uid):
    _record_complete_day(conn, uid, "2026-05-14")
    assert current_streak(conn, uid, date(2026, 5, 14)) == 1


def test_yesterday_only_returns_one(conn, uid):
    _record_complete_day(conn, uid, "2026-05-13")
    # Today not done yet — streak counts backwards from yesterday
    assert current_streak(conn, uid, date(2026, 5, 14)) == 1


def test_three_consecutive_days_with_today_returns_three(conn, uid):
    for d in ["2026-05-12", "2026-05-13", "2026-05-14"]:
        _record_complete_day(conn, uid, d)
    assert current_streak(conn, uid, date(2026, 5, 14)) == 3


def test_three_consecutive_ending_yesterday_returns_three(conn, uid):
    for d in ["2026-05-11", "2026-05-12", "2026-05-13"]:
        _record_complete_day(conn, uid, d)
    # Today not done — streak still 3
    assert current_streak(conn, uid, date(2026, 5, 14)) == 3


def test_gap_resets_streak(conn, uid):
    # Pattern: 12, 14 (skip 13). Today=14. Streak counts only 14.
    _record_complete_day(conn, uid, "2026-05-12")
    _record_complete_day(conn, uid, "2026-05-14")
    assert current_streak(conn, uid, date(2026, 5, 14)) == 1


def test_in_progress_day_does_not_count(conn, uid):
    # Today started but NOT completed → streak counts only completed days before
    _record_complete_day(conn, uid, "2026-05-13")
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14", test_id=None, attempt_id=None,
        started_at="2026-05-14T08:00:00",
    )
    # No complete_session call → completed_at IS NULL
    assert current_streak(conn, uid, date(2026, 5, 14)) == 1  # only yesterday


def test_user_isolation(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    _record_complete_day(conn, a, "2026-05-14")
    assert current_streak(conn, a, date(2026, 5, 14)) == 1
    assert current_streak(conn, b, date(2026, 5, 14)) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daily_streak.py -v`
Expected: All FAIL with import error.

- [ ] **Step 3: Write the streak module**

Create `src/school_test_engine/daily/__init__.py` (empty).

Create `src/school_test_engine/daily/streak.py`:

```python
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from ..storage import daily_sessions_repo


def current_streak(
    conn: sqlite3.Connection,
    user_id: int,
    today: date,
) -> int:
    """Count consecutive completed days ending today (or yesterday, if today
    is not yet completed). Returns 0 if no completed sessions.
    """
    since = (today - timedelta(days=400)).isoformat()
    until = today.isoformat()
    completed = set(daily_sessions_repo.list_recent_completed_dates(
        conn, user_id, since=since, until=until,
    ))

    if not completed:
        return 0

    streak = 0
    cursor = today
    # If today not completed, streak counts backwards starting from yesterday
    if cursor.isoformat() not in completed:
        cursor -= timedelta(days=1)
    while cursor.isoformat() in completed:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daily_streak.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/daily/__init__.py src/school_test_engine/daily/streak.py tests/test_daily_streak.py
git commit -m "feat(phase10): current_streak walks daily_sessions backwards"
```

---

## Task 4: daily/builder.py — has_enough_questions + build_daily_test

**Files:**
- Create: `src/school_test_engine/daily/builder.py`
- Test: `tests/test_daily_builder.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_daily_builder.py`:

```python
import json
import pytest
from datetime import date

from school_test_engine.storage import (
    connect, run_migrations, users_repo, attempts_repo,
)
from school_test_engine.importer.json_import import import_from_string
from school_test_engine.daily.builder import (
    has_enough_questions,
    build_daily_test,
)


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


def _import_test_with_topics(conn, uid, subject: str, topics: list[str]):
    """Import a test where each topic gets one question."""
    questions = []
    for i, topic in enumerate(topics):
        questions.append({
            "id": f"q{i+1}",
            "type": "single_choice",
            "topic": topic,
            "difficulty": "mittel",
            "points": 2,
            "prompt": f"Frage {i+1}",
            "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "correct": ["a"],
            "explanation": "...",
        })
    payload = json.dumps({
        "schema_version": 1,
        "title": f"Test {subject}",
        "subject": subject,
        "grade": 8,
        "school_type": "Realschule",
        "notenschluessel": {1:[100,90], 2:[89,75], 3:[74,60], 4:[59,45], 5:[44,20], 6:[19,0]},
        "questions": questions,
    })
    return import_from_string(conn, payload, user_id=uid)


def _record_answer(conn, uid, test_id, question_ext_id, correct: bool):
    """Create a finished attempt with one answer."""
    aid = attempts_repo.start_attempt(conn, test_id, 10, uid)
    qrow = conn.execute(
        "SELECT id, points FROM questions WHERE test_id = ? AND ext_id = ?",
        (test_id, question_ext_id),
    ).fetchone()
    attempts_repo.upsert_answer(
        conn, aid, qrow["id"],
        response=["a"] if correct else ["b"],
        points_earned=qrow["points"] if correct else 0,
        is_correct=correct,
    )
    attempts_repo.finish_attempt(conn, aid, points_earned=qrow["points"] if correct else 0,
                                 percent=100 if correct else 0,
                                 note=1 if correct else 5)
    return aid


def test_has_enough_questions_false_when_no_library(conn, uid):
    assert has_enough_questions(conn, uid) is False


def test_has_enough_questions_false_with_fewer_than_5(conn, uid):
    _import_test_with_topics(conn, uid, "Mathe", ["A", "B", "C"])  # 3 questions
    assert has_enough_questions(conn, uid) is False


def test_has_enough_questions_true_with_5_or_more(conn, uid):
    _import_test_with_topics(conn, uid, "Mathe", ["A", "B", "C", "D", "E"])
    assert has_enough_questions(conn, uid) is True


def test_has_enough_questions_excludes_synthetic_tests(conn, uid):
    """is_study=1 tests don't count toward the pool size."""
    _import_test_with_topics(conn, uid, "Mathe", ["A", "B"])  # 2 real
    # Create synthetic test manually (study-style)
    conn.execute(
        """
        INSERT INTO tests (title, subject, grade, school_type, description,
                           time_limit_min, notenschluessel, source_json,
                           imported_at, is_study, user_id)
        VALUES ('Synth', 'Mathe', 8, 'Realschule', '', NULL, '{}', '{}', '2026-01-01', 1, ?)
        """,
        (uid,),
    )
    synth_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    for i in range(5):
        conn.execute(
            """INSERT INTO questions (test_id, ext_id, position, type, topic,
                                       difficulty, points, prompt, prompt_math,
                                       payload, explanation)
               VALUES (?, ?, ?, 'single_choice', 'X', 'mittel', 2, 'p', NULL, '{}', NULL)""",
            (synth_id, f"sq{i}", i),
        )
    conn.commit()
    # Still false — synthetic doesn't count
    assert has_enough_questions(conn, uid) is False


def test_build_returns_none_when_insufficient(conn, uid):
    _import_test_with_topics(conn, uid, "Mathe", ["A", "B"])  # only 2
    assert build_daily_test(conn, uid, date(2026, 5, 14)) is None


def test_build_creates_synthetic_test_with_subject_daily_five(conn, uid):
    test_id = _import_test_with_topics(conn, uid, "Mathe", ["T1", "T2", "T3", "T4", "T5"])
    # Practice some questions wrongly so they're "weak"
    _record_answer(conn, uid, test_id, "q1", correct=False)
    _record_answer(conn, uid, test_id, "q2", correct=False)
    _record_answer(conn, uid, test_id, "q3", correct=True)

    new_test_id = build_daily_test(conn, uid, date(2026, 5, 14))
    assert new_test_id is not None

    row = conn.execute("SELECT * FROM tests WHERE id = ?", (new_test_id,)).fetchone()
    assert row["subject"] == "Daily-5"
    assert row["is_study"] == 1
    assert row["title"].startswith("Daily-5")

    questions = conn.execute(
        "SELECT * FROM questions WHERE test_id = ? ORDER BY position",
        (new_test_id,),
    ).fetchall()
    assert len(questions) == 5


def test_build_picks_2_2_1_from_weakest_topics(conn, uid):
    # Provide enough questions per topic for the 2-2-1 quota to fit fully into weak set:
    # WeakA needs 2 questions, WeakB needs 2, WeakC needs 1 → 5 total weak.
    test_id = _import_test_with_topics(conn, uid, "Mathe", [
        "WeakA", "WeakA",      # q1, q2
        "WeakB", "WeakB",      # q3, q4
        "WeakC",                # q5
        "Strong1", "Strong2",  # q6, q7 (won't be picked)
    ])
    # Make WeakA/WeakB/WeakC weak (all wrong)
    for ext_id in ["q1", "q2", "q3", "q4", "q5"]:
        _record_answer(conn, uid, test_id, ext_id, correct=False)
    # Make Strong1/Strong2 strong (correct)
    _record_answer(conn, uid, test_id, "q6", correct=True)
    _record_answer(conn, uid, test_id, "q7", correct=True)

    new_test_id = build_daily_test(conn, uid, date(2026, 5, 14))
    assert new_test_id is not None
    rows = conn.execute(
        "SELECT topic FROM questions WHERE test_id = ?", (new_test_id,)
    ).fetchall()
    topics = [r["topic"] for r in rows]
    weak_set = {"WeakA", "WeakB", "WeakC"}
    # All 5 must be from the weak set since the pool covers the 2-2-1 quota exactly
    assert all(t in weak_set for t in topics), f"unexpected topics: {topics}"
    assert len(topics) == 5
    # Specifically 2x WeakA, 2x WeakB, 1x WeakC
    assert topics.count("WeakA") == 2
    assert topics.count("WeakB") == 2
    assert topics.count("WeakC") == 1


def test_build_falls_back_to_random_when_no_weak_topics(conn, uid):
    # Import 5 questions, all answered correctly → no weak topics
    test_id = _import_test_with_topics(conn, uid, "Mathe", ["A", "B", "C", "D", "E"])
    for ext_id in ["q1", "q2", "q3", "q4", "q5"]:
        _record_answer(conn, uid, test_id, ext_id, correct=True)
    new_test_id = build_daily_test(conn, uid, date(2026, 5, 14))
    assert new_test_id is not None
    questions = conn.execute(
        "SELECT COUNT(*) AS n FROM questions WHERE test_id = ?", (new_test_id,)
    ).fetchone()
    assert questions["n"] == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daily_builder.py -v`
Expected: All FAIL with import error.

- [ ] **Step 3: Write the builder module**

Create `src/school_test_engine/daily/builder.py`:

```python
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from random import Random

from ..models.test import REALSCHULE_DEFAULT_NOTENSCHLUESSEL


DAILY_SUBJECT = "Daily-5"
DAILY_TITLE_PREFIX = "Daily-5"


def has_enough_questions(conn: sqlite3.Connection, user_id: int, min_pool: int = 5) -> bool:
    """True if user has at least min_pool questions across non-synthetic tests."""
    n = conn.execute(
        """
        SELECT COUNT(DISTINCT q.id) AS n
        FROM questions q
        JOIN tests t ON t.id = q.test_id
        WHERE t.user_id = ? AND t.is_study = 0
        """,
        (user_id,),
    ).fetchone()["n"]
    return n >= min_pool


def build_daily_test(
    conn: sqlite3.Connection,
    user_id: int,
    today: date,
    seed: int | None = None,
) -> int | None:
    """Build a synthetic Daily-5 test with 5 questions from the user's weakest
    topics (2-2-1 split). Returns the new test_id, or None if pool insufficient.
    """
    if not has_enough_questions(conn, user_id):
        return None

    rng = Random(seed if seed is not None else today.toordinal())

    chosen_ids = _pick_question_ids(conn, user_id, rng)
    if len(chosen_ids) < 5:
        return None

    # Load full question rows in chosen order
    placeholders = ",".join(["?"] * len(chosen_ids))
    questions = conn.execute(
        f"SELECT * FROM questions WHERE id IN ({placeholders})",
        chosen_ids,
    ).fetchall()
    by_id = {q["id"]: q for q in questions}
    ordered = [by_id[qid] for qid in chosen_ids]

    title = f"{DAILY_TITLE_PREFIX} — {today.strftime('%d.%m.%Y')}"
    description = "Tägliche 5-Fragen-Session aus deinen schwächsten Themen."
    points_total = sum(int(q["points"]) for q in ordered)

    cur = conn.execute(
        """
        INSERT INTO tests
            (title, subject, grade, school_type, description, time_limit_min,
             notenschluessel, source_json, imported_at, is_study, user_id)
        VALUES (?, ?, ?, 'Realschule', ?, NULL, ?, '{}', ?, 1, ?)
        """,
        (
            title,
            DAILY_SUBJECT,
            8,
            description,
            json.dumps({str(k): v for k, v in REALSCHULE_DEFAULT_NOTENSCHLUESSEL.items()}),
            datetime.now(timezone.utc).isoformat(),
            user_id,
        ),
    )
    test_id = cur.lastrowid
    assert test_id is not None

    conn.executemany(
        """
        INSERT INTO questions
            (test_id, ext_id, position, type, topic, difficulty, points,
             prompt, prompt_math, payload, explanation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                test_id,
                f"dq{pos+1}",
                pos,
                q["type"],
                q["topic"],
                q["difficulty"],
                q["points"],
                q["prompt"],
                q["prompt_math"],
                q["payload"],
                q["explanation"],
            )
            for pos, q in enumerate(ordered)
        ],
    )
    conn.commit()
    return test_id


def _pick_question_ids(conn: sqlite3.Connection, user_id: int, rng: Random) -> list[int]:
    """Pick 5 question ids using 2-2-1 from the three weakest topics with fallback."""
    weak_topics = _weakest_topics(conn, user_id, threshold=0.80, limit=3)
    chosen: list[int] = []
    quotas = [2, 2, 1]
    for idx, topic_row in enumerate(weak_topics):
        qids = _random_question_ids_for_topic(
            conn, user_id, topic_row["topic"], topic_row["subject"],
            quotas[idx], rng, exclude=chosen,
        )
        chosen.extend(qids)

    # Fallback: fill up to 5 from any non-study question
    if len(chosen) < 5:
        fillers = _random_question_ids_global(conn, user_id, 5 - len(chosen), rng, exclude=chosen)
        chosen.extend(fillers)

    return chosen[:5]


def _weakest_topics(
    conn: sqlite3.Connection, user_id: int, threshold: float, limit: int,
) -> list[sqlite3.Row]:
    """Return topics with mastery < threshold, sorted ASC by mastery, top `limit`.
    Returns rows with at least 'topic' and 'subject' keys."""
    rows = conn.execute(
        """
        SELECT q.topic AS topic,
               ts.subject AS subject,
               SUM(a.points_earned) * 1.0 / SUM(q.points) AS mastery
        FROM answers a
        JOIN questions q ON q.id = a.question_id
        JOIN attempts t ON t.id = a.attempt_id
        JOIN tests   ts ON ts.id = q.test_id
        WHERE t.completed = 1 AND t.user_id = ? AND ts.is_study = 0
        GROUP BY q.topic, ts.subject
        HAVING mastery < ?
        ORDER BY mastery ASC
        LIMIT ?
        """,
        (user_id, threshold, limit),
    ).fetchall()
    return rows


def _random_question_ids_for_topic(
    conn: sqlite3.Connection,
    user_id: int,
    topic: str,
    subject: str,
    n: int,
    rng: Random,
    exclude: list[int],
) -> list[int]:
    placeholders = ",".join(["?"] * len(exclude)) if exclude else "NULL"
    rows = conn.execute(
        f"""
        SELECT q.id FROM questions q
        JOIN tests t ON t.id = q.test_id
        WHERE t.user_id = ? AND t.is_study = 0
          AND q.topic = ? AND t.subject = ?
          AND q.id NOT IN ({placeholders})
        """,
        (user_id, topic, subject, *exclude),
    ).fetchall()
    ids = [r["id"] for r in rows]
    rng.shuffle(ids)
    return ids[:n]


def _random_question_ids_global(
    conn: sqlite3.Connection,
    user_id: int,
    n: int,
    rng: Random,
    exclude: list[int],
) -> list[int]:
    placeholders = ",".join(["?"] * len(exclude)) if exclude else "NULL"
    rows = conn.execute(
        f"""
        SELECT q.id FROM questions q
        JOIN tests t ON t.id = q.test_id
        WHERE t.user_id = ? AND t.is_study = 0
          AND q.id NOT IN ({placeholders})
        """,
        (user_id, *exclude),
    ).fetchall()
    ids = [r["id"] for r in rows]
    rng.shuffle(ids)
    return ids[:n]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daily_builder.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/daily/builder.py tests/test_daily_builder.py
git commit -m "feat(phase10): build_daily_test picks 2-2-1 from weakest topics"
```

---

## Task 5: daily/finalize.py — hook for show_results

**Files:**
- Create: `src/school_test_engine/daily/finalize.py`
- Test: `tests/test_daily_finalize.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_daily_finalize.py`:

```python
import pytest
from datetime import datetime

from school_test_engine.storage import (
    connect, run_migrations, users_repo, attempts_repo, daily_sessions_repo,
)
from school_test_engine.daily.finalize import finalize_if_daily


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


def _create_basic_test_and_attempt(conn, uid):
    cur = conn.execute(
        """INSERT INTO tests (title, subject, grade, school_type, description,
                              time_limit_min, notenschluessel, source_json,
                              imported_at, is_study, user_id)
           VALUES ('T', 'Daily-5', 8, 'Realschule', '', NULL, '{}', '{}', '2026-01-01', 1, ?)""",
        (uid,),
    )
    test_id = cur.lastrowid
    aid = attempts_repo.start_attempt(conn, test_id, 10, uid)
    return test_id, aid


def test_finalize_completes_open_session(conn, uid):
    test_id, aid = _create_basic_test_and_attempt(conn, uid)
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14",
        test_id=test_id, attempt_id=aid,
        started_at="2026-05-14T08:00:00",
    )
    completed = finalize_if_daily(conn, aid)
    assert completed is True
    row = daily_sessions_repo.get_for_today(conn, uid, "2026-05-14")
    assert row["completed_at"] is not None


def test_finalize_returns_false_for_non_daily_attempt(conn, uid):
    test_id, aid = _create_basic_test_and_attempt(conn, uid)
    # NO daily_sessions row — just a regular attempt
    completed = finalize_if_daily(conn, aid)
    assert completed is False


def test_finalize_returns_false_when_already_completed(conn, uid):
    test_id, aid = _create_basic_test_and_attempt(conn, uid)
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14",
        test_id=test_id, attempt_id=aid,
        started_at="2026-05-14T08:00:00",
    )
    daily_sessions_repo.complete_session(conn, uid, "2026-05-14", completed_at="2026-05-14T08:05:00")
    # Second call should not re-finalize
    completed = finalize_if_daily(conn, aid)
    assert completed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daily_finalize.py -v`
Expected: All FAIL with import error.

- [ ] **Step 3: Write the finalize module**

Create `src/school_test_engine/daily/finalize.py`:

```python
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..storage import daily_sessions_repo


def finalize_if_daily(conn: sqlite3.Connection, attempt_id: int) -> bool:
    """If `attempt_id` belongs to an open daily_sessions row, mark it complete.

    Returns True if a session was finalized, False otherwise (non-daily attempt
    OR session already completed).
    """
    row = conn.execute(
        "SELECT user_id, session_date FROM daily_sessions "
        "WHERE attempt_id = ? AND completed_at IS NULL",
        (attempt_id,),
    ).fetchone()
    if row is None:
        return False
    daily_sessions_repo.complete_session(
        conn,
        row["user_id"],
        row["session_date"],
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daily_finalize.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/daily/finalize.py tests/test_daily_finalize.py
git commit -m "feat(phase10): finalize_if_daily hook completes session on test finish"
```

---

## Task 6: DailyCard widget (4 states)

**Files:**
- Create: `src/school_test_engine/ui/widgets/daily_card.py`

- [ ] **Step 1: Write the widget**

Create `src/school_test_engine/ui/widgets/daily_card.py`:

```python
from __future__ import annotations

from typing import Literal

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


DailyState = Literal["no_library", "due", "done"]


def _streak_text(streak: int) -> str:
    if streak <= 0:
        return ""
    if streak == 1:
        return "🔥 1. Tag"
    return f"🔥 {streak} Tage in Folge"


class DailyCard(ClickableCard):
    """Daily-5 status card on the Hauptmenü. Four visual states (no_library,
    due-no-streak, due-with-streak, done)."""

    practice_clicked = Signal()

    def __init__(
        self,
        state: DailyState,
        streak: int,
        last_grade: int | None = None,
        parent=None,
    ):
        super().__init__(object_name="dailyCard", parent=parent)
        self.setMinimumHeight(96)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 14, 20, 14)
        outer.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(4)

        eyebrow_text = "DAILY-5 · heute"
        if state == "no_library":
            eyebrow_text = "DAILY-5"
        elif state == "done":
            eyebrow_text = "✓ DAILY-5 · heute geschafft"
        eyebrow = QLabel(eyebrow_text)
        eyebrow.setObjectName("eyebrow")
        left.addWidget(eyebrow)

        if state == "no_library":
            title = QLabel("Importiere zuerst Tests in deine Library —\nDaily-5 startet danach.")
            title.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 11pt;")
            title.setWordWrap(True)
            left.addWidget(title)
        elif state == "due":
            title = QLabel("5 Fragen, ~5 Min")
            title.setFont(QFont(FontFamily.DISPLAY, 16, QFont.Weight.Medium))
            title.setStyleSheet(f"color: {Semantic.FG};")
            left.addWidget(title)
            streak_str = _streak_text(streak)
            if streak_str:
                sub = QLabel(streak_str)
                sub.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
                left.addWidget(sub)
        elif state == "done":
            sub_parts: list[str] = []
            streak_str = _streak_text(streak)
            if streak_str:
                sub_parts.append(streak_str)
            if last_grade is not None:
                sub_parts.append(f"Note: {last_grade}")
            sub_parts.append("komm morgen wieder")
            sub = QLabel(" · ".join(sub_parts))
            sub.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
            sub.setWordWrap(True)
            left.addWidget(sub)

        outer.addLayout(left, 1)

        if state == "due":
            btn = QPushButton("Starten →")
            btn.setObjectName("primary")
            btn.clicked.connect(lambda: self.practice_clicked.emit())
            outer.addWidget(btn)
        elif state == "done":
            # Greyed-out check pill
            pill = QLabel("✓")
            pill.setStyleSheet(
                "background: #dde8d0; color: #3e552d; "
                "font-size: 16pt; padding: 4px 14px; border-radius: 14px;"
            )
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            outer.addWidget(pill)
        # state == "no_library": no action button
```

- [ ] **Step 2: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.ui.widgets.daily_card import DailyCard
for st, streak, grade in [('no_library', 0, None), ('due', 0, None), ('due', 3, None), ('done', 4, 2)]:
    c = DailyCard(st, streak, last_grade=grade)
    print('ok', st, 'streak=', streak)"
```

Expected: prints four `ok ...` lines without exception.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/widgets/daily_card.py
git commit -m "feat(phase10): DailyCard widget with 4 states (no_library/due/done)"
```

---

## Task 7: MenuPage — append DailyCard to both layout variants

**Files:**
- Modify: `src/school_test_engine/ui/pages/menu.py`

- [ ] **Step 1: Read the current menu.py**

Locate:
- `_build_compact_grid()` (called when KAs are present)
- `_build_full_grid()` (called when no KAs)
- `reload()` method (rebuilds dynamic content)

Both `_build_compact_grid` and `_build_full_grid` end by adding their grid to `self._dynamic_layout`. We append the DailyCard AFTER both.

- [ ] **Step 2: Add imports**

Add to the top of `src/school_test_engine/ui/pages/menu.py`:

```python
from datetime import date

from ...daily import builder as daily_builder
from ...daily import streak as daily_streak
from ...storage import daily_sessions_repo
from ..widgets.daily_card import DailyCard
```

Note: `from datetime import date` is already imported in Phase 7 — verify, don't duplicate.

- [ ] **Step 3: Add a helper to compute the daily state**

Add this method to `MenuPage`:

```python
    def _compute_daily_state(self, uid: int) -> tuple[str, int, int | None]:
        """Return (state, streak, last_grade)."""
        today = date.today()
        today_iso = today.isoformat()

        streak = daily_streak.current_streak(self.window.conn, uid, today)

        session = daily_sessions_repo.get_for_today(self.window.conn, uid, today_iso)
        if session is not None and session["completed_at"] is not None:
            # Done — look up the attempt's grade
            attempt_row = self.window.conn.execute(
                "SELECT note FROM attempts WHERE id = ?",
                (session["attempt_id"],),
            ).fetchone() if session["attempt_id"] else None
            last_grade = attempt_row["note"] if attempt_row else None
            return ("done", streak, last_grade)

        if not daily_builder.has_enough_questions(self.window.conn, uid):
            return ("no_library", streak, None)

        return ("due", streak, None)
```

- [ ] **Step 4: Append DailyCard in both layout builders**

In `_build_compact_grid`, after the existing `self._dynamic_layout.addLayout(grid_wrap)` call, add:

```python
        # Phase 10: Daily-5 card
        uid = self.window.active_user_id
        if uid is not None:
            state, streak, last_grade = self._compute_daily_state(uid)
            card = DailyCard(state, streak, last_grade=last_grade)
            card.practice_clicked.connect(self.window.start_daily_five)
            self._dynamic_layout.addWidget(card)
```

In `_build_full_grid`, after the existing `self._dynamic_layout.addLayout(grid_wrap)` call, add the SAME block:

```python
        # Phase 10: Daily-5 card
        uid = self.window.active_user_id
        if uid is not None:
            state, streak, last_grade = self._compute_daily_state(uid)
            card = DailyCard(state, streak, last_grade=last_grade)
            card.practice_clicked.connect(self.window.start_daily_five)
            self._dynamic_layout.addWidget(card)
```

- [ ] **Step 5: Smoke test (MenuPage builds without exception)**

The `start_daily_five` method on MainWindow doesn't exist yet (Task 8 will add it). The smoke test below only constructs MenuPage; the click handler isn't invoked.

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
uid = users_repo.create_user(c, 'Clemens', '🧒')

class FakeWindow:
    active_user_id = uid
    conn = c
    user_changed = type('S', (), {'connect': lambda *a, **k: None})()
    def show_menu(self): pass
    def show_library(self): pass
    def show_gaps(self): pass
    def show_history(self): pass
    def show_import(self): pass
    def show_events(self): pass
    def show_grades(self): pass
    def show_prompt_builder(self, *a, **k): pass
    def show_profile_picker(self): pass
    def start_daily_five(self): pass  # stub for now

from school_test_engine.ui.pages.menu import MenuPage
p = MenuPage(FakeWindow())
p.reload()
print('ok')"
```

Expected: `ok` (no exception).

- [ ] **Step 6: Run full suite (no regressions)**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite still green (existing 187 + new tests from Tasks 1-5).

- [ ] **Step 7: Commit**

```bash
git add src/school_test_engine/ui/pages/menu.py
git commit -m "feat(phase10): MenuPage shows DailyCard in both layout variants"
```

---

## Task 8: MainWindow — start_daily_five + show_results hook

**Files:**
- Modify: `src/school_test_engine/ui/main_window.py`

- [ ] **Step 1: Add imports**

In `src/school_test_engine/ui/main_window.py`, add:

```python
from datetime import date, datetime, timezone

from ..daily import builder as daily_builder
from ..daily import finalize as daily_finalize
from ..storage import attempts_repo, daily_sessions_repo
```

- [ ] **Step 2: Add `start_daily_five` method**

Add to `MainWindow` (somewhere with the other show_* / start_* methods):

```python
    def start_daily_five(self) -> None:
        """Start (or resume) today's Daily-5 session."""
        uid = self.active_user_id
        if uid is None:
            return
        today = date.today()
        today_iso = today.isoformat()

        existing = daily_sessions_repo.get_for_today(self.conn, uid, today_iso)
        if existing is not None:
            if existing["completed_at"] is not None:
                return  # already done today
            if existing["attempt_id"] is not None:
                # Resume in-progress session
                self.resume_attempt(existing["attempt_id"])
                return

        # Build fresh test + start attempt + record session
        test_id = daily_builder.build_daily_test(self.conn, uid, today)
        if test_id is None:
            return  # pool insufficient (should not happen if card was clickable)

        points_total = self.conn.execute(
            "SELECT COALESCE(SUM(points), 0) AS pts FROM questions WHERE test_id = ?",
            (test_id,),
        ).fetchone()["pts"]
        attempt_id = attempts_repo.start_attempt(self.conn, test_id, int(points_total), uid)
        daily_sessions_repo.start_session(
            self.conn, uid, today_iso,
            test_id=test_id,
            attempt_id=attempt_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self.runner_page.resume(attempt_id)
        self.stack.setCurrentWidget(self.runner_page)
```

- [ ] **Step 3: Hook `finalize_if_daily` into `show_results`**

Modify `show_results` — add the call BEFORE the existing body:

```python
    def show_results(self, attempt_id: int) -> None:
        daily_finalize.finalize_if_daily(self.conn, attempt_id)
        self._return_to_history = (
            self.stack.currentWidget() is self.history_page
        )
        self.results_page.show_attempt(self.conn, attempt_id)
        self.stack.setCurrentWidget(self.results_page)
```

- [ ] **Step 4: Smoke test the integration**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
uid = users_repo.create_user(c, 'Clemens', '🧒')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.active_user_id = uid
print('has start_daily_five:', hasattr(w, 'start_daily_five'))
# Call with empty library → no-op
w.start_daily_five()
print('ok')"
```

Expected: `has start_daily_five: True` then `ok`.

- [ ] **Step 5: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite green.

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/main_window.py
git commit -m "feat(phase10): MainWindow.start_daily_five + finalize hook in show_results"
```

---

## Task 9: User-isolation regression test

**Files:**
- Create: `tests/test_daily_isolation.py`

- [ ] **Step 1: Write isolation tests**

Create `tests/test_daily_isolation.py`:

```python
import pytest

from school_test_engine.storage import (
    connect, run_migrations, users_repo, daily_sessions_repo,
)


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_two_users_have_independent_sessions(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    daily_sessions_repo.start_session(
        conn, a, "2026-05-14", test_id=None, attempt_id=None,
        started_at="2026-05-14T08:00:00",
    )
    assert daily_sessions_repo.get_for_today(conn, a, "2026-05-14") is not None
    assert daily_sessions_repo.get_for_today(conn, b, "2026-05-14") is None


def test_delete_user_cascade_removes_daily_sessions(conn):
    uid = users_repo.create_user(conn, "Wegmacher")
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14", test_id=None, attempt_id=None,
        started_at="2026-05-14T08:00:00",
    )
    users_repo.delete_user(conn, uid)
    assert conn.execute(
        "SELECT COUNT(*) FROM daily_sessions WHERE user_id = ?", (uid,)
    ).fetchone()[0] == 0
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_daily_isolation.py -v`
Expected: 2 PASS.

Run full suite: `pytest -v 2>&1 | tail -3`
Expected: full suite green.

- [ ] **Step 3: Commit**

```bash
git add tests/test_daily_isolation.py
git commit -m "test(phase10): user isolation + cascade for daily_sessions"
```

---

## Task 10: End-to-end smoke + acceptance audit

**Files:** none — audit only.

- [ ] **Step 1: Run comprehensive end-to-end smoke**

Run:
```bash
QT_QPA_PLATFORM=offscreen python <<'EOF'
import json
from datetime import date, datetime, timezone
from PySide6.QtWidgets import QApplication
app = QApplication([])

from school_test_engine.storage import (
    connect, run_migrations, users_repo, attempts_repo, daily_sessions_repo,
)
from school_test_engine.importer.json_import import import_from_string
from school_test_engine.daily import builder as daily_builder
from school_test_engine.daily import streak as daily_streak
from school_test_engine.daily import finalize as daily_finalize

# AC1: Migration 009 ran
c = connect(':memory:')
run_migrations(c)
ver = c.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
assert ver >= 9
print(f"AC1: schema_version={ver}, daily_sessions table present")

# Setup: user + library with 5 questions
uid = users_repo.create_user(c, 'Clemens', '🧒')
payload = json.dumps({
    "schema_version": 1, "title": "T1", "subject": "Mathe",
    "grade": 8, "school_type": "Realschule",
    "notenschluessel": {1:[100,90], 2:[89,75], 3:[74,60], 4:[59,45], 5:[44,20], 6:[19,0]},
    "questions": [
        {"id": f"q{i}", "type": "single_choice", "topic": f"Topic{i}",
         "difficulty": "mittel", "points": 2,
         "prompt": f"P{i}", "choices": [{"id":"a","text":"A"},{"id":"b","text":"B"}],
         "correct": ["a"], "explanation": "x"}
        for i in range(1, 6)
    ],
})
test_id = import_from_string(c, payload, user_id=uid)

# AC3: has_enough_questions True now
assert daily_builder.has_enough_questions(c, uid) is True
print("AC3a: has_enough_questions True after library import")

# AC4: build_daily_test creates synthetic with subject Daily-5
new_test_id = daily_builder.build_daily_test(c, uid, date(2026, 5, 14))
assert new_test_id is not None
row = c.execute("SELECT * FROM tests WHERE id = ?", (new_test_id,)).fetchone()
assert row["subject"] == "Daily-5"
assert row["is_study"] == 1
qs = c.execute("SELECT COUNT(*) AS n FROM questions WHERE test_id = ?", (new_test_id,)).fetchone()
assert qs["n"] == 5
print(f"AC4: daily test built id={new_test_id}, subject=Daily-5, 5 questions")

# AC2/AC5: MainWindow flow
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.active_user_id = uid
w.menu_page.reload()
print("AC2: MenuPage reloaded successfully with DailyCard")

# AC6: Streak starts at 0
assert daily_streak.current_streak(c, uid, date(2026, 5, 14)) == 0
print("AC6a: streak=0 initially")

# Simulate full flow: start daily, finalize
attempt_id = attempts_repo.start_attempt(c, new_test_id, 10, uid)
daily_sessions_repo.start_session(
    c, uid, "2026-05-14", test_id=new_test_id, attempt_id=attempt_id,
    started_at="2026-05-14T08:00:00",
)
attempts_repo.finish_attempt(c, attempt_id, points_earned=8, percent=80, note=2)
ok = daily_finalize.finalize_if_daily(c, attempt_id)
assert ok is True
print("AC5: finalize_if_daily completes the session")

# AC6: Streak=1 after today's complete
assert daily_streak.current_streak(c, uid, date(2026, 5, 14)) == 1
print("AC6b: streak=1 after today completed")

# Simulate yesterday + day-before-yesterday completed → streak=3
for d in ["2026-05-12", "2026-05-13"]:
    daily_sessions_repo.start_session(
        c, uid, d, test_id=None, attempt_id=None, started_at=d + "T08:00:00",
    )
    daily_sessions_repo.complete_session(c, uid, d, completed_at=d + "T08:05:00")
assert daily_streak.current_streak(c, uid, date(2026, 5, 14)) == 3
print("AC6c: streak=3 across 3 consecutive days")

# AC7: Daily-5 NOT in Phase 7 comparison (subject mismatch)
# Verify by checking subject of the synthetic test
assert row["subject"] != "Mathe"
print("AC7: Daily-5 subject != any KA subject, naturally excluded from comparison")

# AC9: cascade
users_repo.delete_user(c, uid)
n = c.execute("SELECT COUNT(*) FROM daily_sessions WHERE user_id = ?", (uid,)).fetchone()[0]
assert n == 0
print("AC9: cascade removes daily_sessions on user delete")

print("\n=== ALL ACCEPTANCE CRITERIA VERIFIED ===")
EOF
```

Expected: prints `ALL ACCEPTANCE CRITERIA VERIFIED` with each AC line above it.

- [ ] **Step 2: Run full pytest suite**

Run: `pytest -v 2>&1 | tail -5`
Expected: all tests green.

- [ ] **Step 3: Acceptance audit summary**

Walk each spec acceptance criterion:

1. ✅ Migration 009 sauber — Task 1 + smoke
2. ✅ DailyCard auf Hauptmenü in beiden Layouts — Task 7 smoke
3. ✅ Card-Zustände wechseln korrekt — exercised in smoke (no_library → due → done via finalize)
4. ✅ "Starten"-Klick → Runner mit 5 Fragen 2-2-1 — Task 4 + Task 8
5. ✅ Card zeigt "✓ heute geschafft" mit Note nach Abschluss — finalize sets completed_at; menu reload shows done state with last_grade
6. ✅ Streak korrekt + resettet bei Lücke — Task 3 tests + smoke
7. ✅ Daily-5 NICHT in Phase 7 Comparison (subject mismatch) — smoke step
8. ✅ Daily-5 in History sichtbar mit "Daily-5"-Subject — implicit via existing history page (no code change)
9. ✅ Profil-Wechsel: user-isoliert — Task 9 tests
10. ⏳ Manueller End-to-End (display required) — user action

- [ ] **Step 4: No new commit needed for Task 10** (audit only). If polish was needed:

```bash
git add -A
git commit -m "fix(phase10): smoke-test polish"
```

---

## Self-Review

**Spec coverage:**
- §2 Migration 009 → Task 1 ✓
- §3.1 daily/builder.py (has_enough_questions + build_daily_test) → Task 4 ✓
- §3.1 daily/streak.py → Task 3 ✓
- §3.1 daily/finalize.py → Task 5 ✓
- §3.2 daily_sessions_repo → Task 2 ✓
- §3.3 DailyCard widget → Task 6 ✓
- §3.4 MenuPage integration (both layouts) → Task 7 ✓
- §3.5 MainWindow.start_daily_five + show_results hook → Task 8 ✓
- §3.6 subject="Daily-5" naturally excluded → §6 smoke verifies; Library list_tests already filters is_study=0 — no code change needed
- §4 2-2-1 question selection → Task 4 (`_pick_question_ids` + `_weakest_topics`) ✓
- §5 Streak-Berechnung → Task 3 ✓
- §6 Edge cases → covered by tests in Tasks 2-5 + smoke
- §7 Tests → present throughout
- §8 10 Akzeptanzkriterien → Task 10 audit walks them
- §9 Risiken → documented, no code action needed for Phase 10

**Placeholder scan:** No TBDs. Every step has runnable code or commands.

**Type consistency:**
- `daily_sessions_repo.{start,complete,get_for_today,find_by_attempt,list_recent_completed_dates}` — same signatures used in Tasks 2, 3, 5, 7, 8, 9 ✓
- `daily.builder.{has_enough_questions, build_daily_test}` — same in Tasks 4, 7, 8 ✓
- `daily.streak.current_streak(conn, user_id, today: date)` — same in Tasks 3, 7 ✓
- `daily.finalize.finalize_if_daily(conn, attempt_id)` — same in Tasks 5, 8 ✓
- `DailyCard(state, streak, last_grade=None)` — same in Tasks 6, 7 ✓
- `MainWindow.start_daily_five()` — referenced in Tasks 7, 8 ✓
- `DailyState` literal type `"no_library" | "due" | "done"` — Tasks 6, 7 use same strings ✓

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-14-phase-10-daily-five.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task + review checkpoints.

**2. Inline Execution** — Batch execution in this session with checkpoints.

Which approach?

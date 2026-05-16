# Phase 16 — Fehlerheft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine View-Layer-Liste der noch-nicht-gemeisterten Fragen pro Fach, mit One-Click-Übungs-Test (max 10 Fragen, schwerste zuerst). Eviction: 2× richtig in Folge → raus.

**Architecture:** Neues Domain-Paket `error_book/` (Pure-Query-Layer + Synth-Test-Builder), neue UI-Page `ErrorBookPage`, Erweiterung von `gaps.py` (Footer-Button), `global_header.py` (Logo-Menü-Eintrag) und `main_window.py` (Routing). Identitäts-Brücke über `questions.ext_id = "err:{root_qid}"` — keine Migration, keine neue Tabelle.

**Tech Stack:** Python 3.12, PySide6, SQLite, pytest. Reuse: `daily/builder.py`-Pattern für Synth-Test-Bau, `pages/grades.py`-Layout für UI, `widgets/Pill` + `widgets/Eyebrow` + `widgets/FlowLayout`.

**Spec:** `docs/superpowers/specs/2026-05-16-fehlerheft-design.md`

---

## Task 1: Skelett — Domain-Paket + leeres ErrorBookEntry-Modell

**Files:**
- Create: `src/school_test_engine/error_book/__init__.py`
- Create: `src/school_test_engine/error_book/models.py`
- Create: `tests/test_error_book_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_error_book_models.py
from school_test_engine.error_book.models import ErrorBookEntry


def test_error_book_entry_is_frozen():
    entry = ErrorBookEntry(
        question_id=42,
        subject="Mathe",
        topic="Bruchrechnung",
        prompt_excerpt="Was ist 1/2 + 1/3?",
        wrong_count=3,
        last_wrong_at="2026-05-12T10:00:00Z",
        consecutive_correct=1,
    )
    import dataclasses
    assert dataclasses.is_dataclass(entry)
    # frozen → AttributeError on mutation
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.wrong_count = 5  # type: ignore
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_error_book_models.py -v`
Expected: FAIL with `ModuleNotFoundError: school_test_engine.error_book`

- [ ] **Step 3: Create empty package init**

```python
# src/school_test_engine/error_book/__init__.py
"""Fehlerheft domain — view-only über bestehenden answers/attempts/tests/questions-Stamm."""
```

- [ ] **Step 4: Implement ErrorBookEntry**

```python
# src/school_test_engine/error_book/models.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorBookEntry:
    """Eine offene Fehlerheft-Position.

    `question_id` ist immer die ROOT-Frage (nie eine err:-Kopie).
    `consecutive_correct` ist 0 oder 1 — bei ≥2 wird der Eintrag in
    `queries.list_open_entries` rausgefiltert und erscheint nicht.
    """

    question_id: int
    subject: str
    topic: str
    prompt_excerpt: str
    wrong_count: int
    last_wrong_at: str
    consecutive_correct: int
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_error_book_models.py -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/error_book/__init__.py \
        src/school_test_engine/error_book/models.py \
        tests/test_error_book_models.py
git commit -m "feat(error_book): ErrorBookEntry frozen-dataclass + package skeleton"
```

---

## Task 2: Eviction-Helpers in Python

**Files:**
- Create: `src/school_test_engine/error_book/queries.py`
- Modify: `tests/test_error_book_models.py` (oder neu: `tests/test_error_book_eviction.py`)
- Test: `tests/test_error_book_eviction.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_error_book_eviction.py
from school_test_engine.error_book.queries import (
    _is_resolved, _consecutive_correct,
)


class _Row:
    def __init__(self, is_correct: int):
        self.is_correct = is_correct


def test_is_resolved_needs_two_recent_correct():
    assert _is_resolved([_Row(1), _Row(1)]) is True
    assert _is_resolved([_Row(1), _Row(0)]) is False
    assert _is_resolved([_Row(0), _Row(1)]) is False
    assert _is_resolved([_Row(1)]) is False  # zu wenige
    assert _is_resolved([]) is False


def test_consecutive_correct_stops_at_first_wrong():
    assert _consecutive_correct([_Row(1), _Row(1), _Row(0), _Row(1)]) == 2
    assert _consecutive_correct([_Row(1), _Row(0)]) == 1
    assert _consecutive_correct([_Row(0), _Row(1)]) == 0
    assert _consecutive_correct([]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_error_book_eviction.py -v`
Expected: FAIL with `ImportError: cannot import name '_is_resolved'`

- [ ] **Step 3: Implement helpers**

```python
# src/school_test_engine/error_book/queries.py
from __future__ import annotations

import sqlite3
from typing import Iterable


def _is_resolved(answers_desc: Iterable) -> bool:
    """True wenn die letzten 2 Antworten (DESC-sortiert) beide korrekt waren."""
    rows = list(answers_desc)
    if len(rows) < 2:
        return False
    return rows[0].is_correct == 1 and rows[1].is_correct == 1


def _consecutive_correct(answers_desc: Iterable) -> int:
    """Zählt korrekte Antworten vom neuesten Eintrag rückwärts bis zum ersten Fehler."""
    n = 0
    for a in answers_desc:
        if a.is_correct == 1:
            n += 1
        else:
            break
    return n
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_error_book_eviction.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/error_book/queries.py tests/test_error_book_eviction.py
git commit -m "feat(error_book): pure-python eviction helpers (_is_resolved, _consecutive_correct)"
```

---

## Task 3: `list_open_entries` — Eligibility + Answer-Reihe + Filter

**Files:**
- Modify: `src/school_test_engine/error_book/queries.py`
- Create: `tests/test_error_book_queries.py`

Wichtige Vor-Reise: Schema-Reminder:
- `tests (id, user_id, subject, is_study, …)`
- `questions (id, test_id, ext_id, topic, prompt, payload, …)`
- `attempts (id, test_id, finished_at, completed, …)`
- `answers (id, attempt_id, question_id, response, points_earned, is_correct)`

- [ ] **Step 1: Write the failing test — Frage 1× falsch in regulärem Test**

```python
# tests/test_error_book_queries.py
import json

import pytest

from school_test_engine.error_book.queries import list_open_entries, count_open
from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import (
    connect, run_migrations, users_repo, attempts_repo,
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


def _import_one_question_test(conn, uid, subject: str = "Mathe", topic: str = "Bruchrechnung"):
    payload = {
        "title": "T1",
        "subject": subject,
        "grade": 8,
        "school_type": "Realschule",
        "questions": [
            {
                "id": "q1",
                "type": "single_choice",
                "topic": topic,
                "difficulty": "mittel",
                "points": 2,
                "prompt": f"Frage zu {topic}?",
                "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                "correct": ["a"],
            },
        ],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (test_id,)
    ).fetchone()["id"]
    return test_id, qid


def _run_attempt(conn, uid, test_id, qid, *, is_correct: int, points: int = 2):
    """Helper: laufender Attempt, eine Antwort, finish."""
    attempt_id = attempts_repo.start_attempt(conn, test_id, points, uid)
    attempts_repo.upsert_answer(
        conn, attempt_id, qid, response=["a" if is_correct else "b"],
        points_earned=(points if is_correct else 0.0), is_correct=bool(is_correct),
    )
    attempts_repo.finish_attempt(conn, attempt_id, note=1 if is_correct else 6)
    return attempt_id


def test_one_wrong_answer_appears_in_book(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)

    entries = list_open_entries(conn, uid)
    assert len(entries) == 1
    assert entries[0].question_id == qid
    assert entries[0].subject == "Mathe"
    assert entries[0].topic == "Bruchrechnung"
    assert entries[0].wrong_count == 1
    assert entries[0].consecutive_correct == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_error_book_queries.py::test_one_wrong_answer_appears_in_book -v`
Expected: FAIL with `ImportError: cannot import name 'list_open_entries'`

- [ ] **Step 3: Implement `list_open_entries` + `count_open`**

```python
# Append to src/school_test_engine/error_book/queries.py

from .models import ErrorBookEntry


_CANDIDATE_SQL = """
    SELECT DISTINCT a.question_id AS qid
    FROM answers a
    JOIN attempts att ON att.id = a.attempt_id
    JOIN tests t ON t.id = att.test_id
    WHERE a.is_correct = 0
      AND att.completed = 1
      AND t.is_study = 0
      AND t.user_id = ?
"""

_QUESTION_META_SQL = """
    SELECT q.id   AS id,
           t.subject AS subject,
           q.topic AS topic,
           q.prompt AS prompt
    FROM questions q
    JOIN tests t ON t.id = q.test_id
    WHERE q.id = ?
"""

_ANSWERS_DESC_SQL = """
    SELECT a.is_correct AS is_correct, att.finished_at AS finished_at
    FROM answers a
    JOIN attempts att ON att.id = a.attempt_id
    WHERE a.question_id = ? AND att.completed = 1
    UNION ALL
    SELECT a.is_correct AS is_correct, att.finished_at AS finished_at
    FROM answers a
    JOIN attempts att ON att.id = a.attempt_id
    JOIN questions q ON q.id = a.question_id
    WHERE q.ext_id = ? AND att.completed = 1
    ORDER BY finished_at DESC
"""


def _excerpt(prompt: str, limit: int = 80) -> str:
    if prompt is None:
        return ""
    s = " ".join(prompt.split())
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def list_open_entries(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str | None = None,
) -> list[ErrorBookEntry]:
    """Offene Fehlerheft-Positionen, sortiert nach wrong_count DESC, last_wrong_at DESC."""
    qids = [r["qid"] for r in conn.execute(_CANDIDATE_SQL, (user_id,)).fetchall()]

    entries: list[ErrorBookEntry] = []
    for qid in qids:
        meta = conn.execute(_QUESTION_META_SQL, (qid,)).fetchone()
        if meta is None:
            continue
        if subject is not None and meta["subject"] != subject:
            continue

        answers = conn.execute(_ANSWERS_DESC_SQL, (qid, f"err:{qid}")).fetchall()
        if _is_resolved(answers):
            continue

        wrong_count = sum(1 for a in answers if a["is_correct"] == 0)
        last_wrong_at = next(
            (a["finished_at"] for a in answers if a["is_correct"] == 0), ""
        )
        entries.append(ErrorBookEntry(
            question_id=qid,
            subject=meta["subject"],
            topic=meta["topic"] or "",
            prompt_excerpt=_excerpt(meta["prompt"]),
            wrong_count=wrong_count,
            last_wrong_at=last_wrong_at,
            consecutive_correct=_consecutive_correct(answers),
        ))

    entries.sort(key=lambda e: (-e.wrong_count, e.last_wrong_at), reverse=False)
    # Tie-break: jüngeres last_wrong_at zuerst → DESC. Aber wir sortieren bereits
    # ASC nach last_wrong_at oben, also umkehren: zweistufiger Sort:
    entries.sort(key=lambda e: e.last_wrong_at, reverse=True)
    entries.sort(key=lambda e: e.wrong_count, reverse=True)
    return entries


def count_open(conn: sqlite3.Connection, user_id: int) -> dict[str, int]:
    """Anzahl offener Einträge pro Fach (Dict mit Fach → int)."""
    out: dict[str, int] = {}
    for entry in list_open_entries(conn, user_id):
        out[entry.subject] = out.get(entry.subject, 0) + 1
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_error_book_queries.py::test_one_wrong_answer_appears_in_book -v`
Expected: 1 passed

- [ ] **Step 5: Add the other 8 query tests**

```python
# Append to tests/test_error_book_queries.py

def test_wrong_then_right_stays_with_streak_one(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    _run_attempt(conn, uid, test_id, qid, is_correct=1)
    entries = list_open_entries(conn, uid)
    assert len(entries) == 1
    assert entries[0].consecutive_correct == 1


def test_wrong_then_two_right_is_evicted(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    _run_attempt(conn, uid, test_id, qid, is_correct=1)
    _run_attempt(conn, uid, test_id, qid, is_correct=1)
    assert list_open_entries(conn, uid) == []


def test_wrong_right_wrong_breaks_streak(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    _run_attempt(conn, uid, test_id, qid, is_correct=1)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    entries = list_open_entries(conn, uid)
    assert len(entries) == 1
    assert entries[0].consecutive_correct == 0


def test_wrong_only_in_is_study_test_does_not_count(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    # Forciere is_study=1
    conn.execute("UPDATE tests SET is_study = 1 WHERE id = ?", (test_id,))
    conn.commit()
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    assert list_open_entries(conn, uid) == []


def test_eviction_via_err_copy(conn, uid):
    test_id, qid = _import_one_question_test(conn, uid)
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    # Simuliere Kopie über err:-ext_id (zweiter Test, eine Frage, ext_id pointing to qid)
    copy_test_id = _import_one_question_test(conn, uid)[0]
    copy_qid = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (copy_test_id,)
    ).fetchone()["id"]
    conn.execute("UPDATE tests SET is_study = 1 WHERE id = ?", (copy_test_id,))
    conn.execute("UPDATE questions SET ext_id = ? WHERE id = ?", (f"err:{qid}", copy_qid))
    conn.commit()
    # 2× richtig in der Kopie → Original wird evicted
    _run_attempt(conn, uid, copy_test_id, copy_qid, is_correct=1)
    _run_attempt(conn, uid, copy_test_id, copy_qid, is_correct=1)
    assert list_open_entries(conn, uid) == []


def test_subject_filter(conn, uid):
    test_m, qid_m = _import_one_question_test(conn, uid, subject="Mathe")
    test_e, qid_e = _import_one_question_test(conn, uid, subject="Englisch")
    _run_attempt(conn, uid, test_m, qid_m, is_correct=0)
    _run_attempt(conn, uid, test_e, qid_e, is_correct=0)
    assert {e.question_id for e in list_open_entries(conn, uid, subject="Mathe")} == {qid_m}
    assert {e.question_id for e in list_open_entries(conn, uid, subject="Englisch")} == {qid_e}


def test_ordering_wrong_count_desc(conn, uid):
    t1, q1 = _import_one_question_test(conn, uid, topic="A")
    t2, q2 = _import_one_question_test(conn, uid, topic="B")
    # q1: 3× falsch, q2: 1× falsch
    for _ in range(3):
        _run_attempt(conn, uid, t1, q1, is_correct=0)
    _run_attempt(conn, uid, t2, q2, is_correct=0)
    entries = list_open_entries(conn, uid)
    assert [e.question_id for e in entries] == [q1, q2]


def test_count_open_per_subject(conn, uid):
    t1, q1 = _import_one_question_test(conn, uid, subject="Mathe")
    t2, q2 = _import_one_question_test(conn, uid, subject="Englisch")
    _run_attempt(conn, uid, t1, q1, is_correct=0)
    _run_attempt(conn, uid, t2, q2, is_correct=0)
    assert count_open(conn, uid) == {"Mathe": 1, "Englisch": 1}


def test_prompt_excerpt_truncates_at_80(conn, uid):
    # Frage mit langem Prompt
    long_prompt = "A" * 200
    payload = {
        "title": "T", "subject": "Mathe", "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": "X", "difficulty": "mittel",
            "points": 1, "prompt": long_prompt,
            "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "correct": ["a"],
        }],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
    _run_attempt(conn, uid, test_id, qid, is_correct=0)
    entries = list_open_entries(conn, uid)
    assert len(entries[0].prompt_excerpt) <= 80
    assert entries[0].prompt_excerpt.endswith("…")
```

- [ ] **Step 6: Run all query tests**

Run: `pytest tests/test_error_book_queries.py -v`
Expected: 9 passed

- [ ] **Step 7: Commit**

```bash
git add src/school_test_engine/error_book/queries.py tests/test_error_book_queries.py
git commit -m "feat(error_book): list_open_entries + count_open with eligibility + eviction"
```

---

## Task 4: `has_open_errors` Convenience-Wrapper

**Files:**
- Create: `src/school_test_engine/error_book/builder.py`
- Test: `tests/test_error_book_builder.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_error_book_builder.py
import json

import pytest

from school_test_engine.error_book.builder import has_open_errors
from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import (
    connect, run_migrations, users_repo, attempts_repo,
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


def _import_and_fail(conn, uid, subject: str = "Mathe"):
    payload = {
        "title": "T", "subject": subject, "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": "X", "difficulty": "mittel",
            "points": 2, "prompt": "P",
            "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "correct": ["a"],
        }],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
    aid = attempts_repo.start_attempt(conn, test_id, 2, uid)
    attempts_repo.upsert_answer(
        conn, aid, qid, response=["b"], points_earned=0.0, is_correct=False
    )
    attempts_repo.finish_attempt(conn, aid, note=6)


def test_has_open_errors_false_on_empty(conn, uid):
    assert has_open_errors(conn, uid) is False
    assert has_open_errors(conn, uid, subject="Mathe") is False


def test_has_open_errors_true_after_fail(conn, uid):
    _import_and_fail(conn, uid, subject="Mathe")
    assert has_open_errors(conn, uid) is True
    assert has_open_errors(conn, uid, subject="Mathe") is True
    assert has_open_errors(conn, uid, subject="Englisch") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_error_book_builder.py::test_has_open_errors_false_on_empty -v`
Expected: FAIL with `ImportError: cannot import name 'has_open_errors'`

- [ ] **Step 3: Implement `has_open_errors`**

```python
# src/school_test_engine/error_book/builder.py
from __future__ import annotations

import sqlite3

from . import queries


def has_open_errors(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str | None = None,
) -> bool:
    """True wenn mindestens 1 offene Fehlerheft-Position für den User existiert
    (optional gefiltert nach Fach)."""
    counts = queries.count_open(conn, user_id)
    if subject is None:
        return any(v > 0 for v in counts.values())
    return counts.get(subject, 0) > 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_error_book_builder.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/error_book/builder.py tests/test_error_book_builder.py
git commit -m "feat(error_book): has_open_errors predicate"
```

---

## Task 5: Root-Flattening + `_load_questions` Helper

**Files:**
- Modify: `src/school_test_engine/error_book/builder.py`
- Modify: `tests/test_error_book_builder.py`

- [ ] **Step 1: Write the failing tests**

```python
# Append to tests/test_error_book_builder.py
from school_test_engine.error_book.builder import _root_question_id


class _Row(dict):
    def __getitem__(self, k):
        return super().__getitem__(k) if k in self else None


def test_root_question_id_direct():
    row = _Row(id=42, ext_id="q1")
    assert _root_question_id(row) == 42


def test_root_question_id_from_err_copy():
    row = _Row(id=99, ext_id="err:42")
    assert _root_question_id(row) == 42


def test_root_question_id_handles_none_ext_id():
    row = _Row(id=42, ext_id=None)
    assert _root_question_id(row) == 42


def test_root_question_id_ignores_other_prefixes():
    row = _Row(id=42, ext_id="dq1")
    assert _root_question_id(row) == 42
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_error_book_builder.py::test_root_question_id_direct -v`
Expected: FAIL with `ImportError: cannot import name '_root_question_id'`

- [ ] **Step 3: Implement root-flattening**

```python
# Append to src/school_test_engine/error_book/builder.py
import re

_ERR_EXT_RE = re.compile(r"^err:(\d+)$")


def _root_question_id(q_row) -> int:
    """Wenn ext_id 'err:N' matched, returnt N; sonst die eigene id.
    Hält die Kette flach: max 1 Hop Indirektion, egal wie oft kopiert."""
    ext = q_row["ext_id"] if "ext_id" in q_row.keys() else None  # type: ignore[attr-defined]
    # sqlite3.Row vs dict
    if hasattr(q_row, "keys") and not isinstance(q_row, dict):
        ext = q_row["ext_id"]
    elif isinstance(q_row, dict):
        ext = q_row.get("ext_id")
    if ext:
        m = _ERR_EXT_RE.match(ext)
        if m:
            return int(m.group(1))
    return int(q_row["id"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_error_book_builder.py -v`
Expected: 6 passed (2 old + 4 new)

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/error_book/builder.py tests/test_error_book_builder.py
git commit -m "feat(error_book): _root_question_id flatten-chain helper"
```

---

## Task 6: `build_practice_test` — Synth-Test mit `err:`-ext_id

**Files:**
- Modify: `src/school_test_engine/error_book/builder.py`
- Modify: `tests/test_error_book_builder.py`

- [ ] **Step 1: Write the failing test — 0 offen returns None**

```python
# Append to tests/test_error_book_builder.py
from school_test_engine.error_book.builder import build_practice_test


def test_build_practice_returns_none_when_no_errors(conn, uid):
    assert build_practice_test(conn, uid, subject="Mathe") is None


def test_build_practice_creates_is_study_test_with_err_ext_id(conn, uid):
    _import_and_fail(conn, uid, subject="Mathe")
    # Hole root_qid
    root_qid = conn.execute(
        "SELECT a.question_id AS qid FROM answers a "
        "JOIN attempts att ON att.id = a.attempt_id "
        "WHERE a.is_correct = 0 LIMIT 1"
    ).fetchone()["qid"]

    test_id = build_practice_test(conn, uid, subject="Mathe")
    assert test_id is not None

    row = conn.execute(
        "SELECT subject, is_study, title, description FROM tests WHERE id = ?",
        (test_id,),
    ).fetchone()
    assert row["subject"] == "Mathe"
    assert row["is_study"] == 1
    assert row["title"].startswith("Fehler-Übung – Mathe – ")
    assert row["description"] == "Wiederholung von Fragen, die noch nicht sitzen."

    copies = conn.execute(
        "SELECT ext_id FROM questions WHERE test_id = ?", (test_id,)
    ).fetchall()
    assert len(copies) == 1
    assert copies[0]["ext_id"] == f"err:{root_qid}"


def test_build_practice_caps_at_limit(conn, uid):
    # 12 falsche Fragen importieren
    for i in range(12):
        payload = {
            "title": f"T{i}", "subject": "Mathe", "grade": 8, "school_type": "Realschule",
            "questions": [{
                "id": "q1", "type": "single_choice", "topic": f"T{i}",
                "difficulty": "mittel", "points": 1, "prompt": f"P{i}",
                "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                "correct": ["a"],
            }],
        }
        test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
        qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
        aid = attempts_repo.start_attempt(conn, test_id, 1, uid)
        attempts_repo.upsert_answer(conn, aid, qid, response=["b"], points_earned=0.0, is_correct=False)
        attempts_repo.finish_attempt(conn, aid, note=6)

    practice_id = build_practice_test(conn, uid, subject="Mathe", limit=10)
    n_copies = conn.execute(
        "SELECT COUNT(*) AS n FROM questions WHERE test_id = ?", (practice_id,)
    ).fetchone()["n"]
    assert n_copies == 10


def test_build_practice_flattens_chain(conn, uid):
    # Frage falsch → Kopie A baut sich (err:qid) → Kopie A wird wieder falsch beantwortet
    # → bauen wir nochmal: neue Kopie B sollte ext_id err:{root}, NICHT err:{copy_a}
    _import_and_fail(conn, uid, subject="Mathe")
    root_qid = conn.execute(
        "SELECT a.question_id AS qid FROM answers a "
        "JOIN attempts att ON att.id = a.attempt_id "
        "WHERE a.is_correct = 0 LIMIT 1"
    ).fetchone()["qid"]

    practice_1 = build_practice_test(conn, uid, subject="Mathe")
    copy_a_qid = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (practice_1,)
    ).fetchone()["id"]
    # Antwort falsch auf die Kopie A
    aid = attempts_repo.start_attempt(conn, practice_1, 1, uid)
    attempts_repo.upsert_answer(conn, aid, copy_a_qid, response=["b"], points_earned=0.0, is_correct=False)
    attempts_repo.finish_attempt(conn, aid, note=6)

    # Eintrag ist immer noch offen → wieder bauen
    practice_2 = build_practice_test(conn, uid, subject="Mathe")
    assert practice_2 != practice_1  # neuer Test, weil practice_1 schon completed ist
    copy_b_ext = conn.execute(
        "SELECT ext_id FROM questions WHERE test_id = ?", (practice_2,)
    ).fetchone()["ext_id"]
    assert copy_b_ext == f"err:{root_qid}", "Kette muss flach bleiben"


def test_build_practice_resumes_open_attempt(conn, uid):
    _import_and_fail(conn, uid, subject="Mathe")
    test_id_1 = build_practice_test(conn, uid, subject="Mathe")
    # Starte Attempt, finish NICHT
    attempts_repo.start_attempt(conn, test_id_1, 2, uid)

    # Erneuter Aufruf darf KEINEN neuen Test bauen, sondern den existierenden zurückgeben
    test_id_2 = build_practice_test(conn, uid, subject="Mathe")
    assert test_id_2 == test_id_1


def test_build_practice_copies_payload_fields(conn, uid):
    payload = {
        "title": "T", "subject": "Mathe", "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": "Bruchrechnung",
            "difficulty": "schwer", "points": 5,
            "prompt": "Was ist 1/2 + 1/3?",
            "prompt_math": "\\frac{1}{2} + \\frac{1}{3}",
            "explanation": "Auf gemeinsamen Nenner bringen.",
            "choices": [{"id": "a", "text": "5/6"}, {"id": "b", "text": "1/5"}],
            "correct": ["a"],
        }],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
    aid = attempts_repo.start_attempt(conn, test_id, 5, uid)
    attempts_repo.upsert_answer(conn, aid, qid, response=["b"], points_earned=0.0, is_correct=False)
    attempts_repo.finish_attempt(conn, aid, note=6)

    practice_id = build_practice_test(conn, uid, subject="Mathe")
    copy = conn.execute(
        "SELECT type, topic, difficulty, points, prompt, prompt_math, payload, explanation, position "
        "FROM questions WHERE test_id = ?", (practice_id,)
    ).fetchone()
    assert copy["type"] == "single_choice"
    assert copy["topic"] == "Bruchrechnung"
    assert copy["difficulty"] == "schwer"
    assert copy["points"] == 5
    assert copy["prompt"] == "Was ist 1/2 + 1/3?"
    assert copy["prompt_math"] == "\\frac{1}{2} + \\frac{1}{3}"
    assert copy["explanation"] == "Auf gemeinsamen Nenner bringen."
    assert copy["position"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_error_book_builder.py::test_build_practice_returns_none_when_no_errors -v`
Expected: FAIL with `ImportError: cannot import name 'build_practice_test'`

- [ ] **Step 3: Implement `build_practice_test`**

```python
# Append to src/school_test_engine/error_book/builder.py
import json
from datetime import date, datetime, timezone

from ..models.test import REALSCHULE_DEFAULT_NOTENSCHLUESSEL


_FEHLER_TITLE_PREFIX = "Fehler-Übung"
_FEHLER_DESCRIPTION = "Wiederholung von Fragen, die noch nicht sitzen."


def _find_open_practice_test(
    conn: sqlite3.Connection, user_id: int, subject: str
) -> int | None:
    """Returnt test_id eines noch nicht abgeschlossenen Fehler-Übungs-Attempts im Fach,
    oder None."""
    row = conn.execute(
        """
        SELECT t.id AS test_id
        FROM tests t
        JOIN attempts att ON att.test_id = t.id
        WHERE t.user_id = ?
          AND t.subject = ?
          AND t.is_study = 1
          AND t.title LIKE ?
          AND att.completed = 0
        ORDER BY att.started_at DESC
        LIMIT 1
        """,
        (user_id, subject, f"{_FEHLER_TITLE_PREFIX}%"),
    ).fetchone()
    return None if row is None else int(row["test_id"])


def _load_questions(conn: sqlite3.Connection, qids: list[int]) -> list[sqlite3.Row]:
    """Returnt Question-Rows in der Reihenfolge der übergebenen qids."""
    if not qids:
        return []
    placeholders = ",".join(["?"] * len(qids))
    rows = conn.execute(
        f"SELECT * FROM questions WHERE id IN ({placeholders})", qids
    ).fetchall()
    by_id = {r["id"]: r for r in rows}
    return [by_id[qid] for qid in qids if qid in by_id]


def build_practice_test(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str,
    limit: int = 10,
) -> int | None:
    """Baut einen Fehler-Übungs-Test (subject, is_study=1) mit ≤limit kopierten Fragen.
    Returnt test_id, oder None wenn keine offenen Fehler im Fach."""
    existing = _find_open_practice_test(conn, user_id, subject)
    if existing is not None:
        return existing

    entries = queries.list_open_entries(conn, user_id, subject=subject)
    if not entries:
        return None
    entries = entries[:limit]

    qids = [e.question_id for e in entries]
    question_rows = _load_questions(conn, qids)
    if not question_rows:
        return None

    today = date.today()
    title = f"{_FEHLER_TITLE_PREFIX} – {subject} – {today.strftime('%d.%m.%Y')}"
    cur = conn.execute(
        """
        INSERT INTO tests
            (title, subject, grade, school_type, description, time_limit_min,
             notenschluessel, source_json, imported_at, is_study, user_id)
        VALUES (?, ?, ?, 'Realschule', ?, NULL, ?, '{}', ?, 1, ?)
        """,
        (
            title,
            subject,
            8,
            _FEHLER_DESCRIPTION,
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
                f"err:{_root_question_id(q)}",
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
            for pos, q in enumerate(question_rows)
        ],
    )
    conn.commit()
    return test_id
```

- [ ] **Step 4: Run all builder tests**

Run: `pytest tests/test_error_book_builder.py -v`
Expected: 12 passed (2 + 4 + 6 new)

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/error_book/builder.py tests/test_error_book_builder.py
git commit -m "feat(error_book): build_practice_test with resume + chain-flattening + err: ext_id"
```

---

## Task 7: ErrorBookPage — Layout + Subject-Pills + Empty-States

**Files:**
- Create: `src/school_test_engine/ui/pages/error_book.py`
- Test: `tests/test_error_book_page.py`

Vor-Reise: `pages/grades.py:58-71` ist das FlowLayout+Subject-Pill-Pattern, das wir kopieren. `widgets/Eyebrow` ist ein einfacher `QLabel`-Konstruktor.

- [ ] **Step 1: Write the failing test — Page-Konstruktion + leere DB**

```python
# tests/test_error_book_page.py
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
from PySide6.QtWidgets import QApplication

from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import connect, run_migrations, users_repo, attempts_repo
from school_test_engine.ui.pages.error_book import ErrorBookPage


class _MockWindow:
    def __init__(self, conn, uid):
        self.conn = conn
        self.active_user_id = uid
        self.started_practice = None

    def start_error_book_practice(self, subject):
        self.started_practice = subject


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    return app


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


def _import_and_fail(conn, uid, subject="Mathe", topic="X"):
    payload = {
        "title": "T", "subject": subject, "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": topic,
            "difficulty": "mittel", "points": 2, "prompt": f"Frage {topic}",
            "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "correct": ["a"],
        }],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
    aid = attempts_repo.start_attempt(conn, test_id, 2, uid)
    attempts_repo.upsert_answer(conn, aid, qid, response=["b"], points_earned=0.0, is_correct=False)
    attempts_repo.finish_attempt(conn, aid, note=6)


def test_page_empty_state_shows_when_no_errors(qt_app, conn, uid):
    window = _MockWindow(conn, uid)
    page = ErrorBookPage(window, conn)
    page.reload()
    assert page.empty_label.isVisible()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_error_book_page.py::test_page_empty_state_shows_when_no_errors -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'school_test_engine.ui.pages.error_book'`

- [ ] **Step 3: Implement ErrorBookPage skeleton**

```python
# src/school_test_engine/ui/pages/error_book.py
from __future__ import annotations

import sqlite3
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...error_book import builder as error_book_builder
from ...error_book import queries as error_book_queries
from ...error_book.models import ErrorBookEntry
from ..design import Color, FontFamily, Semantic
from ..widgets.eyebrow import Eyebrow
from ..widgets.flow_layout import FlowLayout
from ..widgets.pill import Pill
from .._format import fmt_dt
from .._subjects import SUBJECTS_ALL, subject_variant


class ErrorBookPage(QWidget):
    """Pro-Fach-Liste offener Fehler + One-Click-Übungs-Button im Header."""

    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._current_subject: str | None = None
        self._subject_buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(16)

        outer.addWidget(Eyebrow("Fehlerheft"))
        title = QLabel("Was nochmal hakt")
        title.setObjectName("title")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        # Subject-Pill-Row mit FlowLayout (analog grades.py)
        subject_host = QWidget()
        self._subject_row = FlowLayout(subject_host, h_spacing=6, v_spacing=6)
        for s in SUBJECTS_ALL:
            b = QPushButton(s)
            b.setCheckable(True)
            b.setObjectName("subjectTab")
            b.clicked.connect(lambda _, sub=s: self._select_subject(sub))
            self._subject_buttons[s] = b
            self._subject_row.addWidget(b)
        outer.addWidget(subject_host)

        # Globale Empty-State Card
        self.empty_label = QLabel("Noch keine offenen Fehler — sauber.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(
            f"color: {Color.PAPER_600}; font-family: 'Fraunces'; "
            f"font-style: italic; font-size: 13pt; padding: 40px;"
        )
        outer.addWidget(self.empty_label)

        # Per-Subject Empty-Hinweis
        self.subject_empty_label = QLabel("In diesem Fach gerade alles im Lot.")
        self.subject_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subject_empty_label.setStyleSheet(
            f"color: {Color.PAPER_600}; font-size: 11pt; padding: 30px;"
        )
        outer.addWidget(self.subject_empty_label)

        # Scrollable list of error cards
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(10)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._list_container)
        outer.addWidget(self._scroll, stretch=1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        uid = self.window.active_user_id
        if uid is None:
            return
        counts = error_book_queries.count_open(self.conn, uid)
        total = sum(counts.values())

        # Refresh subject pill labels + enabled state
        for sub, btn in self._subject_buttons.items():
            n = counts.get(sub, 0)
            btn.setText(f"{sub} · {n}" if n > 0 else sub)
            btn.setEnabled(n > 0)

        if total == 0:
            self.empty_label.show()
            self.subject_empty_label.hide()
            for btn in self._subject_buttons.values():
                btn.setVisible(False)
            self._scroll.hide()
            self._current_subject = None
            self._refresh_action_button()
            return

        # Wähle Default-Fach: erstes mit count>0, sonst erstes SUBJECTS_ALL
        if self._current_subject is None or counts.get(self._current_subject, 0) == 0:
            self._current_subject = next(
                (s for s in SUBJECTS_ALL if counts.get(s, 0) > 0),
                SUBJECTS_ALL[0],
            )

        self.empty_label.hide()
        for btn in self._subject_buttons.values():
            btn.setVisible(True)
        for sub, btn in self._subject_buttons.items():
            btn.setChecked(sub == self._current_subject)

        # Render Card-Liste oder per-Subject-Empty
        uid = self.window.active_user_id
        entries = error_book_queries.list_open_entries(
            self.conn, uid, subject=self._current_subject
        )
        self._clear_cards()
        if not entries:
            self.subject_empty_label.show()
            self._scroll.hide()
        else:
            self.subject_empty_label.hide()
            self._scroll.show()
            for e in entries:
                self._list_layout.addWidget(_make_entry_card(e))
            self._list_layout.addStretch(1)
        self._refresh_action_button()

    def practice_button_count(self) -> int:
        """Anzahl Fragen für den Üben-Button im aktiven Fach (gekappt bei 10)."""
        if self._current_subject is None:
            return 0
        uid = self.window.active_user_id
        if uid is None:
            return 0
        n = error_book_queries.count_open(self.conn, uid).get(self._current_subject, 0)
        return min(n, 10)

    def trigger_practice(self) -> None:
        if self._current_subject is None:
            return
        self.window.start_error_book_practice(self._current_subject)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _select_subject(self, subject: str) -> None:
        self._current_subject = subject
        self.reload()

    def _clear_cards(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _refresh_action_button(self) -> None:
        # MainWindow setzt den Action-Button via header.set_page_actions(...)
        # in show_error_book(). reload() informiert nur die Eltern.
        pass


def _make_entry_card(e: ErrorBookEntry) -> QFrame:
    card = QFrame()
    card.setObjectName("assessmentCard")  # Reuse-Stil
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    v = QVBoxLayout(card)
    v.setContentsMargins(18, 14, 18, 14)
    v.setSpacing(8)

    top = QHBoxLayout()
    top.setSpacing(10)
    if e.topic:
        top.addWidget(Pill(e.topic.upper(), subject_variant(e.subject)))
    prompt = QLabel(e.prompt_excerpt)
    prompt.setWordWrap(True)
    prompt.setStyleSheet(f"color: {Semantic.FG}; font-size: 11pt;")
    top.addWidget(prompt, stretch=1)
    v.addLayout(top)

    bottom = QHBoxLayout()
    bottom.setSpacing(8)
    left_text = f"{e.wrong_count}× falsch · zuletzt {fmt_dt(e.last_wrong_at)}"
    left = QLabel(left_text)
    left.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
    bottom.addWidget(left)
    bottom.addStretch(1)
    streak = QLabel(_streak_text(e.consecutive_correct))
    streak.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
    bottom.addWidget(streak)
    v.addLayout(bottom)

    return card


def _streak_text(consecutive_correct: int) -> str:
    if consecutive_correct >= 1:
        return "●○ noch 1× richtig"
    return "○○ noch 2× richtig"
```

- [ ] **Step 4: Run the empty-state test**

Run: `pytest tests/test_error_book_page.py::test_page_empty_state_shows_when_no_errors -v`
Expected: 1 passed

- [ ] **Step 5: Add the remaining 4 UI tests**

```python
# Append to tests/test_error_book_page.py

def test_page_subject_pill_counts(qt_app, conn, uid):
    _import_and_fail(conn, uid, subject="Mathe", topic="A")
    _import_and_fail(conn, uid, subject="Mathe", topic="B")
    _import_and_fail(conn, uid, subject="Englisch", topic="C")
    page = ErrorBookPage(_MockWindow(conn, uid), conn)
    page.reload()
    assert page._subject_buttons["Mathe"].text() == "Mathe · 2"
    assert page._subject_buttons["Englisch"].text() == "Englisch · 1"
    # Andere Fächer sind ungetargeted
    assert page._subject_buttons["Bio"].isEnabled() is False


def test_page_renders_entry_cards_for_active_subject(qt_app, conn, uid):
    _import_and_fail(conn, uid, subject="Mathe", topic="A")
    page = ErrorBookPage(_MockWindow(conn, uid), conn)
    page.reload()
    # 1 Card + 1 stretch in list_layout
    assert page._list_layout.count() >= 1


def test_page_per_subject_empty_state(qt_app, conn, uid):
    _import_and_fail(conn, uid, subject="Mathe", topic="A")
    page = ErrorBookPage(_MockWindow(conn, uid), conn)
    page.reload()
    # Wechsle aktiv zu einem leeren Fach
    page._current_subject = "Englisch"
    page.reload()
    # Page kehrt zu Mathe als default zurück, weil Englisch == 0
    assert page._current_subject == "Mathe"


def test_page_practice_button_count_caps_at_10(qt_app, conn, uid):
    for i in range(15):
        _import_and_fail(conn, uid, subject="Mathe", topic=f"T{i}")
    page = ErrorBookPage(_MockWindow(conn, uid), conn)
    page.reload()
    assert page.practice_button_count() == 10


def test_page_trigger_practice_calls_window(qt_app, conn, uid):
    _import_and_fail(conn, uid, subject="Mathe", topic="A")
    window = _MockWindow(conn, uid)
    page = ErrorBookPage(window, conn)
    page.reload()
    page.trigger_practice()
    assert window.started_practice == "Mathe"
```

- [ ] **Step 6: Run all page tests**

Run: `pytest tests/test_error_book_page.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add src/school_test_engine/ui/pages/error_book.py tests/test_error_book_page.py
git commit -m "feat(ui): ErrorBookPage with subject pills, entry cards, empty states"
```

---

## Task 8: MainWindow-Integration — `show_error_book` + `start_error_book_practice`

**Files:**
- Modify: `src/school_test_engine/ui/main_window.py`
- Test: `tests/test_error_book_main_window.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_error_book_main_window.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import pytest

from PySide6.QtWidgets import QApplication

from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import connect, run_migrations, users_repo, attempts_repo
from school_test_engine.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


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


def _import_and_fail(conn, uid, subject="Mathe"):
    payload = {
        "title": "T", "subject": subject, "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": "X",
            "difficulty": "mittel", "points": 2, "prompt": "P",
            "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "correct": ["a"],
        }],
    }
    test_id = import_from_string(conn, json.dumps(payload), user_id=uid)
    qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,)).fetchone()["id"]
    aid = attempts_repo.start_attempt(conn, test_id, 2, uid)
    attempts_repo.upsert_answer(conn, aid, qid, response=["b"], points_earned=0.0, is_correct=False)
    attempts_repo.finish_attempt(conn, aid, note=6)


def test_show_error_book_swaps_to_page(qt_app, conn, uid):
    window = MainWindow(conn)
    window.set_active_user(uid)
    window.show_error_book()
    assert window.stack.currentWidget() is window.error_book_page


def test_start_error_book_practice_routes_to_runner(qt_app, conn, uid):
    _import_and_fail(conn, uid)
    window = MainWindow(conn)
    window.set_active_user(uid)
    window.start_error_book_practice("Mathe")
    assert window.stack.currentWidget() is window.runner_page


def test_start_error_book_practice_no_errors_does_not_route(qt_app, conn, uid, monkeypatch):
    """0 offene Fehler im Fach → keine Runner-Navigation, ggf. Info-Box."""
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    window = MainWindow(conn)
    window.set_active_user(uid)
    current_before = window.stack.currentWidget()
    window.start_error_book_practice("Mathe")
    assert window.stack.currentWidget() is current_before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_error_book_main_window.py -v`
Expected: FAIL with `AttributeError: 'MainWindow' object has no attribute 'error_book_page'`

- [ ] **Step 3: Wire MainWindow**

Modify `src/school_test_engine/ui/main_window.py` — add import + page instantiation + 2 new methods.

```python
# Edit src/school_test_engine/ui/main_window.py

# 1. Add import (top of imports block, alphabetical order):
from ..error_book import builder as error_book_builder
from .pages.error_book import ErrorBookPage
```

Find the block where existing pages are instantiated (around `self.grades_page = GradesPage(self, conn)`, line ~79). Add right after grades_page:

```python
        self.error_book_page = ErrorBookPage(self, conn)
```

Find where pages are added to the `QStackedWidget` (around line 98). Add `self.error_book_page` after `self.grades_page` in that list.

Add two new methods right after `show_grades`:

```python
    def show_error_book(self) -> None:
        uid = self.active_user_id
        if uid is None:
            return
        ueben_btn = QPushButton("Üben")
        ueben_btn.setObjectName("primary")
        ueben_btn.clicked.connect(self.error_book_page.trigger_practice)
        self.header.set_page_actions([ueben_btn])
        self.error_book_page.reload()
        n = self.error_book_page.practice_button_count()
        ueben_btn.setText(f"Üben ({n})" if n > 0 else "Üben")
        ueben_btn.setEnabled(n > 0)
        self.stack.setCurrentWidget(self.error_book_page)

    def start_error_book_practice(self, subject: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        uid = self.active_user_id
        if uid is None:
            return
        test_id = error_book_builder.build_practice_test(self.conn, uid, subject)
        if test_id is None:
            QMessageBox.information(
                self, "Fehlerheft",
                f"In {subject} gerade keine offenen Fehler.",
            )
            return
        # Check Resume-Pfad: gibt's einen offenen Attempt?
        from ..storage import attempts_repo
        existing_attempt = attempts_repo.find_incomplete_attempt(self.conn, uid, test_id=test_id)
        if existing_attempt is not None:
            self.resume_attempt(existing_attempt["id"])
            return
        # Fresh attempt
        points_total = self.conn.execute(
            "SELECT COALESCE(SUM(points), 0) AS pts FROM questions WHERE test_id = ?",
            (test_id,),
        ).fetchone()["pts"]
        attempt_id = attempts_repo.start_attempt(self.conn, test_id, int(points_total), uid)
        self._return_to_history = False
        self.runner_page.resume(attempt_id)
        self.stack.setCurrentWidget(self.runner_page)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_error_book_main_window.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/main_window.py tests/test_error_book_main_window.py
git commit -m "feat(ui): show_error_book + start_error_book_practice in MainWindow"
```

---

## Task 9: GlobalHeader — Logo-Menü-Eintrag „Fehlerheft"

**Files:**
- Modify: `src/school_test_engine/ui/widgets/global_header.py`
- Test: `tests/test_global_header_error_book.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_global_header_error_book.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.ui.widgets.global_header import GlobalHeader


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


class _MockWindow:
    def show_menu(self): pass
    def show_test_create(self): pass
    def show_events(self): pass
    def show_grades(self): pass
    def show_error_book(self): pass
    def show_profile_picker(self): pass


def test_logo_menu_has_fehlerheft_entry(qt_app):
    header = GlobalHeader(_MockWindow())
    labels = [a.text() for a in header._logo_menu._menu.actions() if not a.isSeparator()]
    assert "Fehlerheft" in labels
    # Reihenfolge: nach Noten, vor Profil wechseln
    idx_noten = labels.index("Noten")
    idx_fehler = labels.index("Fehlerheft")
    idx_profil = labels.index("Profil wechseln")
    assert idx_noten < idx_fehler < idx_profil
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_global_header_error_book.py -v`
Expected: FAIL — `"Fehlerheft" not in labels`

- [ ] **Step 3: Insert the menu item**

```python
# Edit src/school_test_engine/ui/widgets/global_header.py — Zeilen 109-115
# Insert "Fehlerheft" entry between "Noten" and the next separator:

        self._logo_menu = _LogoMenuButton()
        self._logo_menu.add_action("Start", window.show_menu)
        self._logo_menu.add_separator()
        self._logo_menu.add_action("Test erstellen", window.show_test_create)
        self._logo_menu.add_action("Termine", window.show_events)
        self._logo_menu.add_action("Noten", window.show_grades)
        self._logo_menu.add_action("Fehlerheft", window.show_error_book)  # NEU
        self._logo_menu.add_separator()
        self._logo_menu.add_action("Profil wechseln", window.show_profile_picker)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_global_header_error_book.py -v`
Expected: 1 passed

- [ ] **Step 5: Run the existing global_header tests as regression check**

Run: `pytest tests/test_global_header*.py -v`
Expected: alle bisherigen Tests bestehen weiterhin

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/widgets/global_header.py \
        tests/test_global_header_error_book.py
git commit -m "feat(ui): add Fehlerheft entry to logo menu"
```

---

## Task 10: Gaps-Page-Footer — „Fehler nochmal üben →" Button

**Files:**
- Modify: `src/school_test_engine/ui/pages/gaps.py`
- Test: `tests/test_gaps_page_error_book_link.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gaps_page_error_book_link.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.ui.pages.gaps import GapsPage


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


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


class _MockWindow:
    def __init__(self, conn, uid):
        self.conn = conn
        self.active_user_id = uid
        self.show_error_book_called = False

    def show_error_book(self):
        self.show_error_book_called = True


def test_gaps_page_has_footer_button_routing_to_error_book(qt_app, conn, uid):
    window = _MockWindow(conn, uid)
    page = GapsPage(window, conn)
    # Find the button by text
    buttons = page.findChildren(QPushButton)
    matching = [b for b in buttons if "Fehler nochmal" in b.text()]
    assert matching, "Footer-Button 'Fehler nochmal üben' fehlt"
    matching[0].click()
    assert window.show_error_book_called is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gaps_page_error_book_link.py -v`
Expected: FAIL — `"Footer-Button 'Fehler nochmal üben' fehlt"`

- [ ] **Step 3: Add the footer button**

Find the end of `GapsPage.__init__` (after the scroll-area `outer.addWidget(self.scroll, stretch=1)` line, around line 85). Append:

```python
        # Footer-Link zum Fehlerheft (Phase 16)
        footer_row = QHBoxLayout()
        footer_row.addStretch(1)
        self._error_book_btn = QPushButton("Fehler nochmal üben →")
        self._error_book_btn.setObjectName("text")
        self._error_book_btn.clicked.connect(self.window.show_error_book)
        footer_row.addWidget(self._error_book_btn)
        outer.addLayout(footer_row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gaps_page_error_book_link.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/gaps.py tests/test_gaps_page_error_book_link.py
git commit -m "feat(ui): add 'Fehler nochmal üben →' footer button to gaps page"
```

---

## Task 11: End-to-End Loop-Test

**Files:**
- Test: `tests/test_error_book_e2e.py`

- [ ] **Step 1: Write the e2e test**

```python
# tests/test_error_book_e2e.py
import json

import pytest

from school_test_engine.error_book.builder import build_practice_test
from school_test_engine.error_book.queries import list_open_entries
from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import (
    connect, run_migrations, users_repo, attempts_repo,
)


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def _make_payload(title="T", subject="Mathe"):
    return {
        "title": title, "subject": subject, "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "single_choice", "topic": "Bruchrechnung",
            "difficulty": "mittel", "points": 2, "prompt": "Was ist 1/2 + 1/3?",
            "choices": [{"id": "a", "text": "5/6"}, {"id": "b", "text": "1/5"}],
            "correct": ["a"],
        }],
    }


def _answer(conn, uid, test_id, qid, correct: bool):
    points = 2 if correct else 0
    aid = attempts_repo.start_attempt(conn, test_id, 2, uid)
    attempts_repo.upsert_answer(
        conn, aid, qid,
        response=["a"] if correct else ["b"],
        points_earned=points, is_correct=correct,
    )
    attempts_repo.finish_attempt(conn, aid, note=1 if correct else 6)


def test_full_loop_wrong_then_two_correct_via_practice_evicts(conn):
    uid = users_repo.create_user(conn, "Clemens", "🧒")

    # Schritt 1: regulären Test importieren, falsch beantworten
    orig_test = import_from_string(conn, json.dumps(_make_payload()), user_id=uid)
    orig_qid = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (orig_test,)
    ).fetchone()["id"]
    _answer(conn, uid, orig_test, orig_qid, correct=False)

    # Schritt 2: Frage ist im Heft
    assert len(list_open_entries(conn, uid)) == 1

    # Schritt 3: Fehler-Übungs-Test bauen
    practice_test = build_practice_test(conn, uid, subject="Mathe")
    assert practice_test is not None
    practice_qid = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (practice_test,)
    ).fetchone()["id"]
    assert practice_qid != orig_qid

    # Schritt 4: 1× richtig in der Kopie — bleibt im Heft mit streak=1
    _answer(conn, uid, practice_test, practice_qid, correct=True)
    entries = list_open_entries(conn, uid)
    assert len(entries) == 1
    assert entries[0].consecutive_correct == 1

    # Schritt 5: erneut bauen → Resume-Pfad nicht möglich (Attempt finished),
    # neuer Übungs-Test darf gebaut werden
    practice_test_2 = build_practice_test(conn, uid, subject="Mathe")
    assert practice_test_2 != practice_test
    practice_qid_2 = conn.execute(
        "SELECT id FROM questions WHERE test_id = ?", (practice_test_2,)
    ).fetchone()["id"]
    # Schritt 6: 2. richtige Antwort → evicted
    _answer(conn, uid, practice_test_2, practice_qid_2, correct=True)
    assert list_open_entries(conn, uid) == []
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_error_book_e2e.py -v`
Expected: 1 passed

- [ ] **Step 3: Run the full test suite as regression check**

Run: `pytest -q`
Expected: ca. 400 passed (371 + 29 neue, ohne Regressions)

- [ ] **Step 4: Commit**

```bash
git add tests/test_error_book_e2e.py
git commit -m "test(error_book): full-loop e2e — wrong → practice ×2 → evicted"
```

---

## Task 12: Manuelle UI-Verifikation (Offscreen-Render)

**Files:**
- Create: `ux-test/_preview-error-book-empty.png`
- Create: `ux-test/_preview-error-book-with-entries.png`
- Create: `ux-test/_preview-error-book-narrow.png`

- [ ] **Step 1: Render-Snippet für Empty-State**

```python
# Run this in a Python session in the project dir:
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.ui.main_window import MainWindow

app = QApplication([])
conn = connect(":memory:")
run_migrations(conn)
uid = users_repo.create_user(conn, "Clemens Test", "🧒")
window = MainWindow(conn)
window.resize(1280, 800)
window.set_active_user(uid)
window.show_error_book()
window.grab().save("ux-test/_preview-error-book-empty.png")
```

- [ ] **Step 2: Render-Snippet für gefüllten State** (mit 3 Fehlern in 2 Fächern, manuell `import_from_string` + `attempts_repo` driven). Code-Pattern wie in den e2e-Tests.

- [ ] **Step 3: Render-Snippet für Narrow-Mode (768×900)** — gleicher gefüllter State, andere Fenstergröße.

- [ ] **Step 4: Sichtprüfung der 3 Screenshots**

Run: `xdg-open ux-test/_preview-error-book-empty.png` (oder im Bilderviewer öffnen)

Akzeptanzkriterien:
- Empty: zentrierte „Noch keine offenen Fehler — sauber." Card, keine Subject-Pills
- With-Entries: Subject-Pills mit Counts (z.B. „Mathe · 2", „Englisch · 1"), aktives Fach markiert, Card-Liste mit Topic-Pill + Prompt-Excerpt + Bottom-Row, „Üben (2)"-Button im Header
- Narrow: Subject-Pills wrappen in zweite Zeile, Cards bleiben lesbar

- [ ] **Step 5: Kein Commit** (ux-test/ ist in .gitignore — bewusst nicht versioniert)

---

## Self-Review-Notiz

Nach Plan-Schreiben gegen die Spec gecheckt:

- **Spec §5 (Datenmodell):** ✅ Tasks 1, 2, 3 (Frozen-Dataclass + Eviction-Helpers + Query-SQL)
- **Spec §6 (Query-Logik):** ✅ Task 3 (Eligibility + Antwort-Reihe + Subject-Filter + count_open)
- **Spec §7 (Builder):** ✅ Tasks 4 (has_open_errors), 5 (root-Flattening), 6 (build_practice_test inkl. Resume)
- **Spec §8.1-8.3 (Page-Layout + Empty-States):** ✅ Task 7
- **Spec §8.4 (Logo-Menü + Gaps-Footer):** ✅ Tasks 9 + 10
- **Spec §8.5 (MainWindow):** ✅ Task 8 (show_error_book + start_error_book_practice)
- **Spec §9 (Edge-Cases):** ✅ verteilt über Tasks 3, 6, 11 (Test-Cases decken alle Tabellen-Einträge ab)
- **Spec §10 (Tests):** Plan deckt 10+8+5+2+1+2+1 = 29 neue Tests in 7 Dateien — passt ungefähr zur Spec-Schätzung
- **Spec §3 (Nicht-Ziele):** keine Migration, keine neue Tabelle, kein Karten-Modus, kein manuelles Markieren → alles eingehalten

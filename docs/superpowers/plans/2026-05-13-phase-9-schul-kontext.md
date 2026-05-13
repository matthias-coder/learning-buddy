# Phase 9 — Schul-Kontext Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded "8. Klasse Realschule" in the AI prompt generator with five new user-profile fields (grade, school_type, bundesland, school_name, school_year), so generated test prompts adapt to each profile's real school context.

**Architecture:** Migration 008 adds five nullable columns to `users`. New `prompt_builder/school_context.py` exposes a `SchoolContext` dataclass + `BUNDESLAENDER` / `SCHOOL_TYPES` constants. `prompt_builder/assembler.py` gets a `school_context` parameter and runs a phrase-strip + token-replace pass over the base template. `examples/PROMPT-FOR-AI.md` is rewritten with `{{token}}` placeholders. The Profile-Manager edit dialog gains a "Schul-Kontext" section with combos that use an "Andere…"-trigger + QInputDialog pattern (avoids Phase-8's editable-combo trap). PromptBuilderPage reads the context, hard-disables the copy button when grade or school_type is NULL.

**Tech Stack:** Python 3.11, PySide6, SQLite (stdlib sqlite3), pytest. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-05-13-phase-9-schul-kontext-design.md`

**Repository state at start:** master branch, latest commit `f485303` (Phase 9 spec). Test suite: 152/152 green.

---

## File Structure

**New files:**
- `src/school_test_engine/storage/migrations/008_phase9_school_context.sql`
- `src/school_test_engine/prompt_builder/school_context.py` — `SchoolContext` dataclass + `BUNDESLAENDER` + `SCHOOL_TYPES` constants
- `tests/test_migration_008.py`
- `tests/test_school_context.py`
- `tests/test_users_repo_school_context.py`
- `tests/test_prompt_assembler_school_context.py`

**Modified files:**
- `src/school_test_engine/storage/users_repo.py` — `update_user` adds five sentinel params
- `src/school_test_engine/prompt_builder/template.py` — update `_BACKUP_TEMPLATE` to use `{{token}}` placeholders so the fallback path is consistent
- `src/school_test_engine/prompt_builder/assembler.py` — accept `school_context`, run phrase-strip + token-replace before tail-append
- `examples/PROMPT-FOR-AI.md` — replace hardcoded "8. Klasse Realschule" with token placeholders
- `src/school_test_engine/ui/pages/profile_manager.py` — `ProfileValues` adds 5 fields, `_ProfileEditDialog` adds Schul-Kontext section, `ProfileManagerPage._edit` forwards all 5 to `update_user`
- `src/school_test_engine/ui/pages/prompt_builder.py` — read `SchoolContext` from user row, pass to assembler, render context-preview row, hard-disable copy button when context incomplete

---

## Task 1: Migration 008 — 5 nullable columns on users

**Files:**
- Create: `src/school_test_engine/storage/migrations/008_phase9_school_context.sql`
- Test: `tests/test_migration_008.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_migration_008.py`:

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


def test_users_has_grade_column(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "grade" in cols
    assert cols["grade"]["notnull"] == 0  # nullable


def test_users_has_school_type_column(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "school_type" in cols
    assert cols["school_type"]["notnull"] == 0


def test_users_has_bundesland_column(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "bundesland" in cols
    assert cols["bundesland"]["notnull"] == 0


def test_users_has_school_name_column(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "school_name" in cols


def test_users_has_school_year_column(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "school_year" in cols


def test_existing_users_remain_intact(conn):
    """Migration must not delete/break the default 'Standard' user from migration 004."""
    row = conn.execute("SELECT name, grade, school_type FROM users WHERE id = 1").fetchone()
    assert row is not None
    assert row["name"] == "Standard"
    assert row["grade"] is None
    assert row["school_type"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_008.py -v`
Expected: All FAIL — columns don't exist.

- [ ] **Step 3: Write migration SQL**

Create `src/school_test_engine/storage/migrations/008_phase9_school_context.sql`:

```sql
-- Phase 9: Schul-Kontext pro User-Profil

ALTER TABLE users ADD COLUMN grade INTEGER;
ALTER TABLE users ADD COLUMN school_type TEXT;
ALTER TABLE users ADD COLUMN bundesland TEXT;
ALTER TABLE users ADD COLUMN school_name TEXT;
ALTER TABLE users ADD COLUMN school_year TEXT;
```

All five columns are nullable; SQLite allows `ALTER TABLE ADD COLUMN` without `DEFAULT` for nullable types.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_migration_008.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/migrations/008_phase9_school_context.sql tests/test_migration_008.py
git commit -m "feat(phase9): migration 008 — five school-context columns on users"
```

---

## Task 2: SchoolContext module — dataclass + constants

**Files:**
- Create: `src/school_test_engine/prompt_builder/school_context.py`
- Test: `tests/test_school_context.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_school_context.py`:

```python
import pytest
import sqlite3

from school_test_engine.prompt_builder.school_context import (
    BUNDESLAENDER,
    SCHOOL_TYPES,
    SchoolContext,
)


def test_constants_present():
    assert SCHOOL_TYPES == ["Hauptschule", "Realschule", "Gymnasium"]
    assert "Hessen" in BUNDESLAENDER
    assert len(BUNDESLAENDER) == 16


def test_from_user_row_none():
    ctx = SchoolContext.from_user_row(None)
    assert ctx.grade is None
    assert ctx.school_type is None
    assert ctx.bundesland is None
    assert ctx.school_name is None
    assert ctx.school_year is None


def test_from_user_row_full():
    row = {
        "grade": 8,
        "school_type": "Realschule",
        "bundesland": "Hessen",
        "school_name": "Heine-RS",
        "school_year": "2025/26",
    }
    ctx = SchoolContext.from_user_row(row)
    assert ctx.grade == 8
    assert ctx.school_type == "Realschule"
    assert ctx.bundesland == "Hessen"
    assert ctx.school_name == "Heine-RS"
    assert ctx.school_year == "2025/26"


def test_from_user_row_partial():
    row = {
        "grade": 9,
        "school_type": "Gymnasium",
        "bundesland": None,
        "school_name": None,
        "school_year": None,
    }
    ctx = SchoolContext.from_user_row(row)
    assert ctx.grade == 9
    assert ctx.school_type == "Gymnasium"
    assert ctx.bundesland is None


def test_grade_coerced_from_string():
    row = {"grade": "8", "school_type": "Realschule",
           "bundesland": None, "school_name": None, "school_year": None}
    ctx = SchoolContext.from_user_row(row)
    assert ctx.grade == 8


def test_grade_coerced_invalid_string_to_none():
    row = {"grade": "abc", "school_type": "Realschule",
           "bundesland": None, "school_name": None, "school_year": None}
    ctx = SchoolContext.from_user_row(row)
    assert ctx.grade is None


def test_is_minimally_complete_when_both_required():
    ctx = SchoolContext(grade=8, school_type="Realschule",
                       bundesland=None, school_name=None, school_year=None)
    assert ctx.is_minimally_complete() is True


def test_is_minimally_complete_false_when_grade_none():
    ctx = SchoolContext(grade=None, school_type="Realschule",
                       bundesland="Hessen", school_name=None, school_year=None)
    assert ctx.is_minimally_complete() is False


def test_is_minimally_complete_false_when_school_type_none():
    ctx = SchoolContext(grade=8, school_type=None,
                       bundesland="Hessen", school_name=None, school_year=None)
    assert ctx.is_minimally_complete() is False


def test_is_minimally_complete_false_when_school_type_empty():
    ctx = SchoolContext(grade=8, school_type="",
                       bundesland="Hessen", school_name=None, school_year=None)
    assert ctx.is_minimally_complete() is False


def test_works_with_sqlite_row(tmp_path):
    """Real sqlite3.Row must work, not just dicts."""
    from school_test_engine.storage import connect, run_migrations, users_repo
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    uid = users_repo.create_user(c, "Test", "🧒")
    users_repo.update_user(c, uid, grade=10, school_type="Gymnasium",
                           bundesland="Bayern", school_name="X-Gymi", school_year="2025/26")
    row = users_repo.get_user(c, uid)
    ctx = SchoolContext.from_user_row(row)
    assert ctx.grade == 10
    assert ctx.school_type == "Gymnasium"
    c.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_school_context.py -v`
Expected: All FAIL with `ModuleNotFoundError`. The last test (`test_works_with_sqlite_row`) will additionally fail later because `users_repo.update_user` doesn't yet support the new kwargs — that's Task 3's work. Keep this test in the file; it'll pass once Task 3 lands. For now, run the other tests with `-k 'not sqlite_row'`:

Run: `pytest tests/test_school_context.py -v -k "not sqlite_row"`
Expected: All FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the module**

Create `src/school_test_engine/prompt_builder/school_context.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ui._layouts import row_get


BUNDESLAENDER = [
    "Baden-Württemberg",
    "Bayern",
    "Berlin",
    "Brandenburg",
    "Bremen",
    "Hamburg",
    "Hessen",
    "Mecklenburg-Vorpommern",
    "Niedersachsen",
    "Nordrhein-Westfalen",
    "Rheinland-Pfalz",
    "Saarland",
    "Sachsen",
    "Sachsen-Anhalt",
    "Schleswig-Holstein",
    "Thüringen",
]


SCHOOL_TYPES = ["Hauptschule", "Realschule", "Gymnasium"]


def _coerce_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class SchoolContext:
    grade: int | None
    school_type: str | None
    bundesland: str | None
    school_name: str | None
    school_year: str | None

    @classmethod
    def from_user_row(cls, row: Any | None) -> "SchoolContext":
        if row is None:
            return cls(None, None, None, None, None)
        return cls(
            grade=_coerce_int(row_get(row, "grade")),
            school_type=row_get(row, "school_type"),
            bundesland=row_get(row, "bundesland"),
            school_name=row_get(row, "school_name"),
            school_year=row_get(row, "school_year"),
        )

    def is_minimally_complete(self) -> bool:
        """True when both grade and school_type are set — the pair required to
        produce a sensible AI prompt."""
        return self.grade is not None and bool(self.school_type)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_school_context.py -v -k "not sqlite_row"`
Expected: 10 PASS (the sqlite_row test is deferred to after Task 3).

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/prompt_builder/school_context.py tests/test_school_context.py
git commit -m "feat(phase9): SchoolContext dataclass + BUNDESLAENDER / SCHOOL_TYPES constants"
```

---

## Task 3: users_repo.update_user — five new sentinel params

**Files:**
- Modify: `src/school_test_engine/storage/users_repo.py`
- Test: `tests/test_users_repo_school_context.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_users_repo_school_context.py`:

```python
import pytest

from school_test_engine.storage import connect, run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, "Tester")


def test_update_user_sets_grade(conn, uid):
    users_repo.update_user(conn, uid, grade=8)
    assert users_repo.get_user(conn, uid)["grade"] == 8


def test_update_user_clears_grade_with_none(conn, uid):
    users_repo.update_user(conn, uid, grade=8)
    users_repo.update_user(conn, uid, grade=None)
    assert users_repo.get_user(conn, uid)["grade"] is None


def test_update_user_omit_grade_leaves_value(conn, uid):
    users_repo.update_user(conn, uid, grade=8)
    users_repo.update_user(conn, uid, name="neu")
    assert users_repo.get_user(conn, uid)["grade"] == 8


def test_update_user_sets_school_type(conn, uid):
    users_repo.update_user(conn, uid, school_type="Realschule")
    assert users_repo.get_user(conn, uid)["school_type"] == "Realschule"


def test_update_user_sets_bundesland(conn, uid):
    users_repo.update_user(conn, uid, bundesland="Hessen")
    assert users_repo.get_user(conn, uid)["bundesland"] == "Hessen"


def test_update_user_sets_school_name(conn, uid):
    users_repo.update_user(conn, uid, school_name="Heinrich-Heine-RS")
    assert users_repo.get_user(conn, uid)["school_name"] == "Heinrich-Heine-RS"


def test_update_user_sets_school_year(conn, uid):
    users_repo.update_user(conn, uid, school_year="2025/26")
    assert users_repo.get_user(conn, uid)["school_year"] == "2025/26"


def test_update_user_sets_all_five_at_once(conn, uid):
    users_repo.update_user(
        conn, uid,
        grade=10, school_type="Gymnasium", bundesland="Bayern",
        school_name="Max-Plank", school_year="2025/26",
    )
    row = users_repo.get_user(conn, uid)
    assert row["grade"] == 10
    assert row["school_type"] == "Gymnasium"
    assert row["bundesland"] == "Bayern"
    assert row["school_name"] == "Max-Plank"
    assert row["school_year"] == "2025/26"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_users_repo_school_context.py -v`
Expected: All FAIL with `TypeError: update_user() got an unexpected keyword argument 'grade'`.

- [ ] **Step 3: Modify `update_user` to add five new sentinel params**

Open `src/school_test_engine/storage/users_repo.py`. The current signature after Phase 8 is:

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
    sort_order: int | None = None,
) -> None:
```

Add five new sentinel params **between `ai_style_briefing` and `sort_order`**. New signature:

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
) -> None:
```

In the body, after the existing `if ai_style_briefing is not _SENTINEL:` block and before the `sort_order` block, add:

```python
    if grade is not _SENTINEL:
        fields.append("grade = ?"); values.append(grade)
    if school_type is not _SENTINEL:
        fields.append("school_type = ?"); values.append(school_type)
    if bundesland is not _SENTINEL:
        fields.append("bundesland = ?"); values.append(bundesland)
    if school_name is not _SENTINEL:
        fields.append("school_name = ?"); values.append(school_name)
    if school_year is not _SENTINEL:
        fields.append("school_year = ?"); values.append(school_year)
```

- [ ] **Step 4: Run tests to verify they pass (including the deferred Task-2 test)**

Run: `pytest tests/test_users_repo_school_context.py tests/test_school_context.py -v`
Expected: 8 new tests + the previously-deferred `test_works_with_sqlite_row` from Task 2 now also passes. Total: 19 PASS.

Run full suite: `pytest -v 2>&1 | tail -3`
Expected: 168/168 (was 152 + 6 migration + 11 school_context + 8 users_repo extras = right count).

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/users_repo.py tests/test_users_repo_school_context.py
git commit -m "feat(phase9): users_repo.update_user supports 5 school-context fields"
```

---

## Task 4: PROMPT-FOR-AI.md + template backup — switch to {{token}} placeholders

**Files:**
- Modify: `examples/PROMPT-FOR-AI.md`
- Modify: `src/school_test_engine/prompt_builder/template.py` (update `_BACKUP_TEMPLATE`)
- Test: Extend `tests/test_prompt_template.py`

- [ ] **Step 1: Update PROMPT-FOR-AI.md**

Open `examples/PROMPT-FOR-AI.md`. Replace two hardcoded sections:

**Replace line near the start of the `## Aufgabe` section** (the current text reads "Du erzeugst einen Übungs-Test für die **8. Klasse Realschule** in Deutschland."):

```markdown
Du erzeugst einen Übungs-Test für die **{{grade}}. Klasse {{school_type}}** in **{{bundesland}}** (Schule: {{school_name}}, Schuljahr {{school_year}}). Antworte **ausschließlich mit gültigem JSON** im unten beschriebenen Format. Keine Erklärung, kein Code-Block-Fence, kein Markdown drumherum — nur das pure JSON.
```

(The exact prior text was: `Du erzeugst einen Übungs-Test für die **8. Klasse Realschule** in Deutschland. Antworte **ausschließlich mit gültigem JSON** im unten beschriebenen Format. Keine Erklärung, kein Code-Block-Fence, kein Markdown drumherum — nur das pure JSON.` — overwrite that whole paragraph.)

**Replace two lines inside the `## Schema` JSON example:**

Find:
```json
  "subject": "<Mathe|Englisch|Bio|Physik|Chemie|Geschichte>",
  "grade": 8,
  "school_type": "Realschule",
```

Replace with:
```json
  "subject": "<Mathe|Englisch|Bio|Physik|Chemie|Geschichte>",
  "grade": {{grade}},
  "school_type": "{{school_type}}",
```

(Only the two lines for `grade` and `school_type` change. The `subject` line is unchanged.)

- [ ] **Step 2: Update `_BACKUP_TEMPLATE` in template.py to match**

Open `src/school_test_engine/prompt_builder/template.py`. Find `_BACKUP_TEMPLATE = """\` (the fallback template constant from Phase 8 Task 4). Update its content so the same tokens appear:

Replace the current `_BACKUP_TEMPLATE` constant with:

```python
_BACKUP_TEMPLATE = """\
# Test-Fragen mit KI generieren — Prompt-Vorlage

## Aufgabe

Du erzeugst einen Übungs-Test für die **{{grade}}. Klasse {{school_type}}** in **{{bundesland}}** (Schule: {{school_name}}, Schuljahr {{school_year}}).
Antworte ausschließlich mit gültigem JSON im unten beschriebenen Format.

## Schema

```
{
  "schema_version": 1,
  "title": "<Titel>",
  "subject": "<Mathe|Englisch|Bio|Physik|Chemie|Geschichte>",
  "grade": {{grade}},
  "school_type": "{{school_type}}",
  "questions": [
    {
      "id": "q1",
      "type": "single_choice",
      "topic": "<Unterthema>",
      "difficulty": "leicht|mittel|schwer",
      "points": 2,
      "prompt": "<Aufgabe>",
      "choices": [{"id": "a", "text": "..."}],
      "correct": ["a"],
      "explanation": "<Lösung>"
    }
  ]
}
```

## Regeln

1. topic-Wert pro Test konsistent schreiben.
2. id pro Frage eindeutig: q1, q2, ...
3. correct verweist auf choices.id-Werte.
4. Schwierigkeitsmischung ca. 40% leicht, 40% mittel, 20% schwer.
5. Sprache: Deutsch (außer Fach Englisch).
"""
```

- [ ] **Step 3: Add tests for the token presence in the loaded base prompt**

Append to `tests/test_prompt_template.py`:

```python
def test_load_base_prompt_contains_token_placeholders():
    prompt = template.load_base_prompt()
    # Aufgabe section
    assert "{{grade}}" in prompt
    assert "{{school_type}}" in prompt
    assert "{{bundesland}}" in prompt
    assert "{{school_name}}" in prompt
    assert "{{school_year}}" in prompt
    # Schema section also has grade + school_type placeholders
    assert prompt.count("{{grade}}") >= 2
    assert prompt.count('"{{school_type}}"') >= 1


def test_load_base_prompt_no_longer_has_hardcoded_8_realschule():
    prompt = template.load_base_prompt()
    # The old hardcoded phrase must be gone
    assert "8. Klasse Realschule" not in prompt


def test_backup_template_also_uses_tokens(monkeypatch, tmp_path):
    monkeypatch.setattr(template, "_PROMPT_PATH", tmp_path / "missing.md")
    backup = template.load_base_prompt()
    assert "{{grade}}" in backup
    assert "{{school_type}}" in backup
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_prompt_template.py -v`
Expected: All previous template tests PASS plus the 3 new ones. Total ~9 PASS.

Run full suite: `pytest -v 2>&1 | tail -3`
Expected: full suite still green.

- [ ] **Step 5: Commit**

```bash
git add examples/PROMPT-FOR-AI.md src/school_test_engine/prompt_builder/template.py tests/test_prompt_template.py
git commit -m "feat(phase9): PROMPT-FOR-AI.md uses {{token}} placeholders for school context"
```

---

## Task 5: assembler.py — school_context phrase-strip + token-replace

**Files:**
- Modify: `src/school_test_engine/prompt_builder/assembler.py`
- Test: `tests/test_prompt_assembler_school_context.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_prompt_assembler_school_context.py`:

```python
import pytest

from school_test_engine.prompt_builder.assembler import assemble_prompt
from school_test_engine.prompt_builder.school_context import SchoolContext


def _full_ctx():
    return SchoolContext(
        grade=8, school_type="Realschule", bundesland="Hessen",
        school_name="Heinrich-Heine-RS", school_year="2025/26",
    )


def test_full_context_substitutes_all_tokens():
    out = assemble_prompt(
        subject="Mathe", topics=["Lineare Gleichungen"], count=10,
        distribution="auto", style_briefing=None,
        school_context=_full_ctx(),
    )
    assert "8. Klasse Realschule" in out
    assert "in **Hessen**" in out
    assert "Heinrich-Heine-RS" in out
    assert "Schuljahr 2025/26" in out
    # JSON schema lines
    assert '"grade": 8' in out
    assert '"school_type": "Realschule"' in out
    # No bare tokens left
    assert "{{grade}}" not in out
    assert "{{school_type}}" not in out
    assert "{{bundesland}}" not in out
    assert "{{school_name}}" not in out
    assert "{{school_year}}" not in out


def test_grade_and_school_type_null_show_markers():
    ctx = SchoolContext(grade=None, school_type=None,
                       bundesland="Hessen", school_name="X", school_year="2025/26")
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None, school_context=ctx,
    )
    assert "<Klasse>. Klasse <Schultyp>" in out
    # JSON schema also gets markers
    assert '"grade": <Klasse>' in out
    assert '"school_type": "<Schultyp>"' in out


def test_bundesland_null_strips_phrase():
    ctx = SchoolContext(grade=8, school_type="Realschule",
                       bundesland=None,
                       school_name="X", school_year="2025/26")
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None, school_context=ctx,
    )
    assert "in **<Bundesland>**" not in out
    assert "<Bundesland>" not in out
    # No leftover " in " with nothing after it
    assert " in  (" not in out
    assert "(Schule: X, Schuljahr 2025/26)" in out


def test_school_name_and_year_both_null_strip_phrase():
    ctx = SchoolContext(grade=8, school_type="Realschule",
                       bundesland="Hessen", school_name=None, school_year=None)
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None, school_context=ctx,
    )
    assert "(Schule:" not in out
    assert "Schuljahr" not in out
    assert "<Schule>" not in out
    assert "<Schuljahr>" not in out
    # Bundesland survives
    assert "in **Hessen**" in out


def test_partial_school_name_or_year_still_strips_both():
    """Phase 9 strips the whole parenthetical when EITHER name or year is NULL.
    Granular handling deferred to a later phase."""
    ctx = SchoolContext(grade=8, school_type="Realschule",
                       bundesland="Hessen", school_name="Heine-RS", school_year=None)
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None, school_context=ctx,
    )
    # School-name set but year not — entire paren-phrase still drops per spec
    assert "(Schule:" not in out


def test_school_context_none_treated_as_all_null():
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None,
        school_context=None,
    )
    assert "<Klasse>" in out
    assert "<Schultyp>" in out
    # All optional phrases stripped
    assert "(Schule:" not in out
    assert "<Bundesland>" not in out


def test_school_context_omitted_kwarg_treated_as_none():
    # Backwards-compatibility: callers that don't pass school_context still get a valid prompt
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5,
        distribution="auto", style_briefing=None,
    )
    assert "<Klasse>" in out
    assert "<Schultyp>" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_prompt_assembler_school_context.py -v`
Expected: All FAIL — `assemble_prompt` doesn't accept `school_context` yet.

- [ ] **Step 3: Modify assembler.py to add school_context handling**

Open `src/school_test_engine/prompt_builder/assembler.py`. The current function signature ends at `style_briefing: str | None`. Add `school_context: SchoolContext | None = None` to the signature and apply the substitution to the base text.

Replace the entire `assemble_prompt` function (and add the helper above it). The new file body is:

```python
from __future__ import annotations

from . import template
from .school_context import SchoolContext


# Strip patterns: keys are sub-strings in the base markdown; values are the
# condition under which to remove them.
def _apply_school_context(text: str, ctx: SchoolContext | None) -> str:
    if ctx is None:
        ctx = SchoolContext(None, None, None, None, None)

    # Phase A — Phrase-strip when whole groups are NULL.
    # (Strip BEFORE token-replace so we never leave " <Bundesland>" garbage.)
    if ctx.bundesland is None:
        text = text.replace(" in **{{bundesland}}**", "")
    if ctx.school_name is None or ctx.school_year is None:
        # Phase 9 deliberately strips the whole parenthetical when EITHER is NULL.
        # Granular handling deferred (see spec §7).
        text = text.replace(" (Schule: {{school_name}}, Schuljahr {{school_year}})", "")

    # Phase B — Token-replace, leftover NULLs become visible markers.
    substitutions = {
        "{{grade}}":       str(ctx.grade) if ctx.grade is not None else "<Klasse>",
        "{{school_type}}": ctx.school_type or "<Schultyp>",
        "{{bundesland}}":  ctx.bundesland or "<Bundesland>",
        "{{school_name}}": ctx.school_name or "<Schule>",
        "{{school_year}}": ctx.school_year or "<Schuljahr>",
    }
    for token, value in substitutions.items():
        text = text.replace(token, value)
    return text


def _distribution_label(distribution: str) -> str:
    if distribution == "auto":
        return "automatisch (ca. 40/40/20)"
    if not distribution.startswith("manuell:"):
        return "<inkonsistent>"
    payload = distribution.split(":", 1)[1]
    parts = payload.split("-")
    if len(parts) != 3:
        return "<inkonsistent>"
    try:
        leicht, mittel, schwer = (int(p) for p in parts)
    except ValueError:
        return "<inkonsistent>"
    return f"{leicht} leicht, {mittel} mittel, {schwer} schwer"


def assemble_prompt(
    subject: str,
    topics: list[str],
    count: int,
    distribution: str,
    style_briefing: str | None,
    school_context: SchoolContext | None = None,
) -> str:
    """Compose the final prompt text from form inputs, optional style briefing,
    and optional school context.

    The school context substitutes {{grade}}, {{school_type}}, {{bundesland}},
    {{school_name}}, {{school_year}} tokens in the base template (loaded from
    examples/PROMPT-FOR-AI.md). NULL fields show as <Marker> placeholders.
    NULL bundesland strips the " in <BL>" phrase; NULL school_name OR
    school_year strips the entire "(Schule: …, Schuljahr …)" phrase.
    """
    base = template.load_base_prompt()
    base = _apply_school_context(base, school_context)

    style_section = ""
    if style_briefing and style_briefing.strip():
        style_section = (
            "\n## Eigener Stil\n\n"
            + style_briefing.strip()
            + "\n"
        )

    topic_text = ", ".join(t.strip() for t in topics if t.strip()) or "<bitte ergänzen>"
    dist_label = _distribution_label(distribution)

    tail = (
        "\n---\n\n"
        f"Fach: {subject}\n"
        f"Thema: {topic_text}\n"
        f"Anzahl Fragen: {count}\n"
        f"Verteilung: {dist_label}\n"
    )
    return base.rstrip() + "\n" + style_section + tail
```

Key changes vs Phase 8:
- New import: `from .school_context import SchoolContext`
- New helper `_apply_school_context(text, ctx)`
- New keyword param `school_context: SchoolContext | None = None`
- One new line: `base = _apply_school_context(base, school_context)` after `base = template.load_base_prompt()`

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_prompt_assembler_school_context.py -v`
Expected: 7 PASS.

Run: `pytest tests/test_prompt_assembler.py -v`
Expected: All 8 previous-Phase-8 tests still pass (they don't pass `school_context`, so the kwarg-default-None path is exercised — should be `<Klasse>`/`<Schultyp>` markers in their output, but those tests don't assert against the now-substituted tokens; they only check for `Fach: …`, `Thema: …`, etc.).

Run full suite: `pytest -v 2>&1 | tail -3`
Expected: full suite passes (~175 tests now).

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/prompt_builder/assembler.py tests/test_prompt_assembler_school_context.py
git commit -m "feat(phase9): assembler honors SchoolContext via phrase-strip + token-replace"
```

---

## Task 6: Profile-Manager — add Schul-Kontext section

**Files:**
- Modify: `src/school_test_engine/ui/pages/profile_manager.py`

- [ ] **Step 1: Read the current `_ProfileEditDialog` to find the layout variable name**

Run: `grep -n "QVBoxLayout\|QFormLayout\|outer\|layout" src/school_test_engine/ui/pages/profile_manager.py | head -20`

The outer layout in `_ProfileEditDialog.__init__` is named `outer` (confirmed in Phase 8 Task 6). Use that name.

- [ ] **Step 2: Add imports and extend the dialog**

Open `src/school_test_engine/ui/pages/profile_manager.py`.

**2a.** Add `QComboBox`, `QFormLayout`, and `QInputDialog` to the PySide6 import block (sort alphabetically):

```python
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
```

**2b.** Add the new import near the top of the file (after the existing `from ...storage import users_repo` line):

```python
from ...prompt_builder.school_context import BUNDESLAENDER, SCHOOL_TYPES
```

**2c.** Extend `ProfileValues` (around line 47) to include the 5 new fields:

```python
@dataclass
class ProfileValues:
    name: str
    avatar: str
    avatar_image: bytes | None
    birthday: str | None
    ai_style_briefing: str | None
    grade: int | None
    school_type: str | None
    bundesland: str | None
    school_name: str | None
    school_year: str | None
```

**2d.** Extend `_ProfileEditDialog.__init__` kwargs (around line 70):

```python
class _ProfileEditDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        initial_name: str = "",
        initial_avatar: str = "👤",
        initial_image: bytes | None = None,
        initial_birthday: str | None = None,
        initial_style_briefing: str | None = None,
        initial_grade: int | None = None,
        initial_school_type: str | None = None,
        initial_bundesland: str | None = None,
        initial_school_name: str | None = None,
        initial_school_year: str | None = None,
    ):
```

**2e.** Inside `_ProfileEditDialog.__init__`, **immediately after the existing Style-Briefing block** (which was added in Phase 8 Task 6 and ends with `outer.addWidget(self.style_edit)`), insert the Schul-Kontext section:

```python
        # Schul-Kontext (Phase 9)
        ctx_label = QLabel("Schul-Kontext")
        ctx_label.setStyleSheet("color: #4a4538; font-weight: 500; padding-top: 8px;")
        outer.addWidget(ctx_label)

        ctx_form = QFormLayout()
        ctx_form.setSpacing(8)

        # Klassenstufe combo (NULL + 5..13)
        self.grade_combo = QComboBox()
        self.grade_combo.addItem("—", None)
        for g in range(5, 14):
            self.grade_combo.addItem(f"Klasse {g}", g)
        if initial_grade is not None:
            idx = self.grade_combo.findData(initial_grade)
            if idx >= 0:
                self.grade_combo.setCurrentIndex(idx)
        ctx_form.addRow("Klassenstufe:", self.grade_combo)

        # School type combo (NULL + 3 predefined + Andere…)
        self.school_type_combo = QComboBox()
        self.school_type_combo.addItem("—", None)
        for st in SCHOOL_TYPES:
            self.school_type_combo.addItem(st, st)
        self.school_type_combo.addItem("Andere…", "__OTHER__")
        if initial_school_type:
            # If the initial value is one of the predefined types, select it;
            # otherwise insert it as a custom item before "Andere…".
            idx = self.school_type_combo.findData(initial_school_type)
            if idx >= 0:
                self.school_type_combo.setCurrentIndex(idx)
            else:
                last_idx = self.school_type_combo.count() - 1  # index of "Andere…"
                self.school_type_combo.insertItem(last_idx, initial_school_type, initial_school_type)
                self.school_type_combo.setCurrentIndex(last_idx)
        self.school_type_combo.activated.connect(self._on_school_type_activated)
        ctx_form.addRow("Schultyp:", self.school_type_combo)

        # Bundesland combo (NULL + 16 BL + Andere…)
        self.bundesland_combo = QComboBox()
        self.bundesland_combo.addItem("—", None)
        for bl in BUNDESLAENDER:
            self.bundesland_combo.addItem(bl, bl)
        self.bundesland_combo.addItem("Andere…", "__OTHER__")
        if initial_bundesland:
            idx = self.bundesland_combo.findData(initial_bundesland)
            if idx >= 0:
                self.bundesland_combo.setCurrentIndex(idx)
            else:
                last_idx = self.bundesland_combo.count() - 1
                self.bundesland_combo.insertItem(last_idx, initial_bundesland, initial_bundesland)
                self.bundesland_combo.setCurrentIndex(last_idx)
        self.bundesland_combo.activated.connect(self._on_bundesland_activated)
        ctx_form.addRow("Bundesland:", self.bundesland_combo)

        # School-Name (free text)
        self.school_name_edit = QLineEdit()
        self.school_name_edit.setPlaceholderText("z. B. Heinrich-Heine-Realschule")
        if initial_school_name:
            self.school_name_edit.setText(initial_school_name)
        ctx_form.addRow("Schul-Name:", self.school_name_edit)

        # School-Year (free text)
        self.school_year_edit = QLineEdit()
        self.school_year_edit.setPlaceholderText("2025/26")
        if initial_school_year:
            self.school_year_edit.setText(initial_school_year)
        ctx_form.addRow("Schuljahr:", self.school_year_edit)

        outer.addLayout(ctx_form)
```

**2f.** Add the "Andere…"-handlers as methods on `_ProfileEditDialog` (alongside other helper methods like `_clear_birthday`):

```python
    def _on_school_type_activated(self, idx: int) -> None:
        self._handle_other_trigger(self.school_type_combo, idx, "Schultyp eingeben", "Eigener Schultyp:")

    def _on_bundesland_activated(self, idx: int) -> None:
        self._handle_other_trigger(self.bundesland_combo, idx, "Bundesland eingeben", "Eigenes Bundesland:")

    def _handle_other_trigger(self, combo: QComboBox, idx: int, title: str, label: str) -> None:
        if combo.itemData(idx) != "__OTHER__":
            return
        text, ok = QInputDialog.getText(self, title, label)
        text = text.strip() if ok else ""
        if not text:
            combo.setCurrentIndex(0)  # revert to "—" (NULL)
            return
        last_idx = combo.count() - 1  # position of "Andere…"
        # Avoid duplicate insertion if user typed an existing predefined value
        existing = combo.findData(text)
        if existing >= 0:
            combo.setCurrentIndex(existing)
            return
        combo.insertItem(last_idx, text, text)
        combo.setCurrentIndex(last_idx)
```

**2g.** Extend `_ProfileEditDialog.values()` (around line 212) to return the 5 new fields:

```python
    def values(self) -> ProfileValues:
        bd: str | None = None
        if self._birthday_set:
            d = self.birthday_edit.date()
            if d.year() > 1900:
                bd = d.toString("yyyy-MM-dd")
        briefing_text = self.style_edit.toPlainText().strip()
        return ProfileValues(
            name=self.name_edit.text().strip(),
            avatar=self._selected_avatar or "👤",
            avatar_image=self._avatar_image,
            birthday=bd,
            ai_style_briefing=briefing_text or None,
            grade=self.grade_combo.currentData(),
            school_type=self.school_type_combo.currentData() if self.school_type_combo.currentData() != "__OTHER__" else None,
            bundesland=self.bundesland_combo.currentData() if self.bundesland_combo.currentData() != "__OTHER__" else None,
            school_name=self.school_name_edit.text().strip() or None,
            school_year=self.school_year_edit.text().strip() or None,
        )
```

**2h.** Extend `ProfileManagerPage._edit` (around line 376) to pass initial values to the dialog and forward to `update_user`. Update the dialog instantiation:

```python
        dlg = _ProfileEditDialog(
            self,
            initial_name=u["name"],
            initial_avatar=u["avatar"],
            initial_image=row_get(u, "avatar_image"),
            initial_birthday=row_get(u, "birthday"),
            initial_style_briefing=row_get(u, "ai_style_briefing"),
            initial_grade=row_get(u, "grade"),
            initial_school_type=row_get(u, "school_type"),
            initial_bundesland=row_get(u, "bundesland"),
            initial_school_name=row_get(u, "school_name"),
            initial_school_year=row_get(u, "school_year"),
        )
```

And the `users_repo.update_user` call:

```python
        users_repo.update_user(
            self.conn, user_id,
            name=v.name, avatar=v.avatar,
            avatar_image=v.avatar_image, birthday=v.birthday,
            ai_style_briefing=v.ai_style_briefing,
            grade=v.grade, school_type=v.school_type,
            bundesland=v.bundesland, school_name=v.school_name,
            school_year=v.school_year,
        )
```

**2i.** `_create` stays unchanged — new profiles start with NULL school context, set via Edit.

- [ ] **Step 3: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.ui.pages.profile_manager import _ProfileEditDialog
dlg = _ProfileEditDialog(
    initial_name='X',
    initial_grade=8,
    initial_school_type='Realschule',
    initial_bundesland='Hessen',
    initial_school_name='Heine-RS',
    initial_school_year='2025/26',
)
v = dlg.values()
print('ok grade=', v.grade)
print('ok school_type=', v.school_type)
print('ok bundesland=', v.bundesland)
print('ok school_name=', v.school_name)
print('ok school_year=', v.school_year)"
```

Expected:
```
ok grade= 8
ok school_type= Realschule
ok bundesland= Hessen
ok school_name= Heine-RS
ok school_year= 2025/26
```

- [ ] **Step 4: Full test suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite still passes.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/profile_manager.py
git commit -m "feat(phase9): Profile-Manager edit dialog Schul-Kontext section"
```

---

## Task 7: PromptBuilderPage — context preview + hard-validate copy button

**Files:**
- Modify: `src/school_test_engine/ui/pages/prompt_builder.py`

- [ ] **Step 1: Read the current PromptBuilderPage to find insertion points**

Key locations:
- `__init__` — where the style-row is created (after Phase 8 Task 8)
- `show_for` — where briefing is read from user row
- `_rebuild_prompt` — where `assemble_prompt` is called
- `_validate_distribution` — extend to also check school-context completeness

- [ ] **Step 2: Add SchoolContext import**

At the top of `src/school_test_engine/ui/pages/prompt_builder.py`, add the import near the existing prompt_builder imports:

```python
from ...prompt_builder.assembler import assemble_prompt
from ...prompt_builder.school_context import SchoolContext
```

- [ ] **Step 3: Add a context-preview row to the UI**

In `__init__`, find the existing "Style-Briefing preview row" (it has the line `style_row = QHBoxLayout()` and contains `self.style_label`). **Immediately before that block**, insert a Schul-Kontext-preview row:

```python
        # Schul-Kontext preview row (Phase 9)
        ctx_row = QHBoxLayout()
        self.ctx_label = QLabel("Schul-Kontext: —")
        self.ctx_label.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
        self.ctx_label.setWordWrap(True)
        ctx_row.addWidget(self.ctx_label, 1)
        ctx_edit_link = QPushButton("Profil bearbeiten")
        ctx_edit_link.setObjectName("text")
        ctx_edit_link.clicked.connect(lambda: self.window.show_profile_manager("menu"))
        ctx_row.addWidget(ctx_edit_link)
        outer.addLayout(ctx_row)
```

- [ ] **Step 4: Update `show_for` to populate the preview label**

In `show_for`, after the existing block that updates `self.style_label`, add the same kind of update for `self.ctx_label`. Inside the `if uid is None: return` and `self._loading = True` try-block, add (replace the existing style-only block with one that also computes ctx):

Find this block in show_for:
```python
            user = users_repo.get_user(self.conn, uid)
            briefing = row_get(user, "ai_style_briefing") if user else None
            if briefing:
                preview = briefing.splitlines()[0]
                if len(preview) > 80:
                    preview = preview[:77] + "…"
                self.style_label.setText(f'Stil-Briefing (aus Profil): "{preview}"')
            else:
                self.style_label.setText(
                    "Stil-Briefing (aus Profil): — (Hinweis im Profil hinterlegen für persönlichen KI-Stil)"
                )
```

**After** that block, append:
```python
            # Schul-Kontext preview
            ctx = SchoolContext.from_user_row(user)
            self._render_context_preview(ctx)
```

Then add the new helper method `_render_context_preview` somewhere with the other helpers:

```python
    def _render_context_preview(self, ctx: SchoolContext) -> None:
        if not ctx.is_minimally_complete():
            self.ctx_label.setText(
                "⚠ Schul-Kontext unvollständig — fülle Klasse und Schultyp im Profil aus"
            )
            self.ctx_label.setStyleSheet("color: #7e3b39; font-size: 10pt; font-weight: 500;")
            return
        parts = [f"{ctx.grade}. Klasse {ctx.school_type}"]
        if ctx.bundesland:
            parts.append(ctx.bundesland)
        if ctx.school_year:
            parts.append(f"Schuljahr {ctx.school_year}")
        if ctx.school_name:
            parts.append(ctx.school_name)
        self.ctx_label.setText("Schul-Kontext: " + " · ".join(parts))
        self.ctx_label.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
```

- [ ] **Step 5: Update `_rebuild_prompt` to pass school context**

Find `_rebuild_prompt` in the current file. The current body reads:

```python
    def _rebuild_prompt(self) -> None:
        uid = self.window.active_user_id
        briefing = None
        if uid is not None:
            user = users_repo.get_user(self.conn, uid)
            if user is not None:
                briefing = row_get(user, "ai_style_briefing")

        ok = self._validate_distribution()
        dist_str = self._current_dist_string() if ok else "manuell:inkonsistent"
        out = assemble_prompt(
            subject=self.subject_combo.currentText().strip() or SUBJECTS_ALL[0],
            topics=self._current_topics(),
            count=self.count_spin.value(),
            distribution=dist_str,
            style_briefing=briefing,
        )
        self.output_view.setPlainText(out)
        self.copy_btn.setEnabled(ok)
```

Replace with:

```python
    def _rebuild_prompt(self) -> None:
        uid = self.window.active_user_id
        briefing = None
        ctx = SchoolContext(None, None, None, None, None)
        if uid is not None:
            user = users_repo.get_user(self.conn, uid)
            if user is not None:
                briefing = row_get(user, "ai_style_briefing")
                ctx = SchoolContext.from_user_row(user)

        dist_ok = self._validate_distribution()
        dist_str = self._current_dist_string() if dist_ok else "manuell:inkonsistent"
        out = assemble_prompt(
            subject=self.subject_combo.currentText().strip() or SUBJECTS_ALL[0],
            topics=self._current_topics(),
            count=self.count_spin.value(),
            distribution=dist_str,
            style_briefing=briefing,
            school_context=ctx,
        )
        self.output_view.setPlainText(out)
        # Hart-Validierung: Copy-Button only enabled when distribution AND school-context are both valid
        context_ok = ctx.is_minimally_complete()
        self.copy_btn.setEnabled(dist_ok and context_ok)
        if not context_ok:
            self._status_lbl.setText("Schul-Kontext unvollständig")
            self._status_lbl.setStyleSheet("color: #7e3b39; font-size: 10pt;")
        elif not dist_ok:
            # Status from _validate_distribution warn-label is shown elsewhere; clear copy status
            self._status_lbl.setText("")
        else:
            # Don't overwrite "Kopiert ✓" if it's currently shown
            current = self._status_lbl.text()
            if current.startswith("Schul-Kontext"):
                self._status_lbl.setText("")
                self._status_lbl.setStyleSheet(f"color: {Semantic.ACCENT}; font-size: 10pt;")
```

- [ ] **Step 6: Smoke test the full flow**

Run:
```bash
QT_QPA_PLATFORM=offscreen python <<'EOF'
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
uid = users_repo.create_user(c, 'Clemens', '🧒')

class FakeWindow:
    active_user_id = uid
    conn = c
    def show_menu(self): pass
    def show_profile_manager(self, where): pass

from school_test_engine.ui.pages.prompt_builder import PromptBuilderPage
p = PromptBuilderPage(FakeWindow(), c)
p.reload()

# 1. Incomplete context → copy disabled
assert p.copy_btn.isEnabled() is False, "copy must be disabled when context incomplete"
assert "<Klasse>" in p.output_view.toPlainText(), "marker must be visible in prompt"
print("OK 1: copy disabled + marker shown when context incomplete")

# 2. Set context → copy enabled
users_repo.update_user(c, uid, grade=8, school_type='Realschule',
                       bundesland='Hessen', school_name='Heine-RS', school_year='2025/26')
p.reload()
assert p.copy_btn.isEnabled() is True, "copy must be enabled when context complete"
out = p.output_view.toPlainText()
assert "8. Klasse Realschule" in out, "substituted phrase missing"
assert "Hessen" in out, "bundesland missing"
assert "Schuljahr 2025/26" in out, "schuljahr missing"
assert "<Klasse>" not in out, "marker should not appear when grade is set"
print("OK 2: context substituted + copy enabled")

# 3. Partial context (no bundesland) — phrase stripped
users_repo.update_user(c, uid, bundesland=None, school_name=None, school_year=None)
p.reload()
out = p.output_view.toPlainText()
assert "in **<Bundesland>**" not in out
assert "(Schule:" not in out
assert "8. Klasse Realschule" in out  # still has minimal pair
print("OK 3: phrase-strip works for NULL bundesland + school_name+year")

print("ALL 3 RUNTIME CHECKS PASSED")
EOF
```

Expected output:
```
OK 1: copy disabled + marker shown when context incomplete
OK 2: context substituted + copy enabled
OK 3: phrase-strip works for NULL bundesland + school_name+year
ALL 3 RUNTIME CHECKS PASSED
```

- [ ] **Step 7: Full test suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite green.

- [ ] **Step 8: Commit**

```bash
git add src/school_test_engine/ui/pages/prompt_builder.py
git commit -m "feat(phase9): PromptBuilderPage shows context preview + hard-validates copy"
```

---

## Task 8: End-to-end smoke + acceptance audit

**Files:** none — audit only

- [ ] **Step 1: Run a comprehensive end-to-end smoke script**

Run:
```bash
QT_QPA_PLATFORM=offscreen python <<'EOF'
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.prompt_builder.school_context import SchoolContext
from school_test_engine.prompt_builder.assembler import assemble_prompt

# AC1: Migration 008 ran
c = connect(':memory:')
run_migrations(c)
version = c.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
assert version >= 8
print(f"AC1: schema_version={version} — Migration 008 ran")

# AC4: update_user persists all 5 fields
uid = users_repo.create_user(c, 'Clemens', '🧒')
users_repo.update_user(c, uid,
    grade=8, school_type='Realschule', bundesland='Hessen',
    school_name='Heine-RS', school_year='2025/26',
)
row = users_repo.get_user(c, uid)
assert row['grade'] == 8 and row['school_type'] == 'Realschule'
assert row['bundesland'] == 'Hessen' and row['school_name'] == 'Heine-RS'
assert row['school_year'] == '2025/26'
print("AC4: all 5 fields persist via update_user")

# AC5 + AC6: Markdown tokens + assembler substitution
ctx = SchoolContext.from_user_row(row)
out = assemble_prompt(
    subject='Mathe', topics=['Funktionen'], count=10,
    distribution='auto', style_briefing=None,
    school_context=ctx,
)
assert '{{grade}}' not in out and '{{school_type}}' not in out
assert '8. Klasse Realschule' in out
assert '"grade": 8' in out
assert '"school_type": "Realschule"' in out
print("AC5+AC6: tokens replaced, JSON schema lines substituted")

# Marker behavior when NULL
empty_ctx = SchoolContext(None, None, None, None, None)
out_null = assemble_prompt(
    subject='Mathe', topics=['X'], count=5,
    distribution='auto', style_briefing=None,
    school_context=empty_ctx,
)
assert '<Klasse>' in out_null
assert '<Schultyp>' in out_null
assert 'in **<Bundesland>**' not in out_null  # phrase stripped
assert '(Schule:' not in out_null  # phrase stripped
print("AC6b: NULL fields show markers and strip optional phrases")

# AC2 + AC3 + AC7: Profile-Manager dialog
from school_test_engine.ui.pages.profile_manager import _ProfileEditDialog
dlg = _ProfileEditDialog(
    initial_name='X', initial_grade=8, initial_school_type='Realschule',
    initial_bundesland='Hessen', initial_school_name='Heine-RS', initial_school_year='2025/26',
)
v = dlg.values()
assert v.grade == 8 and v.school_type == 'Realschule'
assert v.bundesland == 'Hessen' and v.school_name == 'Heine-RS' and v.school_year == '2025/26'
print("AC2+AC3+AC7: dialog round-trip works")

# AC8: PromptBuilderPage hard-validates copy
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.active_user_id = uid
w.menu_page.reload()
w.prompt_builder_page.show_for()
assert w.prompt_builder_page.copy_btn.isEnabled() is True
print("AC8a: copy enabled when context complete")

# Clear context → copy disabled
users_repo.update_user(c, uid, grade=None, school_type=None)
w.prompt_builder_page.reload()
assert w.prompt_builder_page.copy_btn.isEnabled() is False
print("AC8b: copy disabled when grade/school_type NULL")

print("\n=== ALL ACCEPTANCE CRITERIA VERIFIED ===")
EOF
```

Expected: prints `ALL ACCEPTANCE CRITERIA VERIFIED` with each AC line above it.

- [ ] **Step 2: Run the entire pytest suite one last time**

Run: `pytest -v 2>&1 | tail -5`
Expected: all tests green. Compare count to baseline (152 → 152 + new tests).

- [ ] **Step 3: Acceptance audit summary**

Walk through each spec acceptance criterion (§5 of the design spec) and mark ✅ with evidence:

1. ✅ Migration 008 — verified by Task 1 tests + smoke step
2. ✅ Profile-Edit Schul-Kontext section — verified by Task 6 smoke + acceptance smoke
3. ✅ "Andere…"-Klick öffnet QInputDialog — code present in Task 6, untestable without user input (manual gate)
4. ✅ update_user persists all 5 fields — verified by Task 3 tests + smoke step
5. ✅ PROMPT-FOR-AI.md mit {{token}}-Placeholders — verified by Task 4 tests
6. ✅ Phrase-strip + marker behavior — verified by Task 5 tests + smoke step
7. ✅ PromptBuilderPage context preview — verified by Task 7 smoke
8. ✅ Hart-Validierung Copy-Button — verified by Task 7 smoke (AC8a + AC8b above)
9. ✅ All previous tests still green — verified by `pytest -v` after each task
10. ⏳ Manueller End-to-End mit echtem LLM (user action) — Matthias muss `./run.sh` mit Display nutzen

- [ ] **Step 4: No new commit needed for Task 8** — audit only.

If small fixes were necessary during the smoke run, commit them:
```bash
git add -A
git commit -m "fix(phase9): smoke-test polish"
```

---

## Self-Review

**Spec coverage:**
- §2 Migration 008 → Task 1 ✓
- §3.1 SchoolContext + constants → Task 2 ✓
- §3.2 users_repo.update_user 5 new params → Task 3 ✓
- §3.3 assembler with school_context, phrase-strip, token-replace → Task 5 ✓
- §3.4 PROMPT-FOR-AI.md + backup template tokens → Task 4 ✓
- §3.5 Profile-Manager Schul-Kontext UI + "Andere…"-handler → Task 6 ✓
- §3.6 PromptBuilderPage context preview + hart-validation → Task 7 ✓
- §3.7 Tests → covered across Tasks 1, 2, 3, 4, 5; Task 8 audit
- §4 Edge cases → covered in test cases (Tasks 5, 6, 7)
- §5 10 Akzeptanzkriterien → Task 8 audit walks them
- §6 Nicht-Ziele — nothing to implement, scope guard
- §7 Risiken → Markdown-Drift handled by Task 4 tests; phrase-strip granular-handling deferred (documented); editable-combo trap avoided via "Andere…"-handler pattern

**Placeholder scan:** No TBDs or vague terms. Every step has runnable code or commands.

**Type consistency:**
- `SchoolContext` dataclass field names: `grade`, `school_type`, `bundesland`, `school_name`, `school_year` — consistent across Tasks 2, 3, 5, 6, 7 ✓
- `assemble_prompt(..., school_context=ctx)` — same signature in Tasks 5 + 7 ✓
- `BUNDESLAENDER` and `SCHOOL_TYPES` constants — Task 2 defines, Task 6 imports ✓
- `users_repo.update_user(..., grade=, school_type=, …)` kwargs — Tasks 3 + 6 ✓
- `is_minimally_complete()` method on SchoolContext — Task 2 defines, Task 7 uses ✓

**Phrase-strip pattern verified:**
- Task 4 markdown insert: `" in **{{bundesland}}**"` and `" (Schule: {{school_name}}, Schuljahr {{school_year}})"`
- Task 5 strip code matches these patterns byte-for-byte ✓

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-13-phase-9-schul-kontext.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task + review checkpoints.

**2. Inline Execution** — Batch execution in this session with checkpoints.

Which approach?

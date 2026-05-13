# Phase 8 — Test bauen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-app AI-Prompt-Generator that builds the existing `PROMPT-FOR-AI.md` template from form inputs and a per-profile style briefing, wires it to ExamCards for "KA vorbereiten"-Flow, and remembers the last topic per subject.

**Architecture:** New `prompt_builder/` domain package (parallel to `cockpit/`/`study/`) with `template.py` (parses `examples/PROMPT-FOR-AI.md` at runtime, strips two TODO sections) and `assembler.py` (composes final prompt from inputs + style briefing). Migration 007 adds `users.ai_style_briefing` column and a `prompt_drafts` table. New `PromptBuilderPage` with live-built prompt preview + copy-to-clipboard. ExamCard's pre-existing `practice_clicked` signal gets wired up.

**Tech Stack:** Python 3.11, PySide6, SQLite (stdlib sqlite3), pytest. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-05-13-phase-8-test-bauen-design.md`

**Repository state at start:** master branch, latest commit `49c538e` (Phase 8 spec). Test suite: 122/122 green.

---

## File Structure

**New files:**
- `src/school_test_engine/storage/migrations/007_phase8_prompt_builder.sql`
- `src/school_test_engine/storage/prompt_drafts_repo.py`
- `src/school_test_engine/prompt_builder/__init__.py` (empty package marker)
- `src/school_test_engine/prompt_builder/template.py`
- `src/school_test_engine/prompt_builder/assembler.py`
- `src/school_test_engine/ui/pages/prompt_builder.py`
- `tests/test_migration_007.py`
- `tests/test_prompt_drafts_repo.py`
- `tests/test_prompt_template.py`
- `tests/test_prompt_assembler.py`

**Modified files:**
- `src/school_test_engine/storage/users_repo.py` — `update_user` adds `ai_style_briefing` sentinel param
- `src/school_test_engine/ui/pages/profile_manager.py` — `_ProfileEditDialog` adds Style-Briefing field
- `src/school_test_engine/ui/widgets/exam_card.py` — adds "✨ Test bauen" button next to "Note eintragen"
- `src/school_test_engine/ui/pages/menu.py` — adds "📝 Test bauen" top-bar button + wires `practice_clicked`
- `src/school_test_engine/ui/main_window.py` — registers `PromptBuilderPage`, adds `show_prompt_builder()`
- `src/school_test_engine/ui/style.qss` — appends Phase 8 styles

---

## Task 1: Migration 007 — ai_style_briefing + prompt_drafts

**Files:**
- Create: `src/school_test_engine/storage/migrations/007_phase8_prompt_builder.sql`
- Test: `tests/test_migration_007.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_migration_007.py`:

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


def test_users_has_ai_style_briefing_column(conn):
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "ai_style_briefing" in cols


def test_prompt_drafts_table_exists(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='prompt_drafts'"
    ).fetchone()
    assert row is not None


def test_prompt_drafts_composite_primary_key(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (2, 'Test', '👤', 1, '2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.execute(
        "INSERT INTO prompt_drafts (user_id, subject, last_topic, last_count, last_dist) "
        "VALUES (2, 'Mathe', 'Funktionen', 10, 'auto')"
    )
    # Duplicate (user_id, subject) must fail
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO prompt_drafts (user_id, subject, last_topic, last_count, last_dist) "
            "VALUES (2, 'Mathe', 'X', 10, 'auto')"
        )


def test_prompt_drafts_cascade_on_user_delete(conn):
    conn.execute(
        "INSERT INTO users (id, name, avatar, sort_order, created_at) "
        "VALUES (3, 'Test', '👤', 2, '2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO prompt_drafts (user_id, subject, last_topic, last_count, last_dist) "
        "VALUES (3, 'Mathe', 'X', 10, 'auto')"
    )
    conn.commit()
    conn.execute("DELETE FROM users WHERE id = 3")
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) FROM prompt_drafts WHERE user_id = 3"
    ).fetchone()[0] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_007.py -v`
Expected: All FAIL ("ai_style_briefing" not in cols, no such table prompt_drafts).

- [ ] **Step 3: Write migration SQL**

Create `src/school_test_engine/storage/migrations/007_phase8_prompt_builder.sql`:

```sql
-- Phase 8: Test bauen — KI-Stil-Briefing pro User + Prompt-Drafts pro (User, Fach)

ALTER TABLE users ADD COLUMN ai_style_briefing TEXT;

CREATE TABLE IF NOT EXISTS prompt_drafts (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject     TEXT    NOT NULL,
    last_topic  TEXT,
    last_count  INTEGER NOT NULL DEFAULT 10,
    last_dist   TEXT    NOT NULL DEFAULT 'auto',
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, subject)
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migration_007.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/migrations/007_phase8_prompt_builder.sql tests/test_migration_007.py
git commit -m "feat(phase8): migration 007 — ai_style_briefing + prompt_drafts table"
```

---

## Task 2: users_repo.update_user — add ai_style_briefing param

**Files:**
- Modify: `src/school_test_engine/storage/users_repo.py`
- Modify: `tests/test_users_repo.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_users_repo.py`:

```python
def test_update_user_ai_style_briefing(conn):
    uid = users_repo.create_user(conn, "Stil-Tester")
    users_repo.update_user(conn, uid, ai_style_briefing="Schreibstil: Du-Form.")
    row = users_repo.get_user(conn, uid)
    assert row["ai_style_briefing"] == "Schreibstil: Du-Form."


def test_update_user_clear_ai_style_briefing_with_none(conn):
    uid = users_repo.create_user(conn, "Stil-Tester")
    users_repo.update_user(conn, uid, ai_style_briefing="X")
    users_repo.update_user(conn, uid, ai_style_briefing=None)
    row = users_repo.get_user(conn, uid)
    assert row["ai_style_briefing"] is None


def test_update_user_omitting_ai_style_briefing_leaves_it(conn):
    uid = users_repo.create_user(conn, "Stil-Tester")
    users_repo.update_user(conn, uid, ai_style_briefing="Bleibt")
    users_repo.update_user(conn, uid, name="neu")
    row = users_repo.get_user(conn, uid)
    assert row["ai_style_briefing"] == "Bleibt"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_users_repo.py -v -k ai_style`
Expected: 3 FAIL.

- [ ] **Step 3: Modify `update_user` in users_repo.py**

Open `src/school_test_engine/storage/users_repo.py` and add the new sentinel-pattern parameter to `update_user`. The signature becomes:

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

In the body, after the existing `if birthday is not _SENTINEL:` block, add:

```python
    if ai_style_briefing is not _SENTINEL:
        fields.append("ai_style_briefing = ?"); values.append(ai_style_briefing)
```

(Insert it before the `sort_order` block to keep grouping with the other sentinel-flagged optional fields.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_users_repo.py -v`
Expected: All PASS (previous 7 + 3 new = 10).

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/users_repo.py tests/test_users_repo.py
git commit -m "feat(phase8): users_repo.update_user supports ai_style_briefing with sentinel"
```

---

## Task 3: prompt_drafts_repo

**Files:**
- Create: `src/school_test_engine/storage/prompt_drafts_repo.py`
- Test: `tests/test_prompt_drafts_repo.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_prompt_drafts_repo.py`:

```python
import pytest

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import prompt_drafts_repo


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


def test_upsert_creates_row(conn, uid):
    prompt_drafts_repo.upsert(
        conn, uid, "Mathe",
        last_topic="Funktionen", last_count=10, last_dist="auto",
    )
    row = prompt_drafts_repo.get(conn, uid, "Mathe")
    assert row is not None
    assert row["last_topic"] == "Funktionen"
    assert row["last_count"] == 10
    assert row["last_dist"] == "auto"


def test_upsert_updates_existing_row(conn, uid):
    prompt_drafts_repo.upsert(
        conn, uid, "Mathe",
        last_topic="A", last_count=5, last_dist="auto",
    )
    prompt_drafts_repo.upsert(
        conn, uid, "Mathe",
        last_topic="B", last_count=8, last_dist="manuell:3-3-2",
    )
    rows = conn.execute("SELECT * FROM prompt_drafts WHERE user_id = ? AND subject = ?", (uid, "Mathe")).fetchall()
    assert len(rows) == 1
    assert rows[0]["last_topic"] == "B"
    assert rows[0]["last_count"] == 8
    assert rows[0]["last_dist"] == "manuell:3-3-2"


def test_get_returns_none_when_missing(conn, uid):
    assert prompt_drafts_repo.get(conn, uid, "Mathe") is None


def test_list_for_user_returns_all_subjects(conn, uid):
    prompt_drafts_repo.upsert(conn, uid, "Mathe", last_topic="A", last_count=10, last_dist="auto")
    prompt_drafts_repo.upsert(conn, uid, "Bio", last_topic="B", last_count=8, last_dist="auto")
    rows = prompt_drafts_repo.list_for_user(conn, uid)
    assert len(rows) == 2
    assert {r["subject"] for r in rows} == {"Mathe", "Bio"}


def test_user_isolation(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    prompt_drafts_repo.upsert(conn, a, "Mathe", last_topic="A-Mathe", last_count=10, last_dist="auto")
    assert prompt_drafts_repo.get(conn, a, "Mathe")["last_topic"] == "A-Mathe"
    assert prompt_drafts_repo.get(conn, b, "Mathe") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_prompt_drafts_repo.py -v`
Expected: All FAIL with import error.

- [ ] **Step 3: Write the repo module**

Create `src/school_test_engine/storage/prompt_drafts_repo.py`:

```python
from __future__ import annotations

import sqlite3


def upsert(
    conn: sqlite3.Connection,
    user_id: int,
    subject: str,
    *,
    last_topic: str | None,
    last_count: int,
    last_dist: str,
) -> None:
    conn.execute(
        """
        INSERT INTO prompt_drafts
            (user_id, subject, last_topic, last_count, last_dist, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, subject) DO UPDATE SET
            last_topic = excluded.last_topic,
            last_count = excluded.last_count,
            last_dist  = excluded.last_dist,
            updated_at = excluded.updated_at
        """,
        (user_id, subject, last_topic, last_count, last_dist),
    )
    conn.commit()


def get(
    conn: sqlite3.Connection, user_id: int, subject: str
) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT * FROM prompt_drafts WHERE user_id = ? AND subject = ?",
        (user_id, subject),
    )
    return cur.fetchone()


def list_for_user(
    conn: sqlite3.Connection, user_id: int
) -> list[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM prompt_drafts WHERE user_id = ? ORDER BY updated_at DESC",
        (user_id,),
    )
    return cur.fetchall()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_prompt_drafts_repo.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/prompt_drafts_repo.py tests/test_prompt_drafts_repo.py
git commit -m "feat(phase8): prompt_drafts_repo upsert/get/list (per user+subject)"
```

---

## Task 4: prompt_builder/template.py — parse PROMPT-FOR-AI.md

**Files:**
- Create: `src/school_test_engine/prompt_builder/__init__.py` (empty)
- Create: `src/school_test_engine/prompt_builder/template.py`
- Test: `tests/test_prompt_template.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_prompt_template.py`:

```python
import pytest
from pathlib import Path

from school_test_engine.prompt_builder import template


def test_load_base_prompt_strips_todo_section():
    prompt = template.load_base_prompt()
    assert "## TODO MATTHIAS" not in prompt
    assert "<dein Stil-Briefing hier>" not in prompt


def test_load_base_prompt_strips_anhaengen_section():
    prompt = template.load_base_prompt()
    assert "## Anhängen am Ende" not in prompt
    assert "Fach: <z.B. Mathe>" not in prompt


def test_load_base_prompt_keeps_aufgabe_section():
    prompt = template.load_base_prompt()
    assert "## Aufgabe" in prompt
    assert "8. Klasse Realschule" in prompt


def test_load_base_prompt_keeps_schema_section():
    prompt = template.load_base_prompt()
    assert "## Schema" in prompt
    assert "schema_version" in prompt


def test_load_base_prompt_keeps_regeln_section():
    prompt = template.load_base_prompt()
    assert "## Regeln" in prompt
    assert "topic" in prompt


def test_load_base_prompt_falls_back_when_file_missing(monkeypatch, tmp_path):
    # Point to a non-existent path
    monkeypatch.setattr(template, "_PROMPT_PATH", tmp_path / "missing.md")
    prompt = template.load_base_prompt()
    # Backup must contain Schema definition at minimum
    assert "schema_version" in prompt
    assert "## Aufgabe" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_prompt_template.py -v`
Expected: All FAIL with import error.

- [ ] **Step 3: Write the template module**

Create `src/school_test_engine/prompt_builder/__init__.py` (empty).

Create `src/school_test_engine/prompt_builder/template.py`:

```python
from __future__ import annotations

import re
from pathlib import Path


_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "PROMPT-FOR-AI.md"
)


# Minimal fallback if examples/PROMPT-FOR-AI.md is missing. Keeps the schema
# definition so generated tests remain importable. Update if the schema changes.
_BACKUP_TEMPLATE = """\
# Test-Fragen mit KI generieren — Prompt-Vorlage

## Aufgabe

Du erzeugst einen Übungs-Test für die 8. Klasse Realschule in Deutschland.
Antworte ausschließlich mit gültigem JSON im unten beschriebenen Format.

## Schema

```
{
  "schema_version": 1,
  "title": "<Titel>",
  "subject": "<Mathe|Englisch|Bio|Physik|Chemie|Geschichte>",
  "grade": 8,
  "school_type": "Realschule",
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


def _strip_section_to_separator(text: str, header_marker: str) -> str:
    """Removes a section starting with `header_marker` until the next `---` line
    (or end of file)."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        if not skipping and line.startswith(header_marker):
            skipping = True
            continue
        if skipping:
            if line.strip() == "---":
                skipping = False
                # consume the separator itself too — drop the orphan `---`
                continue
            continue
        out.append(line)
    return "".join(out)


def _strip_section_to_end(text: str, header_marker: str) -> str:
    """Removes a section starting with `header_marker` until end of file."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        if line.startswith(header_marker):
            break
        out.append(line)
    return "".join(out)


def load_base_prompt() -> str:
    """Load the prompt template, stripping the TODO and Anhängen sections.

    Reads `examples/PROMPT-FOR-AI.md` at runtime so Matthias can keep editing
    the markdown. Falls back to a small backup template if the file is missing
    or unparseable.
    """
    if not _PROMPT_PATH.exists():
        return _BACKUP_TEMPLATE
    try:
        raw = _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return _BACKUP_TEMPLATE
    cleaned = _strip_section_to_separator(raw, "## TODO MATTHIAS")
    cleaned = _strip_section_to_end(cleaned, "## Anhängen am Ende")
    # Collapse runs of 3+ blank lines that the stripping may produce
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip() + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_prompt_template.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/prompt_builder/__init__.py src/school_test_engine/prompt_builder/template.py tests/test_prompt_template.py
git commit -m "feat(phase8): prompt_builder.template strips TODO + Anhängen sections"
```

---

## Task 5: prompt_builder/assembler.py — compose final prompt

**Files:**
- Create: `src/school_test_engine/prompt_builder/assembler.py`
- Test: `tests/test_prompt_assembler.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_prompt_assembler.py`:

```python
import pytest

from school_test_engine.prompt_builder.assembler import assemble_prompt


def test_assemble_appends_form_fields():
    out = assemble_prompt(
        subject="Mathe",
        topics=["Lineare Gleichungen", "Quadratische Gleichungen"],
        count=10,
        distribution="auto",
        style_briefing=None,
    )
    assert "Fach: Mathe" in out
    assert "Thema: Lineare Gleichungen, Quadratische Gleichungen" in out
    assert "Anzahl Fragen: 10" in out


def test_assemble_auto_distribution_label():
    out = assemble_prompt(
        subject="Bio", topics=["Zellen"], count=5,
        distribution="auto", style_briefing=None,
    )
    assert "Verteilung: automatisch (ca. 40/40/20)" in out


def test_assemble_manual_distribution_label():
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=10,
        distribution="manuell:3-5-2", style_briefing=None,
    )
    assert "Verteilung: 3 leicht, 5 mittel, 2 schwer" in out


def test_assemble_includes_style_briefing():
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5, distribution="auto",
        style_briefing="Schreibstil: Du-Form, freundlich.",
    )
    assert "## Eigener Stil" in out
    assert "Schreibstil: Du-Form, freundlich." in out


def test_assemble_omits_style_section_when_none():
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5, distribution="auto",
        style_briefing=None,
    )
    assert "## Eigener Stil" not in out


def test_assemble_omits_style_section_when_empty():
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=5, distribution="auto",
        style_briefing="   ",
    )
    assert "## Eigener Stil" not in out


def test_assemble_empty_topics_shows_placeholder():
    out = assemble_prompt(
        subject="Mathe", topics=[], count=5, distribution="auto",
        style_briefing=None,
    )
    assert "Thema: <bitte ergänzen>" in out


def test_assemble_inconsistent_manual_distribution_shows_marker():
    # caller is responsible for upfront validation, but the assembler
    # should still produce a string with a visible marker.
    out = assemble_prompt(
        subject="Mathe", topics=["X"], count=10,
        distribution="manuell:inkonsistent", style_briefing=None,
    )
    assert "Verteilung: <inkonsistent>" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_prompt_assembler.py -v`
Expected: All FAIL with import error.

- [ ] **Step 3: Write the assembler module**

Create `src/school_test_engine/prompt_builder/assembler.py`:

```python
from __future__ import annotations

from . import template


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
) -> str:
    """Compose the final prompt text from form inputs + optional style briefing.

    Args:
        subject: "Mathe" | "Englisch" | … (free text allowed)
        topics: List of topic strings (joined with ", " in output)
        count: Number of questions requested
        distribution: "auto" or "manuell:L-M-S" (e.g. "manuell:3-5-2")
        style_briefing: User's personal hint to the AI, or None to omit section.
    """
    base = template.load_base_prompt()

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_prompt_assembler.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/prompt_builder/assembler.py tests/test_prompt_assembler.py
git commit -m "feat(phase8): prompt_builder.assemble_prompt composes form fields + style"
```

---

## Task 6: Profile-Manager — add ai_style_briefing field

**Files:**
- Modify: `src/school_test_engine/ui/pages/profile_manager.py`

- [ ] **Step 1: Extend the `ProfileValues` dataclass and `_ProfileEditDialog`**

Edit `src/school_test_engine/ui/pages/profile_manager.py`:

**1a.** Add `QPlainTextEdit` to the existing PySide6 import block:

```python
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
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

**1b.** Extend the `ProfileValues` dataclass (around line ~42):

```python
@dataclass
class ProfileValues:
    name: str
    avatar: str
    avatar_image: bytes | None
    birthday: str | None
    ai_style_briefing: str | None
```

**1c.** Add the `initial_style_briefing` parameter to `_ProfileEditDialog.__init__`:

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
    ):
```

**1d.** Inside `_ProfileEditDialog.__init__`, after the existing birthday-row setup and before the OK/Cancel buttons, add a Style-Briefing section. Find the right place by locating the existing birthday widgets, then add this block just below:

```python
        # Style-Briefing for the AI prompt generator
        style_label = QLabel("KI-Stil-Hinweis (optional)")
        style_label.setStyleSheet("color: #4a4538; font-weight: 500; padding-top: 8px;")
        outer.addWidget(style_label)

        self.style_edit = QPlainTextEdit()
        self.style_edit.setPlaceholderText(
            "z. B.: Schreibstil: Du-Form, freundlich.\n"
            "Mathe: saubere Äquivalenzumformungen in der Erklärung."
        )
        self.style_edit.setMaximumHeight(110)
        if initial_style_briefing:
            self.style_edit.setPlainText(initial_style_briefing)
        outer.addWidget(self.style_edit)
```

*Note: `outer` is the name of the dialog's outer QVBoxLayout. If the variable is named differently in this file, use the existing layout name.*

**1e.** Extend the `values()` method to include the briefing:

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
        )
```

**1f.** In `ProfileManagerPage._edit`, pass the existing briefing and persist the new value:

Find the line `dlg = _ProfileEditDialog(` (around line 380) and update it:

```python
        dlg = _ProfileEditDialog(
            self,
            initial_name=u["name"],
            initial_avatar=u["avatar"],
            initial_image=row_get(u, "avatar_image"),
            initial_birthday=row_get(u, "birthday"),
            initial_style_briefing=row_get(u, "ai_style_briefing"),
        )
```

And in the same method, update the `update_user` call to pass the briefing:

```python
        users_repo.update_user(
            self.conn, user_id,
            name=v.name, avatar=v.avatar,
            avatar_image=v.avatar_image, birthday=v.birthday,
            ai_style_briefing=v.ai_style_briefing,
        )
```

**1g.** In `ProfileManagerPage._create`, update the `create_user` call only if needed (since `create_user` does not currently support ai_style_briefing, we leave create-flow alone — user can edit briefing after creating the profile):

Leave `_create` unchanged. The briefing is set via Edit only.

- [ ] **Step 2: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.ui.pages.profile_manager import _ProfileEditDialog, ProfileValues
dlg = _ProfileEditDialog(initial_name='X', initial_style_briefing='Test-Stil')
v = dlg.values()
print('ok', v.ai_style_briefing)"
```

Expected: prints `ok Test-Stil`.

- [ ] **Step 3: Full test suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: All tests still pass.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/pages/profile_manager.py
git commit -m "feat(phase8): Profile-Manager edit dialog supports ai_style_briefing"
```

---

## Task 7: ExamCard — add "Test bauen" button

**Files:**
- Modify: `src/school_test_engine/ui/widgets/exam_card.py`

- [ ] **Step 1: Modify the bottom-actions block**

Open `src/school_test_engine/ui/widgets/exam_card.py`. Find the bottom-row actions block (the section starting `# Bottom row: actions`). Replace the current `if event_data.linked_assessment_id is None:` branch:

```python
        # Bottom row: actions
        actions = QHBoxLayout()
        actions.setSpacing(8)
        if event_data.linked_assessment_id is None:
            practice_btn = QPushButton("✨ Test bauen")
            practice_btn.setObjectName("primary")
            practice_btn.clicked.connect(lambda: self.practice_clicked.emit(self.event_id))
            actions.addWidget(practice_btn)

            grade_btn = QPushButton("Note eintragen")
            grade_btn.setObjectName("text")
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

The change: when there is no linked assessment, both **"✨ Test bauen"** (primary, emits `practice_clicked`) and **"Note eintragen"** (text-style, emits `enter_grade_clicked`) are shown side-by-side. The Note-button was previously primary; now it's secondary.

- [ ] **Step 2: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.cockpit.service import EventCardData
from school_test_engine.ui.widgets.exam_card import ExamCard
d = EventCardData(1, 'Mathe', 'klassenarbeit', '2026-05-20', 3, ['Funktionen'], None, None)
c = ExamCard(d)
print('signals:', c.practice_clicked is not None, c.enter_grade_clicked is not None)
print('ok')"
```

Expected: prints `signals: True True` then `ok`.

- [ ] **Step 3: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: All tests still pass.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/widgets/exam_card.py
git commit -m "feat(phase8): ExamCard shows Test-bauen + Note-eintragen side-by-side"
```

---

## Task 8: PromptBuilderPage — UI scaffolding + live build

**Files:**
- Create: `src/school_test_engine/ui/pages/prompt_builder.py`

- [ ] **Step 1: Write the page**

Create `src/school_test_engine/ui/pages/prompt_builder.py`:

```python
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...prompt_builder.assembler import assemble_prompt
from ...storage import prompt_drafts_repo, users_repo
from .._layouts import row_get
from .._subjects import SUBJECTS_ALL
from ..design import Color, FontFamily, Semantic


class PromptBuilderPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._current_subject = SUBJECTS_ALL[0]
        self._loading = False  # suppress autosave while we populate fields

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(14)

        # Header
        head = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(self.window.show_menu)
        head.addWidget(back)
        head.addStretch(1)

        self.copy_btn = QPushButton("📋 Kopieren")
        self.copy_btn.setObjectName("primary")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        head.addWidget(self.copy_btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {Semantic.ACCENT}; font-size: 10pt;")
        head.addWidget(self._status_lbl)
        outer.addLayout(head)

        eyebrow = QLabel("TEST BAUEN")
        eyebrow.setObjectName("eyebrow")
        outer.addWidget(eyebrow)

        title = QLabel("Übungstest erzeugen")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        # --- Form ---
        form_row1 = QHBoxLayout()
        form_row1.setSpacing(12)
        form_row1.addWidget(QLabel("Fach:"))
        self.subject_combo = QComboBox()
        self.subject_combo.addItems(SUBJECTS_ALL)
        self.subject_combo.setEditable(True)
        self.subject_combo.currentTextChanged.connect(self._on_subject_changed)
        form_row1.addWidget(self.subject_combo)
        form_row1.addSpacing(20)
        form_row1.addWidget(QLabel("Anzahl:"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 50)
        self.count_spin.setValue(10)
        self.count_spin.valueChanged.connect(self._on_changed)
        form_row1.addWidget(self.count_spin)
        form_row1.addStretch(1)
        outer.addLayout(form_row1)

        outer.addWidget(QLabel("Themen (eine Zeile = ein Topic):"))
        self.topics_edit = QPlainTextEdit()
        self.topics_edit.setPlaceholderText("Lineare Gleichungen\nQuadratische Gleichungen")
        self.topics_edit.setMaximumHeight(110)
        self.topics_edit.textChanged.connect(self._on_changed)
        outer.addWidget(self.topics_edit)

        # Distribution row
        dist_row = QHBoxLayout()
        dist_row.setSpacing(10)
        dist_row.addWidget(QLabel("Schwierigkeit:"))
        self.dist_group = QButtonGroup(self)
        self.dist_auto = QRadioButton("auto (40/40/20)")
        self.dist_auto.setChecked(True)
        self.dist_auto.toggled.connect(self._on_dist_mode_changed)
        self.dist_group.addButton(self.dist_auto)
        dist_row.addWidget(self.dist_auto)

        self.dist_manual = QRadioButton("manuell:")
        self.dist_manual.toggled.connect(self._on_dist_mode_changed)
        self.dist_group.addButton(self.dist_manual)
        dist_row.addWidget(self.dist_manual)

        self.leicht_spin = QSpinBox()
        self.leicht_spin.setRange(0, 50); self.leicht_spin.setValue(4)
        self.leicht_spin.valueChanged.connect(self._on_changed)
        dist_row.addWidget(QLabel("L:")); dist_row.addWidget(self.leicht_spin)

        self.mittel_spin = QSpinBox()
        self.mittel_spin.setRange(0, 50); self.mittel_spin.setValue(4)
        self.mittel_spin.valueChanged.connect(self._on_changed)
        dist_row.addWidget(QLabel("M:")); dist_row.addWidget(self.mittel_spin)

        self.schwer_spin = QSpinBox()
        self.schwer_spin.setRange(0, 50); self.schwer_spin.setValue(2)
        self.schwer_spin.valueChanged.connect(self._on_changed)
        dist_row.addWidget(QLabel("S:")); dist_row.addWidget(self.schwer_spin)

        dist_row.addStretch(1)
        outer.addLayout(dist_row)

        self.dist_warn = QLabel("")
        self.dist_warn.setStyleSheet("color: #7e3b39; font-size: 10pt;")
        outer.addWidget(self.dist_warn)

        # Style-Briefing preview row
        style_row = QHBoxLayout()
        self.style_label = QLabel("Stil-Briefing (aus Profil): —")
        self.style_label.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
        self.style_label.setWordWrap(True)
        style_row.addWidget(self.style_label, 1)
        edit_link = QPushButton("Profil bearbeiten")
        edit_link.setObjectName("text")
        edit_link.clicked.connect(lambda: self.window.show_profile_manager("menu"))
        style_row.addWidget(edit_link)
        outer.addLayout(style_row)

        # --- Output ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #d8cdb8;")
        outer.addWidget(sep)

        outer.addWidget(QLabel("🪄 Generierter Prompt:"))
        self.output_view = QPlainTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setObjectName("promptOutput")
        outer.addWidget(self.output_view, 1)

        self._set_manual_enabled(False)
        self._update_status_clear_timer = QTimer(self)
        self._update_status_clear_timer.setSingleShot(True)
        self._update_status_clear_timer.timeout.connect(lambda: self._status_lbl.setText(""))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reload(self) -> None:
        self.show_for(subject=None, topics=None)

    def show_for(self, subject: str | None = None, topics: list[str] | None = None) -> None:
        uid = self.window.active_user_id
        if uid is None:
            return
        self._loading = True
        try:
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

            # Decide subject
            target_subject = subject or self._current_subject
            idx = self.subject_combo.findText(target_subject)
            if idx >= 0:
                self.subject_combo.setCurrentIndex(idx)
            else:
                self.subject_combo.setEditText(target_subject)
            self._current_subject = target_subject

            # Load draft for the subject
            draft = prompt_drafts_repo.get(self.conn, uid, target_subject)

            # Topics: explicit override wins, then draft, else empty
            if topics is not None:
                self.topics_edit.setPlainText("\n".join(topics))
            elif draft and draft["last_topic"]:
                self.topics_edit.setPlainText(draft["last_topic"])
            else:
                self.topics_edit.setPlainText("")

            # Count
            self.count_spin.setValue(draft["last_count"] if draft else 10)

            # Distribution
            dist = draft["last_dist"] if draft else "auto"
            if dist == "auto":
                self.dist_auto.setChecked(True)
                self._set_manual_enabled(False)
            else:
                # manuell:L-M-S
                payload = dist.split(":", 1)[1] if ":" in dist else ""
                parts = payload.split("-")
                if len(parts) == 3:
                    try:
                        l, m, s = (int(p) for p in parts)
                        self.leicht_spin.setValue(l)
                        self.mittel_spin.setValue(m)
                        self.schwer_spin.setValue(s)
                    except ValueError:
                        pass
                self.dist_manual.setChecked(True)
                self._set_manual_enabled(True)
        finally:
            self._loading = False
        self._rebuild_prompt()

    def hideEvent(self, event) -> None:
        self._autosave()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _current_dist_string(self) -> str:
        if self.dist_auto.isChecked():
            return "auto"
        return f"manuell:{self.leicht_spin.value()}-{self.mittel_spin.value()}-{self.schwer_spin.value()}"

    def _current_topics(self) -> list[str]:
        return [t.strip() for t in self.topics_edit.toPlainText().splitlines() if t.strip()]

    def _set_manual_enabled(self, enabled: bool) -> None:
        for w in (self.leicht_spin, self.mittel_spin, self.schwer_spin):
            w.setEnabled(enabled)

    def _validate_distribution(self) -> bool:
        """Return True if current distribution is consistent with count."""
        if self.dist_auto.isChecked():
            self.dist_warn.setText("")
            return True
        total = self.leicht_spin.value() + self.mittel_spin.value() + self.schwer_spin.value()
        if total != self.count_spin.value():
            self.dist_warn.setText(
                f"Summe {total} ≠ Anzahl {self.count_spin.value()} — passe an"
            )
            return False
        self.dist_warn.setText("")
        return True

    # ------------------------------------------------------------------
    # Live build
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _on_subject_changed(self, text: str) -> None:
        if self._loading:
            return
        # Save current draft before switching
        self._autosave()
        # Reload with new subject
        self._current_subject = text.strip() or SUBJECTS_ALL[0]
        self.show_for(subject=self._current_subject)

    def _on_dist_mode_changed(self, _checked: bool) -> None:
        if self._loading:
            return
        self._set_manual_enabled(self.dist_manual.isChecked())
        self._rebuild_prompt()

    def _on_changed(self, *_args) -> None:
        if self._loading:
            return
        self._rebuild_prompt()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _autosave(self) -> None:
        uid = self.window.active_user_id
        if uid is None:
            return
        subject = self.subject_combo.currentText().strip()
        if not subject:
            return
        topics_text = "\n".join(self._current_topics())
        prompt_drafts_repo.upsert(
            self.conn, uid, subject,
            last_topic=topics_text or None,
            last_count=self.count_spin.value(),
            last_dist=self._current_dist_string(),
        )

    def _copy_to_clipboard(self) -> None:
        self._autosave()
        QApplication.clipboard().setText(self.output_view.toPlainText())
        self._status_lbl.setText("Kopiert ✓")
        self._update_status_clear_timer.start(2000)
```

- [ ] **Step 2: Smoke test the page**

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
    def show_menu(self): pass
    def show_profile_manager(self, where): pass
from school_test_engine.ui.pages.prompt_builder import PromptBuilderPage
p = PromptBuilderPage(FakeWindow(), c)
p.reload()
print('output starts with:', p.output_view.toPlainText()[:30])"
```

Expected: prints the first chars of the assembled prompt (e.g., `output starts with: # Test-Fragen mit KI generieren`).

- [ ] **Step 3: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 122/122 still passing.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/pages/prompt_builder.py
git commit -m "feat(phase8): PromptBuilderPage with live build, auto-fill, clipboard"
```

---

## Task 9: MainWindow wiring + show_prompt_builder

**Files:**
- Modify: `src/school_test_engine/ui/main_window.py`

- [ ] **Step 1: Add import + page instance + navigation method**

In `src/school_test_engine/ui/main_window.py`:

**1a.** Add to imports:
```python
from .pages.prompt_builder import PromptBuilderPage
```

**1b.** After `self.grades_page = GradesPage(self, conn)`, add:
```python
        self.prompt_builder_page = PromptBuilderPage(self, conn)
```

**1c.** Add `self.prompt_builder_page` to the stack-registration tuple (alongside events_page and grades_page).

**1d.** Add a new navigation method after `show_grades`:
```python
    def show_prompt_builder(self, subject: str | None = None, topics: list[str] | None = None) -> None:
        self.prompt_builder_page.show_for(subject, topics)
        self.stack.setCurrentWidget(self.prompt_builder_page)
```

- [ ] **Step 2: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations
c = connect(':memory:')
run_migrations(c)
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
print('stack count:', w.stack.count())
print('has show_prompt_builder:', hasattr(w, 'show_prompt_builder'))"
```

Expected: `stack count: 13` (was 12 after Phase 7); `has show_prompt_builder: True`.

- [ ] **Step 3: Full test suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 122/122 passing.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/main_window.py
git commit -m "feat(phase8): wire PromptBuilderPage into MainWindow + show_prompt_builder"
```

---

## Task 10: MenuPage — Top-Bar button + wire practice_clicked

**Files:**
- Modify: `src/school_test_engine/ui/pages/menu.py`

- [ ] **Step 1: Add Test-bauen top-bar button**

In `src/school_test_engine/ui/pages/menu.py`, find the top-bar setup (where `events_btn` and `grades_btn` are added). Add a new button **between** the wordmark/stretch and the existing Termine button (so the order from left becomes: Logomark · Wordmark · stretch · **📝 Test bauen** · 📅 Termine · 📊 Noten · Profil-Chip):

```python
        # Top-bar new buttons (in this order, left to right)
        builder_btn = QPushButton("📝 Test bauen")
        builder_btn.setObjectName("topBarAction")
        builder_btn.clicked.connect(lambda: self.window.show_prompt_builder())
        top_row.addWidget(builder_btn)

        events_btn = QPushButton("📅 Termine")
        events_btn.setObjectName("topBarAction")
        events_btn.clicked.connect(self.window.show_events)
        top_row.addWidget(events_btn)

        grades_btn = QPushButton("📊 Noten")
        grades_btn.setObjectName("topBarAction")
        grades_btn.clicked.connect(self.window.show_grades)
        top_row.addWidget(grades_btn)
```

- [ ] **Step 2: Wire practice_clicked in _build_ka_hero**

Still in `menu.py`, find `_build_ka_hero` (which creates ExamCards) and modify the per-card connection block. Currently it connects `enter_grade_clicked` and `edit_clicked`; add a `practice_clicked` connection:

```python
        for ev in events:
            card = ExamCard(ev)
            card.practice_clicked.connect(self._on_practice_clicked)
            card.enter_grade_clicked.connect(self._on_enter_grade)
            card.edit_clicked.connect(self._on_edit_event)
            strip.addWidget(card)
```

- [ ] **Step 3: Add `_on_practice_clicked` handler**

In the same file, somewhere with the other `_on_*` handlers, add:

```python
    def _on_practice_clicked(self, event_id: int) -> None:
        import json
        ev = events_repo.get(self.window.conn, event_id)
        if ev is None:
            return
        topics = json.loads(ev["topics"] or "[]")
        self.window.show_prompt_builder(subject=ev["subject"], topics=topics)
```

Make sure `events_repo` is already imported in this file (Phase 7 wired it).

- [ ] **Step 4: Smoke test (empty + hero states + navigation routing)**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo, events_repo
c = connect(':memory:')
run_migrations(c)
uid = users_repo.create_user(c, 'Clemens', '🧒')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.active_user_id = uid
w.menu_page.reload()
print('ok empty')
eid = events_repo.create(c, uid, 'Mathe', 'klassenarbeit', '2026-05-20', topics=['Funktionen'])
w.menu_page.reload()
# Trigger practice_clicked manually
w.menu_page._on_practice_clicked(eid)
print('show_prompt_builder routed:', w.stack.currentWidget() is w.prompt_builder_page)
print('subject in combo:', w.prompt_builder_page.subject_combo.currentText())
print('topics in editor:', repr(w.prompt_builder_page.topics_edit.toPlainText()))"
```

Expected:
```
ok empty
show_prompt_builder routed: True
subject in combo: Mathe
topics in editor: 'Funktionen'
```

- [ ] **Step 5: Full test suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 122/122.

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/pages/menu.py
git commit -m "feat(phase8): Top-Bar Test-bauen button + wire ExamCard.practice_clicked"
```

---

## Task 11: QSS — Phase 8 styles

**Files:**
- Modify: `src/school_test_engine/ui/style.qss`

- [ ] **Step 1: Append new style rules**

Append to `src/school_test_engine/ui/style.qss`:

```css

/* ----- Phase 8: Test bauen ----- */

/* Read-only prompt output area */
QPlainTextEdit#promptOutput {
    background: #fbf6ec;
    color: #1e1b15;
    border: 1px solid #ead9be;
    border-radius: 10px;
    padding: 12px;
    font-family: "IBM Plex Mono", monospace;
    font-size: 10pt;
}
```

- [ ] **Step 2: Smoke test that QSS still loads cleanly**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
users_repo.create_user(c, 'Clemens', '🧒')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/style.qss
git commit -m "feat(phase8): QSS for promptOutput textarea"
```

---

## Task 12: User-isolation regression test for prompt_drafts

**Files:**
- Modify: `tests/test_cockpit_isolation.py` (extend existing) OR create new `tests/test_prompt_drafts_isolation.py`

- [ ] **Step 1: Write isolation test**

Create `tests/test_prompt_drafts_isolation.py`:

```python
import pytest

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import prompt_drafts_repo


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_two_users_have_independent_drafts(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    prompt_drafts_repo.upsert(conn, a, "Mathe", last_topic="A-T", last_count=5, last_dist="auto")
    prompt_drafts_repo.upsert(conn, b, "Mathe", last_topic="B-T", last_count=8, last_dist="auto")
    assert prompt_drafts_repo.get(conn, a, "Mathe")["last_topic"] == "A-T"
    assert prompt_drafts_repo.get(conn, b, "Mathe")["last_topic"] == "B-T"


def test_delete_user_cascade_removes_drafts(conn):
    uid = users_repo.create_user(conn, "Wegmacher")
    prompt_drafts_repo.upsert(conn, uid, "Mathe", last_topic="X", last_count=10, last_dist="auto")
    users_repo.delete_user(conn, uid)
    assert conn.execute(
        "SELECT COUNT(*) FROM prompt_drafts WHERE user_id = ?", (uid,)
    ).fetchone()[0] == 0
```

- [ ] **Step 2: Run isolation tests**

Run: `pytest tests/test_prompt_drafts_isolation.py -v`
Expected: 2 PASS.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: all tests pass (~150 total after Phase 8).

- [ ] **Step 4: Commit**

```bash
git add tests/test_prompt_drafts_isolation.py
git commit -m "test(phase8): user isolation + cascade for prompt_drafts"
```

---

## Task 13: End-to-end smoke (programmatic)

**Files:** none

- [ ] **Step 1: Run a programmatic end-to-end script**

Run:
```bash
QT_QPA_PLATFORM=offscreen python <<'EOF'
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo, events_repo, prompt_drafts_repo
from school_test_engine.prompt_builder.assembler import assemble_prompt

# Setup
c = connect(':memory:')
run_migrations(c)
uid = users_repo.create_user(c, 'Clemens', '🧒')

# 1. Style briefing
users_repo.update_user(c, uid, ai_style_briefing="Schreibstil: Du-Form.")
user = users_repo.get_user(c, uid)
assert user["ai_style_briefing"] == "Schreibstil: Du-Form."

# 2. Direct assembler test
out = assemble_prompt(
    subject="Mathe", topics=["Lineare Gleichungen"], count=10,
    distribution="auto", style_briefing=user["ai_style_briefing"],
)
assert "Fach: Mathe" in out
assert "## Eigener Stil" in out
assert "Du-Form" in out

# 3. KA + ExamCard practice_clicked routing
eid = events_repo.create(c, uid, "Mathe", "klassenarbeit", "2026-06-01", topics=["Funktionen", "Gleichungen"])

# Construct MainWindow + simulate flow
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.active_user_id = uid
w.menu_page.reload()
w.menu_page._on_practice_clicked(eid)
assert w.stack.currentWidget() is w.prompt_builder_page
assert w.prompt_builder_page.subject_combo.currentText() == "Mathe"
assert "Funktionen" in w.prompt_builder_page.topics_edit.toPlainText()

# 4. Live-build produces correct output
generated = w.prompt_builder_page.output_view.toPlainText()
assert "Fach: Mathe" in generated
assert "Thema: Funktionen, Gleichungen" in generated
assert "## Eigener Stil" in generated

# 5. Autosave on hideEvent — verify by triggering autosave directly
w.prompt_builder_page._autosave()
draft = prompt_drafts_repo.get(c, uid, "Mathe")
assert draft is not None
assert "Funktionen" in (draft["last_topic"] or "")

# 6. Reload PromptBuilderPage with no args → loads draft
w.prompt_builder_page.show_for()
assert "Funktionen" in w.prompt_builder_page.topics_edit.toPlainText()

# 7. Cascade on user delete
users_repo.delete_user(c, uid)
assert c.execute("SELECT COUNT(*) FROM prompt_drafts WHERE user_id = ?", (uid,)).fetchone()[0] == 0

print("ALL 7 END-TO-END CHECKS PASSED")
EOF
```

Expected: prints `ALL 7 END-TO-END CHECKS PASSED`.

- [ ] **Step 2: Final acceptance audit**

For each of the 10 acceptance criteria in the spec, confirm:
1. ✅ Migration 007 lief — Test in Task 1 + smoke script PASS
2. ✅ Top-Bar 📝 Test bauen — Task 10 smoke (routed to prompt_builder_page)
3. ✅ ExamCard zeigt beide Buttons — Task 7 smoke (signals exist)
4. ✅ ✨ Click öffnet Builder mit Fach+Topics — Smoke Step 3 above
5. ✅ Live-Build — Smoke Step 4 above (Fach+Topics+Stil im Output)
6. ⚠️ Copy-Button — programmatically untestable on headless Linux (no system clipboard) — confirm via Step 3 manual smoke when display available
7. ✅ Profile-Manager Stil-Feld — Task 6 + smoke Step 1
8. ✅ Auto-Fill nach Reload — Smoke Step 6
9. ✅ Cascade — Smoke Step 7 + Task 12
10. ⏳ Manueller End-to-End (Mathe → Claude → JSON → Import → Library) — requires user with display + browser

Document any caveats in your report.

- [ ] **Step 3: No commit needed for Task 13** (acceptance audit only). If any small fixes were made during the audit, commit them with an appropriate message.

---

## Self-Review

**Spec coverage:**
- §2 Migration 007 (users column + prompt_drafts table) → Task 1 ✓
- §3.1 `prompt_builder/` package (template.py, assembler.py) → Tasks 4, 5 ✓
- §3.2 prompt_drafts_repo → Task 3 ✓
- §3.3 users_repo.update_user with ai_style_briefing → Task 2 ✓
- §3.4 PromptBuilderPage → Task 8 ✓
- §3.5 ExamCard with practice_clicked active → Task 7 ✓
- §3.6 Profile-Manager Stil-Briefing-Feld → Task 6 ✓
- §3.7 MainWindow + Menu wiring → Tasks 9, 10 ✓
- §4 Verteilungs-Logik (auto/manuell mit Live-Validierung + Copy-disabled-bei-inkonsistent) → Task 8 (`_validate_distribution`) ✓
- §5 Template-Stripping mit Fallback → Task 4 ✓
- §6 Tests → Tasks 1-5, 12 (unit), Task 13 (end-to-end smoke)
- §7 Edge cases → covered across Tasks 4, 5, 8, 12
- §8 10 Akzeptanzkriterien → audit in Task 13
- §10 Risk Mitigation: Markdown-Drift handled in Task 4 via tests + fallback ✓

**Placeholder scan:** No TBDs. Every step has complete code or a runnable command.

**Type consistency:**
- `assemble_prompt(subject, topics, count, distribution, style_briefing)` — signature consistent in Tasks 5 + 8 ✓
- `prompt_drafts_repo.upsert/get/list_for_user` — same calls in Tasks 3, 8, 12, 13 ✓
- `users_repo.update_user(..., ai_style_briefing=...)` — same in Tasks 2, 6, 13 ✓
- `show_prompt_builder(subject=None, topics=None)` — same in Tasks 9, 10, 13 ✓
- `PromptBuilderPage.show_for(subject, topics)` — same in Tasks 8, 9 ✓
- ExamCard signal `practice_clicked` (Signal(int)) — declared in Phase 7, wired in Tasks 7+10 ✓

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-13-phase-8-test-bauen.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

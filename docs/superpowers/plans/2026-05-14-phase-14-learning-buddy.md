# Phase 14 — Learning Buddy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship „Learning Buddy v1.0" — rebrand the app, add keyboard navigation to the runner, add real charts on the Noten/History pages, and add PDF export for tests, study plans, and grade reports.

**Architecture:** Four independent tracks (A Rebranding, B Keyboard, C Charts, D PDF). One DB migration (`010_phase14_keyboard_hints.sql`) adds a boolean per-user flag. All UI changes follow Phase 13 conventions (text-only chrome, `primary|text|danger` objectNames). Custom `QPainter` widgets for charts (no external lib). PDF via `QPrinter` + `QTextDocument` (same pattern as Phase 5).

**Tech Stack:** PySide6 (Qt6), Python 3.12, SQLite, pytest with `QT_QPA_PLATFORM=offscreen`, QPainter, QPrinter.

**Spec:** `docs/superpowers/specs/2026-05-14-phase-14-learning-buddy.md`

---

## File Structure

### Created
- `src/school_test_engine/storage/migrations/010_phase14_keyboard_hints.sql`
- `src/school_test_engine/ui/keyboard_shortcuts.py`
- `src/school_test_engine/ui/widgets/grade_chart.py`
- `src/school_test_engine/ui/widgets/grade_heatmap.py`
- `src/school_test_engine/pdf_export/__init__.py`
- `src/school_test_engine/pdf_export/_common.py`
- `src/school_test_engine/pdf_export/test_sheet.py`
- `src/school_test_engine/pdf_export/study_plan.py`
- `src/school_test_engine/pdf_export/grade_report.py`
- `tests/test_migration_010.py`
- `tests/test_keyboard_shortcuts.py`
- `tests/test_grade_chart.py`
- `tests/test_grade_heatmap.py`
- `tests/test_assessments_heatmap_query.py`
- `tests/test_pdf_test_sheet.py`
- `tests/test_pdf_study_plan.py`
- `tests/test_pdf_grade_report.py`
- `tests/test_branding.py`

### Modified
- `src/school_test_engine/app.py` — rebrand
- `src/school_test_engine/main_window.py` — window title
- `src/school_test_engine/storage/users_repo.py` — `show_keyboard_hints` kwarg
- `src/school_test_engine/storage/assessments_repo.py` — `heatmap_data` helper
- `src/school_test_engine/ui/pages/menu.py` — wordmark + footer
- `src/school_test_engine/ui/pages/runner.py` — keyboard wiring + cheat-sheet
- `src/school_test_engine/ui/pages/review.py` — keyboard wiring
- `src/school_test_engine/ui/pages/grades.py` — embed GradeChart + PDF button
- `src/school_test_engine/ui/pages/history.py` — embed GradeHeatmap
- `src/school_test_engine/ui/pages/library.py` — PDF button per Test-Card
- `src/school_test_engine/ui/widgets/exam_card.py` — Lernplan-PDF button
- `src/school_test_engine/ui/pages/event_edit.py` — Lernplan-PDF button (edit mode)
- `install-desktop.sh` — updated echo line
- `school-test-engine.desktop` — Name/Comment

---

## Task Overview

1. Migration 010 + users_repo flag
2. Track A: app.py + main window title rebrand
3. Track A: menu.py wordmark + footer
4. Track A: install-desktop.sh + .desktop file
5. Track B: keyboard_shortcuts.py module
6. Track B: RunnerPage wire-up + cheat-sheet
7. Track B: ReviewPage wire-up
8. Track C: assessments_repo.heatmap_data
9. Track C: GradeChart widget
10. Track C: GradeHeatmap widget
11. Track C: Embed GradeChart on Noten-Page
12. Track C: Embed GradeHeatmap on History-Page
13. Track D: pdf_export base (_common.py)
14. Track D: test_sheet + Library PDF button
15. Track D: study_plan + ExamCard + EventEditPage buttons
16. Track D: grade_report + Noten-Page PDF button
17. Final acceptance check

---

### Task 1: Migration 010 + users_repo flag

**Files:**
- Create: `src/school_test_engine/storage/migrations/010_phase14_keyboard_hints.sql`
- Modify: `src/school_test_engine/storage/users_repo.py`
- Test: `tests/test_migration_010.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_migration_010.py`:

```python
"""Phase 14 Migration 010: adds users.show_keyboard_hints (BOOLEAN DEFAULT 1)."""
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "test.db")
    c.row_factory = sqlite3.Row
    run_migrations(c)
    yield c
    c.close()


def test_users_show_keyboard_hints_column_exists(conn):
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    assert "show_keyboard_hints" in cols


def test_new_user_has_keyboard_hints_default_on(conn):
    uid = users_repo.create_user(conn, "Test", "👤")
    row = users_repo.get_user(conn, uid)
    assert row["show_keyboard_hints"] == 1


def test_update_user_can_toggle_keyboard_hints(conn):
    uid = users_repo.create_user(conn, "Test", "👤")
    users_repo.update_user(conn, uid, show_keyboard_hints=0)
    row = users_repo.get_user(conn, uid)
    assert row["show_keyboard_hints"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_migration_010.py -v
```
Expected: 3 failures (column doesn't exist; `update_user` rejects unknown kwarg).

- [ ] **Step 3: Create migration SQL**

Create `src/school_test_engine/storage/migrations/010_phase14_keyboard_hints.sql`:

```sql
-- Phase 14: Keyboard-hint cheat-sheet toggle per user

ALTER TABLE users ADD COLUMN show_keyboard_hints INTEGER NOT NULL DEFAULT 1;
```

- [ ] **Step 4: Extend users_repo**

In `src/school_test_engine/storage/users_repo.py`, find:

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

Replace with (adds `show_keyboard_hints` as last kwarg, keeping the existing pattern):

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
) -> None:
```

In the body, add after the `sort_order` block:

```python
    if show_keyboard_hints is not None:
        fields.append("show_keyboard_hints = ?"); values.append(int(show_keyboard_hints))
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_migration_010.py -v
```
Expected: 3 passes.

- [ ] **Step 6: Run full suite (regression check)**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q
```
Expected: all green (256 + 3 = 259 minimum).

- [ ] **Step 7: Commit**

```bash
git add src/school_test_engine/storage/migrations/010_phase14_keyboard_hints.sql \
        src/school_test_engine/storage/users_repo.py \
        tests/test_migration_010.py
git commit -m "feat(phase14): migration 010 + users.show_keyboard_hints flag"
```

---

### Task 2: App-level rebranding (app.py + window title)

**Files:**
- Modify: `src/school_test_engine/app.py`
- Modify: `src/school_test_engine/ui/main_window.py`
- Test: `tests/test_branding.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_branding.py`:

```python
"""Phase 14 Track A: App is rebranded to 'Learning Buddy'."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.storage import run_migrations


@pytest.fixture(scope="module")
def app():
    inst = QApplication.instance() or QApplication([])
    return inst


def test_application_name_is_learning_buddy(app):
    from school_test_engine import app as app_module
    # We don't call main() (it blocks), but we verify the strings are present in the source.
    src = (app_module.__file__)
    text = open(src, encoding="utf-8").read()
    assert 'setApplicationName("Learning Buddy")' in text
    assert 'setApplicationDisplayName("Learning Buddy")' in text


def test_main_window_title_is_learning_buddy(app, tmp_path):
    db = tmp_path / "lb.db"
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    run_migrations(c)
    from school_test_engine.ui.main_window import MainWindow
    win = MainWindow(c)
    assert win.windowTitle() == "Learning Buddy"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_branding.py -v
```
Expected: 2 failures.

- [ ] **Step 3: Update app.py**

In `src/school_test_engine/app.py`, find:

```python
    app.setApplicationName("School Test Engine")
    app.setApplicationDisplayName("Übungstests")
```

Replace with:

```python
    app.setApplicationName("Learning Buddy")
    app.setApplicationDisplayName("Learning Buddy")
    app.setOrganizationName("Matthias Kessler")
```

- [ ] **Step 4: Update MainWindow title**

In `src/school_test_engine/ui/main_window.py`, find:

```python
        self.setWindowTitle("Übungstests")
```

Replace with:

```python
        self.setWindowTitle("Learning Buddy")
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_branding.py -v
```
Expected: 2 passes.

- [ ] **Step 6: Run full suite**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/school_test_engine/app.py \
        src/school_test_engine/ui/main_window.py \
        tests/test_branding.py
git commit -m "feat(phase14): rebrand app to Learning Buddy"
```

---

### Task 3: Menu top-bar wordmark + footer

**Files:**
- Modify: `src/school_test_engine/ui/pages/menu.py`

- [ ] **Step 1: Locate the existing top-bar block**

Run:
```bash
grep -n "logomark\|Wordmark\|wordmark\|QSvgWidget\|Top-Bar" /home/matthias/Dokumente/Claude/ai-projects/school-test-engine/src/school_test_engine/ui/pages/menu.py | head -10
```

Identify where the logomark (Eichen SVG) is added to the top-bar layout. Right after that widget, the old wordmark was a separate `QSvgWidget` for a wordmark SVG or a `QLabel`. Read those 15 lines to understand the current state.

- [ ] **Step 2: Replace old wordmark with QLabel**

Locate where the wordmark widget is added next to the logomark in the top-bar layout. If it's a `QSvgWidget(str(WORDMARK_PATH))` or similar, replace it with:

```python
        wordmark = QLabel("Learning Buddy")
        wordmark.setFont(QFont(FontFamily.DISPLAY, 14, QFont.Weight.Normal))
        wordmark.setStyleSheet("color: #4a4538;")
        # add to the same layout slot where the old wordmark widget was added
```

If no wordmark widget was there before (only logomark), add this `QLabel` immediately after the logomark widget in the top-bar layout.

Ensure `QFont` and `FontFamily` are imported at the top of the file (they likely already are; if not, add the imports from `..design`).

- [ ] **Step 3: Add footer label at end of menu page**

In `menu.py`, find the end of the main vertical layout (the last `addWidget` or `addLayout` before the close of `__init__` / `_build_layout`). Insert just before the final `addStretch(1)` (or as the last item if no stretch):

```python
        footer = QLabel("designed by Matthias")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #a89e89; font-size: 9pt;")
        outer.addWidget(footer)  # or whichever variable is the page's outermost QVBoxLayout
```

(Adapt the layout variable name to match what's actually used in `menu.py` — likely `outer` or `main_layout`.)

- [ ] **Step 4: Run full suite (smoke)**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q
```
Expected: all green. (The branding test only checks app/window-level strings; the menu wordmark is a visual-only change.)

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/menu.py
git commit -m "feat(phase14): menu top-bar wordmark + footer tagline"
```

---

### Task 4: Update .desktop file + install script

**Files:**
- Modify: `school-test-engine.desktop`
- Modify: `install-desktop.sh`

- [ ] **Step 1: Update .desktop file**

Replace the entire content of `/home/matthias/Dokumente/Claude/ai-projects/school-test-engine/school-test-engine.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Learning Buddy
Comment=Klassenarbeits-Übungen für die Schule — designed by Matthias
GenericName=Lernen für die Schule
Exec=__PROJECT_DIR__/run.sh
Icon=__PROJECT_DIR__/assets/icon.svg
Terminal=false
Categories=Education;Math;Languages;
Keywords=Schule;Test;Übung;Mathe;Englisch;Learning;
StartupNotify=true
```

- [ ] **Step 2: Update install-desktop.sh echo lines**

In `install-desktop.sh`, find:

```bash
echo "  Du findest 'Übungstests' jetzt im Startmenü unter Bildung/Lernen."
```

Replace with:

```bash
echo "  Du findest 'Learning Buddy' jetzt im Startmenü unter Bildung/Lernen."
```

- [ ] **Step 3: Verify .desktop file is syntactically valid**

Run:
```bash
desktop-file-validate /home/matthias/Dokumente/Claude/ai-projects/school-test-engine/school-test-engine.desktop 2>&1 || true
```
Expected: no errors (or only deprecated-key warnings, which are harmless). If `desktop-file-validate` is not installed, skip this step.

- [ ] **Step 4: Commit**

```bash
git add school-test-engine.desktop install-desktop.sh
git commit -m "feat(phase14): .desktop file uses Learning Buddy name"
```

---

### Task 5: Keyboard-shortcuts module

**Files:**
- Create: `src/school_test_engine/ui/keyboard_shortcuts.py`
- Test: `tests/test_keyboard_shortcuts.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_keyboard_shortcuts.py`:

```python
"""Phase 14 Track B: keyboard shortcuts module."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_install_runner_shortcuts_registers_all_keys(app):
    from school_test_engine.ui.keyboard_shortcuts import install_runner_shortcuts
    page = QWidget()
    fired: dict[str, int] = {"prev": 0, "next": 0, "mark": 0, "overview": 0, "abort": 0}
    shortcuts = install_runner_shortcuts(
        page,
        on_prev=lambda: fired.__setitem__("prev", fired["prev"] + 1),
        on_next=lambda: fired.__setitem__("next", fired["next"] + 1),
        on_mark=lambda: fired.__setitem__("mark", fired["mark"] + 1),
        on_overview=lambda: fired.__setitem__("overview", fired["overview"] + 1),
        on_abort=lambda: fired.__setitem__("abort", fired["abort"] + 1),
    )
    # We expect 7 shortcuts: Left, Right, Return, Enter, M, O, Escape
    assert len(shortcuts) == 7
    # Verify each shortcut has a key sequence
    seqs = {s.key().toString() for s in shortcuts}
    assert "Left" in seqs
    assert "Right" in seqs
    assert "Return" in seqs or "Enter" in seqs
    assert "M" in seqs
    assert "O" in seqs
    assert "Esc" in seqs


def test_right_arrow_fires_on_next(app):
    from school_test_engine.ui.keyboard_shortcuts import install_runner_shortcuts
    page = QWidget()
    page.resize(200, 200)
    fired = {"next": 0}
    install_runner_shortcuts(
        page,
        on_prev=lambda: None,
        on_next=lambda: fired.__setitem__("next", fired["next"] + 1),
        on_mark=lambda: None,
        on_overview=lambda: None,
        on_abort=lambda: None,
    )
    page.show()
    QTest.qWaitForWindowExposed(page)
    QTest.keyClick(page, Qt.Key.Key_Right)
    QApplication.processEvents()
    assert fired["next"] == 1
    page.close()


def test_m_key_fires_on_mark(app):
    from school_test_engine.ui.keyboard_shortcuts import install_runner_shortcuts
    page = QWidget()
    page.resize(200, 200)
    fired = {"mark": 0}
    install_runner_shortcuts(
        page,
        on_prev=lambda: None,
        on_next=lambda: None,
        on_mark=lambda: fired.__setitem__("mark", fired["mark"] + 1),
        on_overview=lambda: None,
        on_abort=lambda: None,
    )
    page.show()
    QTest.qWaitForWindowExposed(page)
    QTest.keyClick(page, Qt.Key.Key_M)
    QApplication.processEvents()
    assert fired["mark"] == 1
    page.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_keyboard_shortcuts.py -v
```
Expected: 3 failures (ModuleNotFoundError).

- [ ] **Step 3: Create the module**

Create `src/school_test_engine/ui/keyboard_shortcuts.py`:

```python
"""Phase 14 Track B: centralized keyboard shortcut bindings for runner-like pages."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget


def install_runner_shortcuts(
    page: QWidget,
    *,
    on_prev: Callable[[], None],
    on_next: Callable[[], None],
    on_mark: Callable[[], None],
    on_overview: Callable[[], None],
    on_abort: Callable[[], None],
) -> list[QShortcut]:
    """Install Phase-14 keyboard shortcuts on a runner-like page.

    Bindings:
      ← / Left           → on_prev
      → / Right          → on_next
      Enter / Return     → on_next
      M                  → on_mark
      O                  → on_overview
      Esc                → on_abort

    Tab + Space for option selection is handled natively by Qt's QRadioButton /
    QCheckBox focus handling and is NOT registered here.

    Returns the list of created QShortcut instances. The caller should retain
    this list so the shortcuts live as long as the page.
    """
    shortcuts: list[QShortcut] = []

    def _add(key: Qt.Key | QKeySequence, callback: Callable[[], None]) -> None:
        sc = QShortcut(QKeySequence(key), page)
        sc.activated.connect(callback)
        shortcuts.append(sc)

    _add(Qt.Key.Key_Left, on_prev)
    _add(Qt.Key.Key_Right, on_next)
    _add(Qt.Key.Key_Return, on_next)
    _add(Qt.Key.Key_Enter, on_next)
    _add(Qt.Key.Key_M, on_mark)
    _add(Qt.Key.Key_O, on_overview)
    _add(Qt.Key.Key_Escape, on_abort)

    return shortcuts
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_keyboard_shortcuts.py -v
```
Expected: 3 passes.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/keyboard_shortcuts.py \
        tests/test_keyboard_shortcuts.py
git commit -m "feat(phase14): keyboard_shortcuts module"
```

---

### Task 6: Wire keyboard shortcuts into RunnerPage + cheat-sheet

**Files:**
- Modify: `src/school_test_engine/ui/pages/runner.py`

- [ ] **Step 1: Add imports + cheat-sheet QLabel + shortcut wiring in `__init__`**

In `src/school_test_engine/ui/pages/runner.py`, ensure these imports exist near the top:

```python
from ..keyboard_shortcuts import install_runner_shortcuts
```

In `RunnerPage.__init__`, after the action-buttons row is built (but before `addStretch(1)` or similar at the end), add the cheat-sheet:

```python
        # Phase 14: keyboard cheat-sheet (togglable per user via show_keyboard_hints)
        self.cheat_sheet = QLabel(
            "Tab Optionen · Space wählen · ←→ Fragen · M markieren · O Übersicht · Esc Menü"
        )
        self.cheat_sheet.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cheat_sheet.setStyleSheet("color: #a89e89; font-size: 9pt;")
        # Find the variable for the main layout (outer or main_layout) and append:
        outer.addWidget(self.cheat_sheet)
```

(If `outer` isn't the variable name, replace with the actual one — read the surrounding code first.)

At the end of `__init__`, after all widgets are created, install shortcuts:

```python
        # Phase 14: keyboard shortcuts (Tab/Space handled natively by Qt focus)
        self._shortcuts = install_runner_shortcuts(
            self,
            on_prev=self._on_prev,
            on_next=self._on_next,
            on_mark=self._on_mark,
            on_overview=self._on_overview,
            on_abort=self._on_abort,
        )
```

Adapt the callback names to the actual private methods on `RunnerPage` — likely already exist with names like `_go_prev`, `_go_next`, `_toggle_mark`, `_open_review`, `_abort_to_menu` or similar. Read the file to find them.

- [ ] **Step 2: Toggle cheat-sheet visibility based on user preference**

`RunnerPage` likely has a method that's called when a new attempt starts or when reload happens (e.g., `start_new`, `resume`, `reload`). Inside that method, read the current user's `show_keyboard_hints` flag and call:

```python
        row = users_repo.get_user(self.conn, self.window.active_user_id)
        if row is not None:
            self.cheat_sheet.setVisible(bool(row["show_keyboard_hints"]))
```

Add `from ...storage import users_repo` at the top if not already imported.

- [ ] **Step 3: Run full suite**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q
```
Expected: all green. Existing runner tests should still pass.

- [ ] **Step 4: Add an integration test**

Append to `tests/test_keyboard_shortcuts.py`:

```python
def test_runner_page_installs_shortcuts(app, tmp_path):
    """The RunnerPage actually installs the shortcuts when constructed."""
    import sqlite3
    from school_test_engine.storage import run_migrations, users_repo
    from school_test_engine.ui.pages.runner import RunnerPage

    db = tmp_path / "r.db"
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    run_migrations(c)

    class _StubWindow:
        def __init__(self, conn):
            self.conn = conn
            self.active_user_id = users_repo.create_user(conn, "Test", "👤")
        def show_results(self, *a, **kw): pass
        def show_menu(self, *a, **kw): pass

    win = _StubWindow(c)
    page = RunnerPage(win, c)
    assert hasattr(page, "_shortcuts")
    assert len(page._shortcuts) == 7
```

Run:
```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_keyboard_shortcuts.py::test_runner_page_installs_shortcuts -v
```
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/runner.py \
        tests/test_keyboard_shortcuts.py
git commit -m "feat(phase14): wire keyboard shortcuts + cheat-sheet into RunnerPage"
```

---

### Task 7: Wire shortcuts into ReviewPage

**Files:**
- Modify: `src/school_test_engine/ui/pages/review.py`

- [ ] **Step 1: Add minimal shortcuts to ReviewPage**

In `src/school_test_engine/ui/pages/review.py`, at the top:

```python
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
```

(May already be partially imported — add what's missing.)

In `ReviewPage.__init__`, at the end (after all widgets created), add:

```python
        # Phase 14: keyboard shortcuts on Review-Page
        self._review_shortcuts: list[QShortcut] = []
        for key, cb in [
            (Qt.Key.Key_Escape, self._go_back),       # adapt to actual method name (← Weiter üben)
            (Qt.Key.Key_Return, self._submit),         # adapt to actual method name (Abgeben)
            (Qt.Key.Key_Enter, self._submit),
        ]:
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(cb)
            self._review_shortcuts.append(sc)
```

(Adapt `_go_back` and `_submit` to the actual method names on `ReviewPage` — read the file first. Likely they're `_back_to_runner` and `_submit_attempt` or similar.)

- [ ] **Step 2: Run full suite**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q
```
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/pages/review.py
git commit -m "feat(phase14): keyboard shortcuts on ReviewPage"
```

---

### Task 8: assessments_repo.heatmap_data

**Files:**
- Modify: `src/school_test_engine/storage/assessments_repo.py`
- Test: `tests/test_assessments_heatmap_query.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_assessments_heatmap_query.py`:

```python
"""Phase 14 Track C: heatmap aggregation query."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from school_test_engine.storage import assessments_repo, run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "h.db")
    c.row_factory = sqlite3.Row
    run_migrations(c)
    yield c
    c.close()


def test_heatmap_data_empty(conn):
    uid = users_repo.create_user(conn, "Test", "👤")
    result = assessments_repo.heatmap_data(conn, uid, weeks_back=8)
    assert result == {}


def test_heatmap_data_single_assessment(conn):
    uid = users_repo.create_user(conn, "Test", "👤")
    today = date.today()
    iso = today.isoformat()
    assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", iso,
        grade=2.0, points=None, max_points=None, note=None,
        scheduled_event_id=None,
    )
    result = assessments_repo.heatmap_data(conn, uid, weeks_back=8)
    assert "Mathe" in result
    week_starts = list(result["Mathe"].keys())
    assert len(week_starts) == 1
    assert result["Mathe"][week_starts[0]] == 2.0


def test_heatmap_data_avg_within_week(conn):
    uid = users_repo.create_user(conn, "Test", "👤")
    monday = date.today() - timedelta(days=date.today().weekday())
    a1_iso = monday.isoformat()
    a2_iso = (monday + timedelta(days=2)).isoformat()
    assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", a1_iso,
        grade=2.0, points=None, max_points=None, note=None,
        scheduled_event_id=None,
    )
    assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", a2_iso,
        grade=4.0, points=None, max_points=None, note=None,
        scheduled_event_id=None,
    )
    result = assessments_repo.heatmap_data(conn, uid, weeks_back=8)
    # both assessments fall in the same week → avg = 3.0
    assert list(result["Mathe"].values())[0] == 3.0


def test_heatmap_data_excludes_old(conn):
    uid = users_repo.create_user(conn, "Test", "👤")
    long_ago = (date.today() - timedelta(weeks=20)).isoformat()
    assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", long_ago,
        grade=2.0, points=None, max_points=None, note=None,
        scheduled_event_id=None,
    )
    result = assessments_repo.heatmap_data(conn, uid, weeks_back=8)
    assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_assessments_heatmap_query.py -v
```
Expected: 4 failures (AttributeError: no attribute 'heatmap_data').

- [ ] **Step 3: Add the function**

Append to `src/school_test_engine/storage/assessments_repo.py`:

```python
def heatmap_data(
    conn: sqlite3.Connection, user_id: int, weeks_back: int = 8,
) -> dict[str, dict["date", float]]:
    """Returns {subject: {week_monday_date: avg_grade}} for assessments within
    the last `weeks_back` weeks. Week start is Monday."""
    from datetime import date, timedelta
    today = date.today()
    earliest_monday = today - timedelta(days=today.weekday() + (weeks_back - 1) * 7)
    earliest_iso = earliest_monday.isoformat()

    cur = conn.execute(
        """
        SELECT subject, assessment_date, grade
        FROM assessments
        WHERE user_id = ? AND assessment_date >= ?
        ORDER BY subject ASC, assessment_date ASC
        """,
        (user_id, earliest_iso),
    )
    result: dict[str, dict[date, list[float]]] = {}
    for row in cur.fetchall():
        d = date.fromisoformat(row["assessment_date"])
        monday = d - timedelta(days=d.weekday())
        result.setdefault(row["subject"], {}).setdefault(monday, []).append(float(row["grade"]))

    # Average each week's grades
    averaged: dict[str, dict[date, float]] = {}
    for subject, weeks in result.items():
        averaged[subject] = {wk: sum(vals) / len(vals) for wk, vals in weeks.items()}
    return averaged
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_assessments_heatmap_query.py -v
```
Expected: 4 passes.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/assessments_repo.py \
        tests/test_assessments_heatmap_query.py
git commit -m "feat(phase14): assessments_repo.heatmap_data aggregation"
```

---

### Task 9: GradeChart widget

**Files:**
- Create: `src/school_test_engine/ui/widgets/grade_chart.py`
- Test: `tests/test_grade_chart.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_grade_chart.py`:

```python
"""Phase 14 Track C: GradeChart QPainter widget."""
from __future__ import annotations

import os
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_grade_chart_constructs_empty(app):
    from school_test_engine.ui.widgets.grade_chart import GradeChart
    chart = GradeChart()
    assert chart.minimumHeight() >= 200


def test_grade_chart_set_data_does_not_raise(app):
    from school_test_engine.ui.widgets.grade_chart import GradeChart
    chart = GradeChart()
    today = date.today()
    chart.set_data(
        schriftlich=[(today - timedelta(days=30), 2.0), (today, 2.5)],
        muendlich=[(today - timedelta(days=60), 2.5), (today - timedelta(days=10), 2.0)],
    )
    # No exception = success


def test_grade_chart_paints_without_exception(app):
    from school_test_engine.ui.widgets.grade_chart import GradeChart
    from PySide6.QtCore import QSize
    chart = GradeChart()
    chart.resize(QSize(400, 200))
    today = date.today()
    chart.set_data(
        schriftlich=[(today - timedelta(days=30), 2.0), (today, 2.5)],
        muendlich=[],
    )
    pixmap = chart.grab()
    assert not pixmap.isNull()


def test_grade_chart_placeholder_when_too_few_points(app):
    from school_test_engine.ui.widgets.grade_chart import GradeChart
    chart = GradeChart()
    chart.set_data(schriftlich=[], muendlich=[])
    pixmap = chart.grab()
    assert not pixmap.isNull()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_grade_chart.py -v
```
Expected: 4 failures (ModuleNotFoundError).

- [ ] **Step 3: Create the widget**

Create `src/school_test_engine/ui/widgets/grade_chart.py`:

```python
"""Phase 14 Track C: Notenverlauf-Liniendiagramm pro Fach."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


CLAY = "#c26a3d"
TEA = "#658a47"
PAPER_300 = "#d8cdb8"
PAPER_500 = "#8a8068"
PAPER_600 = "#6f6757"


class GradeChart(QWidget):
    """Line-chart for grade history. X = date, Y = grade (1 top, 6 bottom).

    Two series: schriftlich (clay) and muendlich (tea). Dotted line when
    fewer than 2 points in a series. Placeholder when both empty.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self._schriftlich: list[tuple[date, float]] = []
        self._muendlich: list[tuple[date, float]] = []

    def sizeHint(self) -> QSize:
        return QSize(500, 220)

    def set_data(
        self,
        schriftlich: list[tuple[date, float]],
        muendlich: list[tuple[date, float]],
    ) -> None:
        self._schriftlich = sorted(schriftlich, key=lambda t: t[0])
        self._muendlich = sorted(muendlich, key=lambda t: t[0])
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        all_pts = self._schriftlich + self._muendlich
        if len(all_pts) < 2:
            self._paint_placeholder(p)
            return

        margin_left = 36
        margin_right = 16
        margin_top = 24
        margin_bottom = 32
        rect = self.rect().adjusted(margin_left, margin_top, -margin_right, -margin_bottom)

        # X-axis range
        min_date = min(d for d, _ in all_pts)
        max_date = max(d for d, _ in all_pts)
        if (max_date - min_date).days < 30:
            max_date = min_date + timedelta(days=30)
        date_span = max(1, (max_date - min_date).days)

        # Helpers
        def x_for(d: date) -> float:
            t = (d - min_date).days / date_span
            return rect.left() + t * rect.width()

        def y_for(grade: float) -> float:
            # 1 at top, 6 at bottom
            t = (grade - 1.0) / 5.0
            return rect.top() + t * rect.height()

        # Y-axis grid + labels
        p.setPen(QPen(QColor(PAPER_300), 1))
        p.setFont(QFont("Inter", 8))
        for g in range(1, 7):
            y = y_for(float(g))
            p.drawLine(rect.left(), int(y), rect.right(), int(y))
            p.setPen(QPen(QColor(PAPER_600), 1))
            p.drawText(rect.left() - 26, int(y) + 4, f"{g}")
            p.setPen(QPen(QColor(PAPER_300), 1))

        # X-axis labels (month tick at left + right)
        p.setPen(QPen(QColor(PAPER_600), 1))
        p.drawText(rect.left(), rect.bottom() + 16, min_date.strftime("%b %Y"))
        p.drawText(rect.right() - 60, rect.bottom() + 16, max_date.strftime("%b %Y"))

        # Plot series
        self._plot_series(p, self._schriftlich, QColor(CLAY), x_for, y_for)
        self._plot_series(p, self._muendlich, QColor(TEA), x_for, y_for)

        # Legend
        p.setFont(QFont("Inter", 9))
        legend_y = margin_top - 4
        p.setBrush(QColor(CLAY))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(rect.right() - 140, legend_y, 8, 8)
        p.setPen(QPen(QColor(PAPER_600), 1))
        p.drawText(rect.right() - 128, legend_y + 8, "schriftlich")
        p.setBrush(QColor(TEA))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(rect.right() - 70, legend_y, 8, 8)
        p.setPen(QPen(QColor(PAPER_600), 1))
        p.drawText(rect.right() - 58, legend_y + 8, "mündlich")

    def _plot_series(self, p, series, color, x_for, y_for) -> None:
        if not series:
            return
        pen = QPen(color, 2)
        if len(series) < 2:
            pen.setStyle(Qt.PenStyle.DotLine)
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)
        p.setPen(pen)
        path = QPainterPath()
        first_x = x_for(series[0][0])
        first_y = y_for(series[0][1])
        path.moveTo(first_x, first_y)
        for d, g in series[1:]:
            path.lineTo(x_for(d), y_for(g))
        p.drawPath(path)
        # Points
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        for d, g in series:
            p.drawEllipse(int(x_for(d)) - 4, int(y_for(g)) - 4, 8, 8)

    def _paint_placeholder(self, p: QPainter) -> None:
        p.setPen(QPen(QColor(PAPER_500), 1))
        p.setFont(QFont("Inter", 11))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Mehr Noten = aussagekräftiger Verlauf")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_grade_chart.py -v
```
Expected: 4 passes.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/widgets/grade_chart.py \
        tests/test_grade_chart.py
git commit -m "feat(phase14): GradeChart QPainter widget"
```

---

### Task 10: GradeHeatmap widget

**Files:**
- Create: `src/school_test_engine/ui/widgets/grade_heatmap.py`
- Test: `tests/test_grade_heatmap.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_grade_heatmap.py`:

```python
"""Phase 14 Track C: GradeHeatmap widget."""
from __future__ import annotations

import os
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_heatmap_constructs(app):
    from school_test_engine.ui.widgets.grade_heatmap import GradeHeatmap
    hm = GradeHeatmap()
    assert hm.minimumHeight() >= 220


def test_heatmap_paints_empty(app):
    from school_test_engine.ui.widgets.grade_heatmap import GradeHeatmap
    hm = GradeHeatmap()
    hm.resize(600, 220)
    pixmap = hm.grab()
    assert not pixmap.isNull()


def test_heatmap_set_data_paints(app):
    from school_test_engine.ui.widgets.grade_heatmap import GradeHeatmap
    hm = GradeHeatmap()
    hm.resize(600, 240)
    monday = date.today() - timedelta(days=date.today().weekday())
    weeks = [monday - timedelta(weeks=i) for i in reversed(range(8))]
    hm.set_data(
        weeks=weeks,
        rows=[
            ("Mathe", {weeks[7]: 2.0, weeks[5]: 3.0}),
            ("Englisch", {weeks[6]: 2.5}),
        ],
    )
    pixmap = hm.grab()
    assert not pixmap.isNull()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_grade_heatmap.py -v
```
Expected: 3 failures (ModuleNotFoundError).

- [ ] **Step 3: Create the widget**

Create `src/school_test_engine/ui/widgets/grade_heatmap.py`:

```python
"""Phase 14 Track C: Fach × Wochen Heatmap."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


PAPER_100 = "#f4efe6"
PAPER_300 = "#d8cdb8"
PAPER_500 = "#8a8068"
PAPER_600 = "#6f6757"
FG = "#1e1b15"


def _cell_color(grade: float) -> QColor:
    """Returns a pastel color for a grade. 1=clear tea, 6=clear rose."""
    if grade <= 2.0:
        return QColor("#bcd2a4")   # tea-pastel
    if grade <= 3.0:
        return QColor("#dde8d0")   # tea-light
    if grade <= 4.0:
        return QColor("#f6e3bb")   # honey
    return QColor("#f6c8c2")       # rose


class GradeHeatmap(QWidget):
    """8 weeks × subjects heatmap."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self._weeks: list[date] = []
        self._rows: list[tuple[str, dict[date, float]]] = []

    def sizeHint(self) -> QSize:
        return QSize(560, 280)

    def set_data(
        self,
        weeks: list[date],
        rows: list[tuple[str, dict[date, float]]],
    ) -> None:
        self._weeks = list(weeks)
        self._rows = list(rows)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self._rows or not self._weeks:
            p.setPen(QPen(QColor(PAPER_500), 1))
            p.setFont(QFont("Inter", 11))
            p.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "Noch keine Noten in den letzten 8 Wochen",
            )
            return

        label_width = 90
        legend_height = 28
        header_height = 22
        body_top = header_height
        body_bottom = self.height() - legend_height
        cells_left = label_width
        cells_width = self.width() - cells_left - 8
        cell_w = max(20, cells_width // max(1, len(self._weeks)))
        row_h = max(28, (body_bottom - body_top - 4) // max(1, len(self._rows)))

        # Header row (week labels)
        p.setFont(QFont("Inter", 9))
        p.setPen(QPen(QColor(PAPER_600), 1))
        for i, monday in enumerate(self._weeks):
            week_num = monday.isocalendar().week
            x = cells_left + i * cell_w
            p.drawText(QRect(x, 0, cell_w, header_height),
                       Qt.AlignmentFlag.AlignCenter,
                       f"KW {week_num:02d}")

        # Subject rows + cells
        p.setFont(QFont("Inter", 10))
        for row_i, (subject, week_grades) in enumerate(self._rows):
            y = body_top + row_i * row_h
            # Label
            p.setPen(QPen(QColor(FG), 1))
            p.drawText(QRect(0, y, label_width - 8, row_h),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       subject)
            # Cells
            for i, monday in enumerate(self._weeks):
                x = cells_left + i * cell_w
                inner = QRect(x + 2, y + 2, cell_w - 4, row_h - 4)
                if monday in week_grades:
                    color = _cell_color(week_grades[monday])
                    p.setBrush(color)
                else:
                    p.setBrush(QColor(PAPER_100))
                p.setPen(QPen(QColor(PAPER_300), 1))
                p.drawRoundedRect(inner, 4, 4)

        # Legend
        legend_y = self.height() - legend_height + 4
        p.setFont(QFont("Inter", 9))
        items = [
            ("≤2,0", _cell_color(2.0)),
            ("≤3,0", _cell_color(3.0)),
            ("≤4,0", _cell_color(4.0)),
            (">4,0", _cell_color(5.0)),
            ("keine", QColor(PAPER_100)),
        ]
        legend_x = cells_left
        for label, color in items:
            p.setBrush(color)
            p.setPen(QPen(QColor(PAPER_300), 1))
            p.drawRoundedRect(legend_x, legend_y, 14, 14, 3, 3)
            p.setPen(QPen(QColor(PAPER_600), 1))
            p.drawText(legend_x + 18, legend_y + 12, label)
            legend_x += 60
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_grade_heatmap.py -v
```
Expected: 3 passes.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/widgets/grade_heatmap.py \
        tests/test_grade_heatmap.py
git commit -m "feat(phase14): GradeHeatmap QPainter widget"
```

---

### Task 11: Embed GradeChart on Noten-Page

**Files:**
- Modify: `src/school_test_engine/ui/pages/grades.py`

- [ ] **Step 1: Add import**

In `src/school_test_engine/ui/pages/grades.py`, near the existing widget imports:

```python
from ..widgets.grade_chart import GradeChart
```

- [ ] **Step 2: Instantiate GradeChart and embed it**

In `GradesPage.__init__`, after the assessments list scroll-area is wired up, you don't need to add `GradeChart` to the constructor. Instead, build it lazily inside `_render_content`.

In `_render_content`, after the hero is added (`self._content_layout.addWidget(self._build_average_hero(avg))`) and before the empty/loop, insert:

```python
        # Phase 14: Notenverlauf-Chart
        chart_eyebrow = QLabel("NOTENVERLAUF")
        chart_eyebrow.setObjectName("eyebrow")
        self._content_layout.addWidget(chart_eyebrow)

        from datetime import date as _date
        schriftlich_pts = [
            (_date.fromisoformat(r["assessment_date"]), float(r["grade"]))
            for r in assessments_repo.list_by_subject(self.conn, uid, self._current_subject)
            if r["category"] == "schriftlich"
        ]
        muendlich_pts = [
            (_date.fromisoformat(r["assessment_date"]), float(r["grade"]))
            for r in assessments_repo.list_by_subject(self.conn, uid, self._current_subject)
            if r["category"] == "muendlich"
        ]
        chart = GradeChart()
        chart.set_data(schriftlich=schriftlich_pts, muendlich=muendlich_pts)
        self._content_layout.addWidget(chart)
```

(The two list-comprehensions iterate the same SQL twice — that's fine for now; can be optimized later. `rows` was already fetched in the existing code further down; if so, reuse `rows` instead.)

- [ ] **Step 3: Run full suite**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q
```
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/pages/grades.py
git commit -m "feat(phase14): embed GradeChart on Noten-Page"
```

---

### Task 12: Embed GradeHeatmap on History-Page

**Files:**
- Modify: `src/school_test_engine/ui/pages/history.py`

- [ ] **Step 1: Add imports**

In `src/school_test_engine/ui/pages/history.py`:

```python
from datetime import date, timedelta
from ...storage import assessments_repo
from ..widgets.grade_heatmap import GradeHeatmap
```

- [ ] **Step 2: Embed the heatmap above existing content**

In `HistoryPage`, locate where the main content widgets are built (likely `reload()` or `__init__`). Before the existing table/list, add a new section.

If the layout is built in `__init__`:

```python
        # Phase 14: Wochen-Heatmap
        heatmap_eyebrow = QLabel("WOCHEN-ÜBERSICHT")
        heatmap_eyebrow.setObjectName("eyebrow")
        outer.addWidget(heatmap_eyebrow)
        self.heatmap = GradeHeatmap()
        outer.addWidget(self.heatmap)
```

(`outer` adapted to actual layout variable name.)

In `reload()`, populate the heatmap:

```python
        uid = self.window.active_user_id
        if uid is not None:
            today = date.today()
            monday_today = today - timedelta(days=today.weekday())
            weeks = [monday_today - timedelta(weeks=i) for i in reversed(range(8))]
            raw = assessments_repo.heatmap_data(self.conn, uid, weeks_back=8)
            rows = sorted(raw.items(), key=lambda kv: kv[0])
            self.heatmap.set_data(weeks=weeks, rows=rows)
```

- [ ] **Step 3: Run full suite**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q
```
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/pages/history.py
git commit -m "feat(phase14): embed GradeHeatmap on History-Page"
```

---

### Task 13: pdf_export base module

**Files:**
- Create: `src/school_test_engine/pdf_export/__init__.py`
- Create: `src/school_test_engine/pdf_export/_common.py`

- [ ] **Step 1: Create the package**

Create `src/school_test_engine/pdf_export/__init__.py`:

```python
"""Phase 14 Track D: PDF export templates (test sheet, study plan, grade report)."""
```

- [ ] **Step 2: Create the common module**

Create `src/school_test_engine/pdf_export/_common.py`:

```python
"""Shared HTML + render helpers for PDF templates."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QFileDialog, QWidget


CSS = """
<style>
  body { font-family: 'Inter', sans-serif; color: #1e1b15; font-size: 11pt; }
  h1 { font-family: 'Fraunces', serif; font-size: 24pt; margin: 0 0 4pt; color: #13110c; }
  h2 { font-family: 'Fraunces', serif; font-size: 16pt; margin: 16pt 0 6pt; color: #1e1b15; }
  .eyebrow { font-size: 9pt; color: #6f6757; letter-spacing: 1.5pt; text-transform: uppercase; }
  .wordmark { font-family: 'Fraunces', serif; font-size: 12pt; color: #4a4538; }
  .footer { font-size: 8pt; color: #a89e89; text-align: center; margin-top: 24pt; }
  .question { margin-bottom: 14pt; }
  .question .num { font-weight: 600; color: #4a4538; }
  table { border-collapse: collapse; width: 100%; }
  th, td { padding: 4pt 8pt; border-bottom: 1px solid #ebe3d5; text-align: left; }
  th { color: #6f6757; font-size: 9pt; font-weight: 500; }
  .answer-line { display: inline-block; border-bottom: 1px solid #4a4538; height: 18pt; min-width: 200pt; }
  .option-bullet { font-size: 14pt; vertical-align: middle; }
</style>
"""


def html_header(title: str) -> str:
    """Returns the opening <html><head>...</head><body><wordmark><h1>title</h1>."""
    return (
        f"<html><head><meta charset='utf-8'/>{CSS}</head><body>"
        f"<div class='wordmark'>Learning Buddy</div>"
        f"<h1>{title}</h1>"
    )


def html_footer() -> str:
    return "<div class='footer'>designed by Matthias</div></body></html>"


def render_to_pdf(html: str, output_path: str) -> None:
    """Render an HTML string to a PDF at output_path."""
    document = QTextDocument()
    document.setHtml(html)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(output_path)
    document.print_(printer)


def render_to_bytes(html: str) -> bytes:
    """Render an HTML string to PDF bytes (in-memory). Useful for tests."""
    import tempfile, os as _os
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        render_to_pdf(html, tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        _os.unlink(tmp_path)


def save_pdf_with_dialog(
    parent: QWidget, html: str, default_filename: str,
) -> bool:
    """Open a save dialog and render the PDF on confirm. Returns True on success."""
    path, _ = QFileDialog.getSaveFileName(
        parent, "PDF speichern", default_filename, "PDF (*.pdf)",
    )
    if not path:
        return False
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    render_to_pdf(html, path)
    return True
```

- [ ] **Step 3: Run full suite (smoke import)**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q
```
Expected: all green (no behavior change, just new files).

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/pdf_export/
git commit -m "feat(phase14): pdf_export base module with HTML helpers"
```

---

### Task 14: test_sheet PDF + Library button

**Files:**
- Create: `src/school_test_engine/pdf_export/test_sheet.py`
- Modify: `src/school_test_engine/ui/pages/library.py`
- Test: `tests/test_pdf_test_sheet.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_pdf_test_sheet.py`:

```python
"""Phase 14 Track D: Test-Sheet PDF export."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.storage import run_migrations, users_repo


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


def _make_test(conn, uid, subject="Mathe"):
    cur = conn.execute(
        "INSERT INTO tests (user_id, subject, created_at) VALUES (?, ?, datetime('now'))",
        (uid, subject),
    )
    test_id = cur.lastrowid
    for i, (prompt, kind, answer) in enumerate([
        ("Was ist 1+1?", "single", "2"),
        ("Was ist 3+4?", "short_answer", "7"),
    ]):
        cur = conn.execute(
            "INSERT INTO questions (test_id, position, kind, prompt, points, answer_text) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (test_id, i, kind, prompt, answer),
        )
        if kind == "single":
            qid = cur.lastrowid
            for pos, label, is_correct in [(0, "1", 0), (1, "2", 1), (2, "3", 0)]:
                conn.execute(
                    "INSERT INTO choices (question_id, position, label, is_correct) "
                    "VALUES (?, ?, ?, ?)",
                    (qid, pos, label, is_correct),
                )
    conn.commit()
    return test_id


def test_export_test_sheet_returns_html_with_questions(app, conn):
    from school_test_engine.pdf_export.test_sheet import export_test_sheet
    uid = users_repo.create_user(conn, "Test", "👤")
    test_id = _make_test(conn, uid)
    html = export_test_sheet(conn, test_id)
    assert "Was ist 1+1?" in html
    assert "Was ist 3+4?" in html
    assert "Learning Buddy" in html
    assert "Lösungen" in html or "LÖSUNGEN" in html


def test_export_test_sheet_renders_to_pdf_bytes(app, conn):
    from school_test_engine.pdf_export.test_sheet import export_test_sheet
    from school_test_engine.pdf_export._common import render_to_bytes
    uid = users_repo.create_user(conn, "Test", "👤")
    test_id = _make_test(conn, uid)
    html = export_test_sheet(conn, test_id)
    pdf = render_to_bytes(html)
    assert pdf[:5] == b"%PDF-"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_pdf_test_sheet.py -v
```
Expected: 2 failures (ModuleNotFoundError).

- [ ] **Step 3: Create the template**

Create `src/school_test_engine/pdf_export/test_sheet.py`:

```python
"""Phase 14 Track D: Render a test as a printable worksheet + solutions page."""
from __future__ import annotations

import sqlite3
from datetime import date
from html import escape

from ._common import html_header, html_footer


def export_test_sheet(conn: sqlite3.Connection, test_id: int) -> str:
    """Render a test as a printable worksheet HTML. Two-section layout:
    questions on page 1+, solutions on a separate page."""
    test_row = conn.execute(
        "SELECT * FROM tests WHERE id = ?", (test_id,),
    ).fetchone()
    if test_row is None:
        raise ValueError(f"Test {test_id} not found")
    subject = test_row["subject"]
    today_str = date.today().strftime("%d.%m.%Y")

    questions = conn.execute(
        "SELECT * FROM questions WHERE test_id = ? ORDER BY position ASC",
        (test_id,),
    ).fetchall()

    parts = [
        html_header(f"{escape(subject)} · Übungs-Test"),
        f"<div class='eyebrow'>{escape(today_str)}</div>",
        "<p>Name: <span class='answer-line'></span> &nbsp;&nbsp; Klasse: <span class='answer-line'></span></p>",
    ]

    # Page 1+: questions
    for i, q in enumerate(questions, start=1):
        parts.append("<div class='question'>")
        parts.append(f"<span class='num'>{i}.</span> {escape(q['prompt'])}<br/>")
        if q["kind"] in ("single", "multi"):
            choices = conn.execute(
                "SELECT * FROM choices WHERE question_id = ? ORDER BY position ASC",
                (q["id"],),
            ).fetchall()
            for c in choices:
                parts.append(
                    f"<span class='option-bullet'>○</span> {escape(c['label'])}<br/>"
                )
        else:  # short_answer
            parts.append("<span class='answer-line'></span><br/><br/>")
            parts.append("<span class='answer-line'></span>")
        parts.append("</div>")

    # Page break → solutions
    parts.append("<div style='page-break-before: always;'>")
    parts.append("<h2>Lösungen</h2>")
    for i, q in enumerate(questions, start=1):
        if q["kind"] in ("single", "multi"):
            correct = conn.execute(
                "SELECT label FROM choices WHERE question_id = ? AND is_correct = 1 "
                "ORDER BY position ASC",
                (q["id"],),
            ).fetchall()
            answer = ", ".join(escape(c["label"]) for c in correct)
        else:
            answer = escape(q["answer_text"] or "")
        parts.append(f"<p><span class='num'>{i}.</span> {answer}</p>")
    parts.append("</div>")

    parts.append(html_footer())
    return "".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_pdf_test_sheet.py -v
```
Expected: 2 passes.

- [ ] **Step 5: Add PDF button to Library cards**

In `src/school_test_engine/ui/pages/library.py`, locate where the per-test action buttons are added to each Test-Card (likely a row with „Starten →" and „…"). Add a third button before that row's `addStretch` (if any):

```python
        pdf_btn = QPushButton("PDF")
        pdf_btn.setObjectName("text")
        pdf_btn.clicked.connect(lambda _, tid=test["id"], subj=test["subject"]: self._export_pdf(tid, subj))
        # add to the actions row layout (variable name depends on context)
```

Add a new method on `LibraryPage`:

```python
    def _export_pdf(self, test_id: int, subject: str) -> None:
        from ...pdf_export.test_sheet import export_test_sheet
        from ...pdf_export._common import save_pdf_with_dialog
        from datetime import date
        html = export_test_sheet(self.conn, test_id)
        default = f"learning-buddy-{subject.lower()}-{date.today().isoformat()}.pdf"
        save_pdf_with_dialog(self, html, default)
```

- [ ] **Step 6: Run full suite**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/school_test_engine/pdf_export/test_sheet.py \
        src/school_test_engine/ui/pages/library.py \
        tests/test_pdf_test_sheet.py
git commit -m "feat(phase14): test-sheet PDF export + Library button"
```

---

### Task 15: study_plan PDF + ExamCard + EventEditPage buttons

**Files:**
- Create: `src/school_test_engine/pdf_export/study_plan.py`
- Modify: `src/school_test_engine/ui/widgets/exam_card.py`
- Modify: `src/school_test_engine/ui/pages/event_edit.py`
- Test: `tests/test_pdf_study_plan.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_pdf_study_plan.py`:

```python
"""Phase 14 Track D: Study-Plan PDF export."""
from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.storage import events_repo, run_migrations, users_repo


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "sp.db")
    c.row_factory = sqlite3.Row
    run_migrations(c)
    yield c
    c.close()


def test_export_study_plan_basic(app, conn):
    from school_test_engine.pdf_export.study_plan import export_study_plan
    uid = users_repo.create_user(conn, "Test", "👤")
    eid = events_repo.create(
        conn, uid, "Mathe", "klassenarbeit",
        (date.today() + timedelta(days=6)).isoformat(),
        topics=["Bruchrechnung", "Gleichungen", "Geometrie"],
        note=None,
    )
    html = export_study_plan(conn, eid)
    assert "LERNPLAN" in html or "Lernplan" in html
    assert "Bruchrechnung" in html
    assert "Gleichungen" in html
    assert "Geometrie" in html
    assert "Learning Buddy" in html


def test_export_study_plan_renders_pdf(app, conn):
    from school_test_engine.pdf_export.study_plan import export_study_plan
    from school_test_engine.pdf_export._common import render_to_bytes
    uid = users_repo.create_user(conn, "Test", "👤")
    eid = events_repo.create(
        conn, uid, "Bio", "test",
        (date.today() + timedelta(days=3)).isoformat(),
        topics=["Zellbiologie"],
        note=None,
    )
    html = export_study_plan(conn, eid)
    pdf = render_to_bytes(html)
    assert pdf[:5] == b"%PDF-"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_pdf_study_plan.py -v
```
Expected: 2 failures.

- [ ] **Step 3: Create the template**

Create `src/school_test_engine/pdf_export/study_plan.py`:

```python
"""Phase 14 Track D: Render a study plan PDF for an upcoming KA."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from html import escape

from ..storage import events_repo
from ._common import html_header, html_footer


KIND_LABELS = {
    "klassenarbeit": "Klassenarbeit",
    "klausur": "Klausur",
    "test": "Test",
    "sonstiges": "Sonstiges",
}


def _topic_mastery(conn: sqlite3.Connection, user_id: int, subject: str, topic: str) -> tuple[int, int]:
    """Returns (correct, total) for this user/subject/topic across all attempts.
    (0, 0) means never practiced."""
    row = conn.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct,
          COUNT(*) AS total
        FROM answers a
        JOIN questions q ON q.id = a.question_id
        JOIN tests t     ON t.id = q.test_id
        JOIN attempts at ON at.id = a.attempt_id
        WHERE t.user_id = ? AND t.subject = ? AND q.topic = ?
        """,
        (user_id, subject, topic),
    ).fetchone()
    return int(row["correct"] or 0), int(row["total"] or 0)


def _mastery_bar(correct: int, total: int) -> str:
    if total == 0:
        return "○○○○○"
    filled = round(5 * correct / total)
    return "●" * filled + "○" * (5 - filled)


def export_study_plan(conn: sqlite3.Connection, event_id: int) -> str:
    ev = events_repo.get(conn, event_id)
    if ev is None:
        raise ValueError(f"Event {event_id} not found")

    event_date = date.fromisoformat(ev["event_date"])
    today = date.today()
    days_until = (event_date - today).days
    countdown = "heute" if days_until == 0 else (
        f"in {days_until} Tagen" if days_until > 0 else f"vor {abs(days_until)} Tagen"
    )
    subject = ev["subject"]
    kind = KIND_LABELS.get(ev["kind"], "Termin")
    topics = json.loads(ev["topics"] or "[]")
    user_id = ev["user_id"]

    parts = [
        html_header(f"{escape(subject)} {escape(kind)}"),
        "<div class='eyebrow'>LERNPLAN</div>",
        f"<p>{escape(event_date.strftime('%d. %B %Y'))} · {escape(countdown)}</p>",
        "<h2>Themen der KA</h2>",
        "<table>",
        "<tr><th>Thema</th><th>Stand</th><th>Versuche</th></tr>",
    ]

    rated: list[tuple[str, int, int]] = []
    for topic in topics:
        correct, total = _topic_mastery(conn, user_id, subject, topic)
        rated.append((topic, correct, total))
        bar = _mastery_bar(correct, total)
        last = f"{correct}/{total}" if total > 0 else "noch nicht geübt"
        parts.append(
            f"<tr><td>{escape(topic)}</td><td>{bar}</td><td>{escape(last)}</td></tr>"
        )
    parts.append("</table>")

    # Empfehlungs-Reihenfolge: weakest first; "noch nicht geübt" zählt als 0/1
    def _ratio(t):
        _, correct, total = t
        if total == 0:
            return -1.0  # sort lowest, i.e. first
        return correct / total

    sorted_topics = sorted(rated, key=_ratio)
    parts.append("<h2>Empfehlung</h2>")
    parts.append("<ol>")
    for topic, correct, total in sorted_topics:
        if total == 0:
            hint = "noch nicht geübt"
        elif correct / total < 0.6:
            hint = "schwach"
        else:
            hint = "zur Sicherheit"
        parts.append(f"<li>{escape(topic)} — {hint}</li>")
    parts.append("</ol>")
    parts.append(html_footer())
    return "".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_pdf_study_plan.py -v
```
Expected: 2 passes.

- [ ] **Step 5: Add ExamCard "Lernplan PDF" button**

In `src/school_test_engine/ui/widgets/exam_card.py`, find the action-row build (currently has `practice_btn` and `grade_btn` when `linked_assessment_id is None`). Add a third button + a new signal at the top of the class:

```python
class ExamCard(ClickableCard):
    # ...
    practice_clicked = Signal(int)
    enter_grade_clicked = Signal(int)
    edit_clicked = Signal(int)
    study_plan_clicked = Signal(int)   # NEW
```

In the action row build, add after `grade_btn`:

```python
            plan_btn = QPushButton("Lernplan PDF")
            plan_btn.setObjectName("text")
            plan_btn.clicked.connect(lambda: self.study_plan_clicked.emit(self.event_id))
            actions.addWidget(plan_btn)
```

In `menu.py`, find where `practice_clicked` is connected on the ExamCard instance and connect the new signal:

```python
        card.study_plan_clicked.connect(self._on_export_study_plan)
```

Add a new method on `MenuPage`:

```python
    def _on_export_study_plan(self, event_id: int) -> None:
        from ...pdf_export.study_plan import export_study_plan
        from ...pdf_export._common import save_pdf_with_dialog
        from datetime import date
        html = export_study_plan(self.conn, event_id)
        default = f"learning-buddy-lernplan-{date.today().isoformat()}.pdf"
        save_pdf_with_dialog(self, html, default)
```

- [ ] **Step 6: Add Lernplan-Button to EventEditPage in edit mode**

In `src/school_test_engine/ui/pages/event_edit.py`, the footer currently has `delete_btn`. Add a second footer button to the left of it, visible only in edit mode:

```python
        self.plan_btn = QPushButton("Lernplan PDF")
        self.plan_btn.setObjectName("text")
        self.plan_btn.clicked.connect(self._export_plan)
        self.plan_btn.setVisible(False)
        footer.addWidget(self.plan_btn)
```

(Add immediately before `footer.addWidget(self.delete_btn)`.)

In `show_for`, when `event_id is not None`:

```python
            self.plan_btn.setVisible(True)
```

(And `setVisible(False)` in the new-mode branch.)

New method:

```python
    def _export_plan(self) -> None:
        if self._event_id is None:
            return
        from ...pdf_export.study_plan import export_study_plan
        from ...pdf_export._common import save_pdf_with_dialog
        from datetime import date
        html = export_study_plan(self.conn, self._event_id)
        default = f"learning-buddy-lernplan-{date.today().isoformat()}.pdf"
        save_pdf_with_dialog(self, html, default)
```

- [ ] **Step 7: Run full suite**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q
```
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add src/school_test_engine/pdf_export/study_plan.py \
        src/school_test_engine/ui/widgets/exam_card.py \
        src/school_test_engine/ui/pages/event_edit.py \
        src/school_test_engine/ui/pages/menu.py \
        tests/test_pdf_study_plan.py
git commit -m "feat(phase14): study-plan PDF export + ExamCard + EventEditPage buttons"
```

---

### Task 16: grade_report PDF + Noten-Page button

**Files:**
- Create: `src/school_test_engine/pdf_export/grade_report.py`
- Modify: `src/school_test_engine/ui/pages/grades.py`
- Test: `tests/test_pdf_grade_report.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_pdf_grade_report.py`:

```python
"""Phase 14 Track D: Grade-Report PDF export."""
from __future__ import annotations

import os
import sqlite3
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.storage import assessments_repo, run_migrations, users_repo


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "gr.db")
    c.row_factory = sqlite3.Row
    run_migrations(c)
    yield c
    c.close()


def test_export_grade_report_basic(app, conn):
    from school_test_engine.pdf_export.grade_report import export_grade_report
    uid = users_repo.create_user(conn, "Clemens", "👤")
    assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", date.today().isoformat(),
        grade=2.0, points=None, max_points=None, note=None, scheduled_event_id=None,
    )
    assessments_repo.create(
        conn, uid, "Englisch", "muendlich", date.today().isoformat(),
        grade=3.0, points=None, max_points=None, note=None, scheduled_event_id=None,
    )
    html = export_grade_report(conn, uid)
    assert "Clemens" in html
    assert "Mathe" in html
    assert "Englisch" in html
    assert "Learning Buddy" in html


def test_export_grade_report_renders_pdf(app, conn):
    from school_test_engine.pdf_export.grade_report import export_grade_report
    from school_test_engine.pdf_export._common import render_to_bytes
    uid = users_repo.create_user(conn, "Clemens", "👤")
    assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", date.today().isoformat(),
        grade=2.0, points=None, max_points=None, note=None, scheduled_event_id=None,
    )
    html = export_grade_report(conn, uid)
    pdf = render_to_bytes(html)
    assert pdf[:5] == b"%PDF-"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_pdf_grade_report.py -v
```
Expected: 2 failures.

- [ ] **Step 3: Create the template**

Create `src/school_test_engine/pdf_export/grade_report.py`:

```python
"""Phase 14 Track D: Render a current grade report PDF for one user."""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import date
from html import escape
from pathlib import Path

from ..cockpit import service as cockpit
from ..storage import assessments_repo, users_repo
from ._common import html_header, html_footer


CATEGORY_LABEL = {"schriftlich": "schriftlich", "muendlich": "mündlich", "sonstige": "sonstige"}


def _row(d: dict | None, key: str, default=None):
    if d is None:
        return default
    try:
        v = d[key]
        return v if v is not None else default
    except (KeyError, IndexError):
        return default


def export_grade_report(conn: sqlite3.Connection, user_id: int) -> str:
    user = users_repo.get_user(conn, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")

    name = user["name"]
    school_name = _row(user, "school_name", "")
    grade_klass = _row(user, "grade")
    school_year = _row(user, "school_year", "")
    school_line_parts: list[str] = []
    if school_name:
        school_line_parts.append(escape(school_name))
    if grade_klass:
        school_line_parts.append(f"Klasse {int(grade_klass)}")
    if school_year:
        school_line_parts.append(f"Schuljahr {escape(school_year)}")
    school_line = " · ".join(school_line_parts) or "&nbsp;"

    today_str = date.today().strftime("%d.%m.%Y")
    parts = [
        html_header(f"{escape(name)} — Notenübersicht"),
        f"<div class='eyebrow'>STAND: {escape(today_str)}</div>",
        f"<p>{school_line}</p>",
    ]

    # Fetch all subjects with at least one assessment
    subjects = sorted({
        row["subject"]
        for row in conn.execute(
            "SELECT DISTINCT subject FROM assessments WHERE user_id = ? ORDER BY subject",
            (user_id,),
        ).fetchall()
    })

    for subject in subjects:
        rows = assessments_repo.list_by_subject(conn, user_id, subject)
        if not rows:
            continue
        avg = cockpit.subject_grade_average(conn, user_id, subject)
        zeugnis = "—" if avg.zeugnis_estimate is None else f"{avg.zeugnis_estimate:.2f}".replace(".", ",")
        breakdown = (
            f"schriftlich {_fmt(avg.schriftlich_avg)} · "
            f"mündlich {_fmt(avg.muendlich_avg)}"
        )
        parts.append(f"<h2>{escape(subject)}</h2>")
        parts.append(f"<p><span style='font-family:Fraunces;font-size:28pt'>{zeugnis}</span><br/>")
        parts.append(f"<span class='eyebrow'>ZEUGNIS-SCHÄTZUNG</span> &nbsp; {breakdown}</p>")
        # Optional: embed chart as PNG
        chart_path = _render_chart_png(rows)
        if chart_path:
            parts.append(f"<p><img src='file://{chart_path}' width='480' /></p>")
        parts.append("<table>")
        parts.append("<tr><th>Datum</th><th>Art</th><th>Note</th><th>Notiz</th></tr>")
        for r in rows:
            cat = CATEGORY_LABEL.get(r["category"], r["category"])
            grade_str = f"{r['grade']:.1f}".rstrip("0").rstrip(".").replace(".", ",")
            note = r["note"] or ""
            parts.append(
                f"<tr><td>{r['assessment_date']}</td><td>{escape(cat)}</td>"
                f"<td>{grade_str}</td><td>{escape(note)}</td></tr>"
            )
        parts.append("</table>")

    if not subjects:
        parts.append("<p>Noch keine Noten erfasst.</p>")
    parts.append(html_footer())
    return "".join(parts)


def _fmt(val: float | None) -> str:
    if val is None:
        return "—"
    return f"{val:.2f}".replace(".", ",")


def _render_chart_png(rows: list) -> str | None:
    """Render a GradeChart with this subject's data to a temp PNG, return path."""
    try:
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is None:
            return None
        from ..ui.widgets.grade_chart import GradeChart
        from datetime import date as _date
        schriftlich = [
            (_date.fromisoformat(r["assessment_date"]), float(r["grade"]))
            for r in rows if r["category"] == "schriftlich"
        ]
        muendlich = [
            (_date.fromisoformat(r["assessment_date"]), float(r["grade"]))
            for r in rows if r["category"] == "muendlich"
        ]
        if len(schriftlich) + len(muendlich) < 2:
            return None
        chart = GradeChart()
        chart.resize(600, 220)
        chart.set_data(schriftlich=schriftlich, muendlich=muendlich)
        pixmap = chart.grab()
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        pixmap.save(tmp.name, "PNG")
        return tmp.name
    except Exception:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_pdf_grade_report.py -v
```
Expected: 2 passes.

- [ ] **Step 5: Add "Als PDF" button to Noten-Page top-bar**

In `src/school_test_engine/ui/pages/grades.py`, find the header row (currently: back-btn, stretch, +Note). Add a third button between stretch and +Note:

```python
        pdf_btn = QPushButton("Als PDF")
        pdf_btn.setObjectName("text")
        pdf_btn.clicked.connect(self._export_pdf)
        head.addWidget(pdf_btn)
        head.addWidget(add)   # existing +Note button stays last
```

Add a new method on `GradesPage`:

```python
    def _export_pdf(self) -> None:
        from ...pdf_export.grade_report import export_grade_report
        from ...pdf_export._common import save_pdf_with_dialog
        from datetime import date
        uid = self.window.active_user_id
        if uid is None:
            return
        html = export_grade_report(self.conn, uid)
        default = f"learning-buddy-notenuebersicht-{date.today().isoformat()}.pdf"
        save_pdf_with_dialog(self, html, default)
```

- [ ] **Step 6: Run full suite**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/school_test_engine/pdf_export/grade_report.py \
        src/school_test_engine/ui/pages/grades.py \
        tests/test_pdf_grade_report.py
git commit -m "feat(phase14): grade-report PDF export + Noten-Page button"
```

---

### Task 17: Final acceptance check

**Files:** none modified — verification only.

- [ ] **Step 1: Run full test suite**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
```
Expected: all green, count ≥ 276 (256 baseline + ~20 new).

- [ ] **Step 2: Verify spec acceptance criteria 1-12**

Run the verification script:

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && bash -c '
echo "=== Phase 14 ACCEPTANCE CHECKS ==="
echo ""
echo "1. App-Name in code:"
grep -q "setApplicationName(\"Learning Buddy\")" src/school_test_engine/app.py && echo "  ✓ app.py applicationName"
grep -q "setWindowTitle(\"Learning Buddy\")" src/school_test_engine/ui/main_window.py && echo "  ✓ MainWindow title"
echo ""
echo "2. .desktop file:"
grep -q "Name=Learning Buddy" school-test-engine.desktop && echo "  ✓ .desktop Name"
echo ""
echo "3. Wordmark in menu:"
grep -q "Learning Buddy" src/school_test_engine/ui/pages/menu.py && echo "  ✓ menu.py wordmark"
grep -q "designed by Matthias" src/school_test_engine/ui/pages/menu.py && echo "  ✓ menu.py footer"
echo ""
echo "4. Keyboard module exists:"
test -f src/school_test_engine/ui/keyboard_shortcuts.py && echo "  ✓ keyboard_shortcuts.py"
echo ""
echo "5. RunnerPage uses shortcuts:"
grep -q "install_runner_shortcuts" src/school_test_engine/ui/pages/runner.py && echo "  ✓ runner.py wires shortcuts"
grep -q "cheat_sheet" src/school_test_engine/ui/pages/runner.py && echo "  ✓ cheat_sheet label"
echo ""
echo "6. Chart widgets:"
test -f src/school_test_engine/ui/widgets/grade_chart.py && echo "  ✓ GradeChart"
test -f src/school_test_engine/ui/widgets/grade_heatmap.py && echo "  ✓ GradeHeatmap"
echo ""
echo "7. Charts integrated:"
grep -q "GradeChart" src/school_test_engine/ui/pages/grades.py && echo "  ✓ grades.py embeds chart"
grep -q "GradeHeatmap" src/school_test_engine/ui/pages/history.py && echo "  ✓ history.py embeds heatmap"
echo ""
echo "8. PDF export module:"
test -f src/school_test_engine/pdf_export/test_sheet.py && echo "  ✓ test_sheet.py"
test -f src/school_test_engine/pdf_export/study_plan.py && echo "  ✓ study_plan.py"
test -f src/school_test_engine/pdf_export/grade_report.py && echo "  ✓ grade_report.py"
echo ""
echo "9. PDF buttons wired:"
grep -q "_export_pdf\|PDF\"" src/school_test_engine/ui/pages/library.py && echo "  ✓ library.py PDF button"
grep -q "Lernplan PDF\|study_plan" src/school_test_engine/ui/widgets/exam_card.py && echo "  ✓ exam_card.py Lernplan button"
grep -q "_export_pdf\|Als PDF" src/school_test_engine/ui/pages/grades.py && echo "  ✓ grades.py Als-PDF button"
echo ""
echo "10. Migration:"
test -f src/school_test_engine/storage/migrations/010_phase14_keyboard_hints.sql && echo "  ✓ migration 010"
echo ""
echo "=== COMMIT CHAIN ==="
git log --oneline 0d1f323..HEAD
'
```

All checks should print ✓.

- [ ] **Step 3: Manual smoke (optional, not in CI)**

Launch the app and walk through:
```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && .venv/bin/python -m school_test_engine
```

1. Window-title should read „Learning Buddy".
2. Menu top-bar has Logomark + „Learning Buddy" wordmark in Fraunces.
3. Menu footer reads „designed by Matthias".
4. Run a Test → press Tab cycles through options, Space selects, → advances, M marks, O opens Übersicht, Esc returns to menu. Cheat-sheet visible at bottom.
5. Noten-Page: select a subject with multiple assessments → NOTENVERLAUF chart appears under Zeugnis-Hero.
6. History-Page: WOCHEN-ÜBERSICHT heatmap is shown above the existing table.
7. Library: each test card has a small „PDF" button → click → save dialog → PDF gets a worksheet + Lösungen page.
8. Menu ExamCard: „Lernplan PDF" button → produces a PDF with topics + mastery bars + recommendation.
9. Noten-Page „Als PDF": produces a multi-subject report with embedded charts.

- [ ] **Step 4: Mark Phase 14 complete**

After all checks pass, update the auto-memory `project_overview.md` to note Phase 14 done (add a `- Phase 14 (Learning Buddy)` entry; mention test count 276+; mention 4 tracks; reference spec/plan paths).

Mark TaskCreate #86 (Phase 14: Learning Buddy Polish) as completed.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Covered by |
|---|---|
| §5.1 Rebranding app.py | Task 2 |
| §5.1 Rebranding menu wordmark/footer | Task 3 |
| §5.1 Rebranding .desktop | Task 4 |
| §5.2 Keyboard module | Task 5 |
| §5.2 RunnerPage wiring + cheat-sheet + show_keyboard_hints | Tasks 1, 6 |
| §5.2 ReviewPage wiring | Task 7 |
| §5.3 GradeChart widget | Task 9 |
| §5.3 GradeHeatmap widget | Task 10 |
| §5.3 heatmap_data SQL | Task 8 |
| §5.3 Integrate chart on Noten | Task 11 |
| §5.3 Integrate heatmap on History | Task 12 |
| §5.4 PDF base helpers | Task 13 |
| §5.4 test_sheet + Library | Task 14 |
| §5.4 study_plan + ExamCard + EventEdit | Task 15 |
| §5.4 grade_report + Noten | Task 16 |
| §5.5 Tests | Tasks 1-2, 5, 8-10, 14-16 |
| §6 Acceptance | Task 17 |

No spec gaps.

**2. Placeholder scan:** All steps contain either full code, find/replace pairs, or specific commands. No TBD/TODO.

**3. Type consistency:**
- `install_runner_shortcuts(page, *, on_prev, on_next, on_mark, on_overview, on_abort)` — signature used consistently in Task 5 and Task 6.
- `GradeChart.set_data(schriftlich, muendlich)` — used in Task 9 and Task 11.
- `GradeHeatmap.set_data(weeks, rows)` — used in Task 10 and Task 12.
- `assessments_repo.heatmap_data(conn, user_id, weeks_back=8) -> dict[str, dict[date, float]]` — defined in Task 8, consumed in Task 12.
- `export_test_sheet(conn, test_id) -> str` (HTML), `export_study_plan(conn, event_id) -> str`, `export_grade_report(conn, user_id) -> str` — all return HTML; `render_to_pdf(html, path)` and `save_pdf_with_dialog(parent, html, default_filename)` consume HTML.
- `users.show_keyboard_hints` INTEGER NOT NULL DEFAULT 1 — used in migration (Task 1) and reload (Task 6).

All names consistent.

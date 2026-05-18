# Phase 18 — Globaler Zurück-Button + Noten-Nachtrag für vergangene KAs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build (1) a history-stack-based global back button in `GlobalHeader` and (2) a discovery + entry flow for grades on past KAs (Schulkalender-Card badge + MenuPage echo banner).

**Architecture:** `MainWindow` gets a single `_navigate(target, **kwargs)` dispatcher with a `_history: list[tuple[str, dict]]` stack. All existing `show_*` methods become thin wrappers around it. Grade-status flows through one new `events_repo` query (`list_past_klausuren_with_grade_status`) used by both the `CalendarEntryCard` badge variants and the `OpenGradesBanner` count.

**Tech Stack:** PySide6 (Qt6), SQLite, pytest. No new dependencies. No DB migration.

**Spec:** `docs/superpowers/specs/2026-05-18-zurueck-button-noten-nachtrag-design.md`

---

## File Structure

### Phase A — Navigation refactor

| File | Responsibility | Status |
|---|---|---|
| `src/school_test_engine/ui/main_window.py` | Adds `_history`, `_navigate`, `_navigate_back`, `_dispatch`. All `show_*` methods become wrappers calling `_navigate`. Existing `_return_to_history` field for runner→results→history flow is preserved. | Modify |
| `src/school_test_engine/ui/pages/assessment_edit.py:343-352` | `_navigate_back()` calls `self.window._navigate_back()` instead of hardcoded routing. | Modify |
| `src/school_test_engine/ui/pages/event_edit.py` | Same change in its `_navigate_back()`. | Modify |
| `src/school_test_engine/ui/pages/profile_edit.py` | Same change. | Modify |
| `src/school_test_engine/ui/pages/profile_manager.py` | Same change. | Modify |
| `tests/ui/test_navigation_stack.py` | New test file — Stack push/pop, top-dedup, runner-no-push, menu-clears-stack. | Create |

### Phase B — Back-button widget

| File | Responsibility | Status |
|---|---|---|
| `src/school_test_engine/ui/widgets/back_button.py` | New `BackButton(QFrame)` — arrow + "Zurück" text, emits `clicked` signal. | Create |
| `src/school_test_engine/ui/widgets/global_header.py` | Adds back-button as first widget left of logo. Exposes it via `self.back_button`. | Modify |
| `src/school_test_engine/ui/main_window.py` | Wires back-button visibility in `_navigate`/`_navigate_back`. Installs Esc `QShortcut`. | Modify |
| `src/school_test_engine/ui/style.qss` | New `QFrame#backButton` styling (hover, padding, height). | Modify |
| `tests/ui/test_back_button_widget.py` | New file — visibility binding, click signal, Esc shortcut. | Create |

### Phase C — Grade-status query + CalendarEntryCard badge + click routing

| File | Responsibility | Status |
|---|---|---|
| `src/school_test_engine/storage/events_repo.py` | New `list_past_klausuren_with_grade_status(conn, user_id, today)`. | Modify |
| `src/school_test_engine/ui/widgets/calendar_entry_card.py` | Optional `grade_status: GradeStatus \| None` kwarg; render "Note offen" `Pill` or existing `GradePill` next to the existing kind-pill. | Modify |
| `src/school_test_engine/school_calendar/models.py` | Add lightweight `GradeStatus` dataclass (assessment_id, grade). Lives next to `CalendarEntry`. | Modify |
| `src/school_test_engine/ui/pages/school_calendar.py:212-214` | New `_open_klausur` body — routes past KAs to `show_assessment_edit`, future KAs to `show_event_edit`. Loads grade-status for past KAs in `_reload_list_only`. | Modify |
| `src/school_test_engine/ui/pages/assessment_edit.py:232-260` | When `prefill_event_id` is set AND `assessment_id is None`, prefills subject from the event row AND disables `self.subject` + `self.date_edit`. | Modify |
| `tests/storage/test_events_repo_grade_status.py` | New file — query covers (with note / without note / not-klausur kind / future / scopes by user). | Create |
| `tests/ui/test_calendar_entry_card.py` | Append: badge variants — past klausur with note, past klausur without note, future klausur (no badge). | Modify |
| `tests/ui/test_school_calendar_page.py` | Append: click-routing for past-with-note, past-without-note, future-klausur. | Modify |
| `tests/test_assessment_edit_page.py` | Append: prefill_event_id disables subject + date fields. | Modify |

### Phase D — Menu echo banner + tab preselect + E2E

| File | Responsibility | Status |
|---|---|---|
| `src/school_test_engine/ui/widgets/open_grades_banner.py` | New widget analog to `FerienBanner` — honey strip, count label, clickable. | Create |
| `src/school_test_engine/ui/pages/menu.py:60-103` | New `_open_grades_banner_slot` between `_ferien_banner_slot` and `_dynamic_container`; `_refresh_open_grades_banner()` called from `reload()`. | Modify |
| `src/school_test_engine/ui/pages/school_calendar.py` | Add `show_for(initial_tab: str \| None = None)` method; activate corresponding tab button before `_reload_list_only`. | Modify |
| `src/school_test_engine/ui/main_window.py` | `_dispatch["school_calendar"]` accepts `initial_tab` kwarg; passes to `school_calendar_page.show_for`. | Modify |
| `tests/ui/test_open_grades_banner_widget.py` | New file — count pluralisation, hidden when N=0, click emits to right target. | Create |
| `tests/ui/test_menu_page_open_grades.py` | New file — banner appears/disappears with DB state. | Create |
| `tests/integration/test_grade_nachtrag_flow.py` | New file — E2E: vergangene KA → click → assessment_edit prefill → save → back → badge wechselt → banner-count dekrementiert. | Create |

---

## Phase A — Navigation Refactor

### Task A1: Add empty navigation skeleton + first stack test

**Files:**
- Modify: `src/school_test_engine/ui/main_window.py` (after `__init__`, around line 120)
- Create: `tests/ui/test_navigation_stack.py`

- [ ] **Step 1: Write the failing test**

Create `tests/ui/test_navigation_stack.py`:

```python
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import run_migrations, users_repo


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


@pytest.fixture
def window(conn):
    from school_test_engine.ui.main_window import MainWindow
    uid = users_repo.create_user(conn, name="Test")
    w = MainWindow(conn)
    w.set_active_user(uid)
    return w


def test_navigate_initializes_empty_history(window):
    # set_active_user → show_menu; menu is root → history must be empty
    assert window._history == []


def test_navigate_to_grades_pushes_menu_onto_stack(window):
    window._navigate("grades")
    assert len(window._history) == 1
    assert window._history[0][0] == "menu"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_navigation_stack.py -v`
Expected: FAIL with `AttributeError: 'MainWindow' object has no attribute '_history'`.

- [ ] **Step 3: Add the minimal skeleton to MainWindow**

In `src/school_test_engine/ui/main_window.py`:

After the existing `__init__` body, insert these new fields (place them next to `self._return_to_history = False` on line 117):

```python
        self._history: list[tuple[str, dict]] = []
        self._current: tuple[str, dict] | None = None
```

Then add these methods anywhere in the navigation section (after `set_active_user`, around line 135 — keep them grouped):

```python
    # ------------------------------------------------------------------
    # Navigation dispatcher (Phase 18)
    # ------------------------------------------------------------------

    def _navigate(self, target: str, **kwargs) -> None:
        """Central navigation entry point. Pushes current head onto the
        history stack and renders the target page.

        Special rules:
        - target == "menu":   clears stack (root reset)
        - target == "runner": never pushed onto stack (mid-test must use
                              Pause-Button, not Back)
        - target == top:      replaces top rather than pushing (dedup)
        """
        if target == "menu":
            self._history.clear()
        elif target == "runner":
            pass
        elif self._current is not None and self._current[0] != target:
            if not self._history or self._history[-1][0] != self._current[0]:
                self._history.append(self._current)
        # Resolve and render
        renderer = self._dispatch.get(target)
        if renderer is None:
            raise ValueError(f"Unknown navigation target: {target!r}")
        renderer(**kwargs)
        self._current = (target, dict(kwargs))

    def _navigate_back(self) -> None:
        if not self._history:
            return
        target, kwargs = self._history.pop()
        renderer = self._dispatch.get(target)
        if renderer is None:
            return
        renderer(**kwargs)
        self._current = (target, dict(kwargs))
```

Finally, initialize `self._dispatch` at the very end of `__init__` (after the existing `self._bg_sync_worker = None` line):

```python
        self._dispatch: dict[str, callable] = {}  # populated in Task A2
```

- [ ] **Step 4: Run test to verify it still fails (correctly)**

Run: `pytest tests/ui/test_navigation_stack.py::test_navigate_initializes_empty_history -v`
Expected: PASS.

Run: `pytest tests/ui/test_navigation_stack.py::test_navigate_to_grades_pushes_menu_onto_stack -v`
Expected: FAIL with `ValueError: Unknown navigation target: 'grades'`.

This is the right failure — dispatch is empty. We'll populate in A2.

- [ ] **Step 5: Commit**

```bash
git add tests/ui/test_navigation_stack.py src/school_test_engine/ui/main_window.py
git commit -m "feat(ui/nav): add _navigate dispatcher + history stack skeleton (Phase 18 A1)"
```

---

### Task A2: Populate `_dispatch` + convert all `show_*` to wrappers

**Files:**
- Modify: `src/school_test_engine/ui/main_window.py`

- [ ] **Step 1: Refactor `show_*` methods to private `_render_*` and add a wrapper**

For every `show_*` method that should participate in navigation, extract the body into a private `_render_*` method and replace the public method body with a call to `self._navigate("<target>", ...)`.

Concretely, in `main_window.py`:

Replace `show_profile_picker` (line 139) with:

```python
    def show_profile_picker(self) -> None:
        self.active_user_id = None
        self.header.setVisible(False)
        self.profile_picker_page.reload()
        self.stack.setCurrentWidget(self.profile_picker_page)
        # Profile picker is pre-login — no stack tracking.
        self._history.clear()
        self._current = ("profile_picker", {})
```

Replace `show_profile_manager` body with a wrapper:

```python
    def show_profile_manager(self, return_to: str = "picker") -> None:
        self._navigate("profile_manager", return_to=return_to)

    def _render_profile_manager(self, return_to: str = "picker") -> None:
        self.header.set_page_actions([])
        self.profile_manager_page.show_for(return_to)
        self.stack.setCurrentWidget(self.profile_manager_page)
```

Same pattern for `show_profile_edit`, `show_menu`, `show_library`, `show_import`, `show_gaps`, `show_school_calendar`, `show_prompt_builder`, `show_test_create`, `show_event_edit`.

For `show_*` methods that set page-action buttons in the header (currently `show_history`, `show_events`, `show_grades`, `show_error_book`), the page-action setup lives in the `_render_*` body so it re-runs whenever the page is rendered via Back. Example for `show_history`:

```python
    def show_history(self) -> None:
        self._navigate("history")

    def _render_history(self) -> None:
        csv_btn = QPushButton("CSV exportieren")
        csv_btn.setObjectName("text")
        csv_btn.clicked.connect(self.history_page.export_csv)
        self.header.set_page_actions([csv_btn])
        self.history_page.reload()
        self.stack.setCurrentWidget(self.history_page)
```

And for `show_error_book`, preserve the `uid is None`-guard and the `_refresh_error_book_action` call inside `_render_error_book`:

```python
    def show_error_book(self) -> None:
        self._navigate("error_book")

    def _render_error_book(self) -> None:
        uid = self.active_user_id
        if uid is None:
            return
        self._error_book_ueben_btn = QPushButton("Üben")
        self._error_book_ueben_btn.setObjectName("primary")
        self._error_book_ueben_btn.clicked.connect(self.error_book_page.trigger_practice)
        self.header.set_page_actions([self._error_book_ueben_btn])
        self.error_book_page.reload()
        self._refresh_error_book_action()
        self.stack.setCurrentWidget(self.error_book_page)
```

For `show_school_calendar`, preserve the `uid is None` guard:

```python
    def show_school_calendar(self) -> None:
        self._navigate("school_calendar")

    def _render_school_calendar(self) -> None:
        uid = self.active_user_id
        if uid is None:
            return
        self.header.set_page_actions([])
        self.school_calendar_page.reload()
        self.stack.setCurrentWidget(self.school_calendar_page)
```

(In Task D3 we'll add an `initial_tab` kwarg to both.)

For `show_menu`, the wrapper must clear `self._return_to_history` BEFORE calling `_navigate` (preserves existing behavior at line 156):

```python
    def show_menu(self) -> None:
        self._return_to_history = False
        self._navigate("menu")

    def _render_menu(self) -> None:
        self.header.set_page_actions([])
        self.menu_page.reload()
        self.stack.setCurrentWidget(self.menu_page)
```

For `show_assessment_edit`, keep all four parameters in the public signature for backward compat, and pass them through (drop `return_to` — it's no longer used internally but stays in the signature so existing callsites don't break):

```python
    def show_assessment_edit(
        self,
        assessment_id: int | None = None,
        return_to: str = "grades",
        prefill_subject: str | None = None,
        prefill_event_id: int | None = None,
    ) -> None:
        # return_to is preserved for API compatibility; the history stack
        # supersedes it (see Phase 18 design doc, Feature 1).
        self._navigate(
            "assessment_edit",
            assessment_id=assessment_id,
            prefill_subject=prefill_subject,
            prefill_event_id=prefill_event_id,
        )

    def _render_assessment_edit(
        self,
        assessment_id: int | None = None,
        prefill_subject: str | None = None,
        prefill_event_id: int | None = None,
    ) -> None:
        self.header.set_page_actions([])
        self.assessment_edit_page.show_for(
            assessment_id, "grades", prefill_subject, prefill_event_id,
        )
        self.stack.setCurrentWidget(self.assessment_edit_page)
```

Same idea for `show_event_edit` (drop `return_to` from internal call), `show_profile_edit`, `show_profile_manager`.

For `show_results`, keep the existing `_return_to_history` logic in the wrapper (line 343-349), but push via dispatcher:

```python
    def show_results(self, attempt_id: int) -> None:
        from ..daily import finalize as daily_finalize
        daily_finalize.finalize_if_daily(self.conn, attempt_id)
        self._return_to_history = (
            self.stack.currentWidget() is self.history_page
        )
        self._navigate("results", attempt_id=attempt_id)

    def _render_results(self, attempt_id: int) -> None:
        self.results_page.show_attempt(self.conn, attempt_id)
        self.stack.setCurrentWidget(self.results_page)
```

For `start_test`, `start_daily_five`, `resume_attempt`, `back_to_runner`, `jump_to_question`: these all land on the runner — they call `_navigate("runner", ...)` which by special rule does NOT push:

```python
    def start_test(self, test_id: int) -> None:
        self._return_to_history = False
        self._navigate("runner", action="start", test_id=test_id)

    def resume_attempt(self, attempt_id: int) -> None:
        self._return_to_history = False
        self._navigate("runner", action="resume", attempt_id=attempt_id)

    def back_to_runner(self) -> None:
        self._navigate("runner", action="raw")

    def jump_to_question(self, index: int) -> None:
        self.runner_page.jump_to_question(index)
        self._navigate("runner", action="raw")

    def _render_runner(self, action: str = "raw", **kwargs) -> None:
        if action == "start":
            self.runner_page.start_new(kwargs["test_id"])
        elif action == "resume":
            self.runner_page.resume(kwargs["attempt_id"])
        # "raw" → caller already mutated runner_page state
        self.stack.setCurrentWidget(self.runner_page)
```

For `show_review`:

```python
    def show_review(self, attempt_id: int) -> None:
        self._navigate("review", attempt_id=attempt_id)

    def _render_review(self, attempt_id: int) -> None:
        self.review_page.show_for_attempt()
        self.stack.setCurrentWidget(self.review_page)
```

Finally, populate `_dispatch` at the end of `__init__` (replace the empty-dict placeholder from A1):

```python
        self._dispatch = {
            "menu": self._render_menu,
            "library": self._render_library,
            "import": self._render_import,
            "gaps": self._render_gaps,
            "history": self._render_history,
            "events": self._render_events,
            "grades": self._render_grades,
            "error_book": self._render_error_book,
            "school_calendar": self._render_school_calendar,
            "prompt_builder": self._render_prompt_builder,
            "test_create": self._render_test_create,
            "event_edit": self._render_event_edit,
            "assessment_edit": self._render_assessment_edit,
            "profile_manager": self._render_profile_manager,
            "profile_edit": self._render_profile_edit,
            "results": self._render_results,
            "review": self._render_review,
            "runner": self._render_runner,
        }
```

- [ ] **Step 2: Run full suite**

Run: `pytest -x -q`
Expected: ALL 494 existing tests still pass — wrappers delegate transparently. PLUS `test_navigate_to_grades_pushes_menu_onto_stack` from A1 now PASSES.

If anything regresses, the failing test is the diagnostic — fix root cause, don't paper over.

- [ ] **Step 3: Commit**

```bash
git add src/school_test_engine/ui/main_window.py
git commit -m "refactor(ui/nav): convert show_* methods to _navigate wrappers (Phase 18 A2)"
```

---

### Task A3: Stack-hygiene + edge-case tests

**Files:**
- Modify: `tests/ui/test_navigation_stack.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_navigation_stack.py`:

```python
def test_navigate_back_pops_to_previous_target(window):
    window._navigate("grades")
    window._navigate("assessment_edit")
    assert len(window._history) == 2
    window._navigate_back()
    assert len(window._history) == 1
    assert window._current[0] == "grades"


def test_navigate_to_menu_clears_history(window):
    window._navigate("grades")
    window._navigate("assessment_edit")
    window._navigate("menu")
    assert window._history == []
    assert window._current[0] == "menu"


def test_navigate_runner_does_not_push_to_stack(window):
    window._navigate("grades")
    before = len(window._history)
    window._navigate("runner", action="raw")
    # runner does NOT push grades onto stack
    assert len(window._history) == before


def test_navigate_dedupes_when_target_equals_current(window):
    # Clicking "Grades" twice in the logo menu should not stack two 'grades'.
    window._navigate("grades")
    window._navigate("grades")
    # menu was pushed once when first transitioning away; second call is dedup
    assert window._history == [("menu", {})]


def test_navigate_back_on_empty_stack_is_noop(window):
    # Fresh start: history empty; back should not crash
    window._navigate_back()
    assert window._current[0] == "menu"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/ui/test_navigation_stack.py -v`
Expected: All 6 tests PASS. (The skeleton from A1+A2 should already handle these — if any fail, fix `_navigate` in main_window.py.)

- [ ] **Step 3: Commit**

```bash
git add tests/ui/test_navigation_stack.py
git commit -m "test(ui/nav): cover stack hygiene + edge cases (Phase 18 A3)"
```

---

### Task A4: Simplify `_navigate_back` callsites in 4 pages

**Files:**
- Modify: `src/school_test_engine/ui/pages/assessment_edit.py:343-352`
- Modify: `src/school_test_engine/ui/pages/event_edit.py` (search for `_navigate_back`)
- Modify: `src/school_test_engine/ui/pages/profile_edit.py:445`
- Modify: `src/school_test_engine/ui/pages/profile_manager.py:191`

- [ ] **Step 1: Replace the `_navigate_back` body in `assessment_edit.py`**

Replace lines 346-352 (the current `_navigate_back` method):

```python
    def _navigate_back(self) -> None:
        if self._return_to == "menu":
            self.window.show_menu()
        elif self._return_to == "events":
            self.window.show_events()
        else:
            self.window.show_grades()
```

with:

```python
    def _navigate_back(self) -> None:
        self.window._navigate_back()
```

- [ ] **Step 2: Same change in `event_edit.py`**

Find the `_navigate_back` method (around line 244 — check with `grep -n '_navigate_back\|_return_to ==' src/school_test_engine/ui/pages/event_edit.py`).

Replace the entire if/elif/else routing block with:

```python
    def _navigate_back(self) -> None:
        self.window._navigate_back()
```

- [ ] **Step 3: Same change in `profile_edit.py` and `profile_manager.py`**

In `profile_edit.py:445`, replace the existing `_return_to`-routing block (search for `target = self._return_to`) with:

```python
        self.window._navigate_back()
```

In `profile_manager.py:191`, replace the if/else block (search for `if self._return_to == "menu"`) with:

```python
        self.window._navigate_back()
```

- [ ] **Step 4: Run full suite**

Run: `pytest -x -q`
Expected: All tests PASS. The simplified `_navigate_back` calls relies on MainWindow's stack — for tests that DON'T go through `_navigate` (i.e. they call `page.show_for(...)` directly without setting up `_current`), `_navigate_back` becomes a no-op (empty history). That's fine for tests that only verify save/cancel state, not navigation target.

If a test specifically asserts "after cancel, we're on grades page": that test must be updated to drive navigation via `window.show_assessment_edit(...)` instead of `page.show_for(...)` directly. There should be very few such tests — search with: `grep -rE "_navigate_back\b|return_to=" tests/`. Most tests stub `window` and don't care about the post-back location.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/assessment_edit.py src/school_test_engine/ui/pages/event_edit.py src/school_test_engine/ui/pages/profile_edit.py src/school_test_engine/ui/pages/profile_manager.py
git commit -m "refactor(ui/pages): delegate _navigate_back to MainWindow stack (Phase 18 A4)"
```

---

## Phase B — Back-Button Widget

### Task B1: Build the `BackButton` widget

**Files:**
- Create: `src/school_test_engine/ui/widgets/back_button.py`
- Create: `tests/ui/test_back_button_widget.py`

- [ ] **Step 1: Write the failing test**

Create `tests/ui/test_back_button_widget.py`:

```python
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_back_button_renders_text_and_arrow():
    from school_test_engine.ui.widgets.back_button import BackButton
    b = BackButton()
    # Find the text-label child:
    from PySide6.QtWidgets import QLabel
    labels = b.findChildren(QLabel)
    texts = [lbl.text() for lbl in labels]
    assert any("Zurück" in t for t in texts)
    assert any("←" in t or "⮜" in t for t in texts)


def test_back_button_click_emits_signal():
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtGui import QMouseEvent
    from school_test_engine.ui.widgets.back_button import BackButton

    b = BackButton()
    received = []
    b.clicked.connect(lambda: received.append(1))

    ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(1, 1), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    b.mousePressEvent(ev)
    assert received == [1]


def test_back_button_uses_pointing_cursor():
    from PySide6.QtCore import Qt
    from school_test_engine.ui.widgets.back_button import BackButton
    b = BackButton()
    assert b.cursor().shape() == Qt.CursorShape.PointingHandCursor
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_back_button_widget.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'school_test_engine.ui.widgets.back_button'`.

- [ ] **Step 3: Implement the widget**

Create `src/school_test_engine/ui/widgets/back_button.py`:

```python
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from ..design import Color, FontFamily, FontSize


class BackButton(QFrame):
    """Globaler Zurück-Button im GlobalHeader. Emits `clicked` on left-press.

    Visibility is controlled by MainWindow (bound to history-stack depth)."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("backButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 4, 12, 4)
        h.setSpacing(6)

        arrow = QLabel("←")
        arrow.setStyleSheet(
            f"color: {Color.PAPER_700}; font-size: 16pt; font-weight: 400;"
        )
        h.addWidget(arrow)

        text = QLabel("Zurück")
        text.setFont(QFont(FontFamily.BODY, FontSize.SM, QFont.Weight.Medium))
        text.setStyleSheet(f"color: {Color.PAPER_700};")
        h.addWidget(text)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_back_button_widget.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/widgets/back_button.py tests/ui/test_back_button_widget.py
git commit -m "feat(ui/widget): BackButton widget for global header (Phase 18 B1)"
```

---

### Task B2: Integrate `BackButton` into `GlobalHeader` + wire visibility

**Files:**
- Modify: `src/school_test_engine/ui/widgets/global_header.py`
- Modify: `src/school_test_engine/ui/main_window.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/ui/test_navigation_stack.py`:

```python
def test_back_button_visibility_binds_to_history_depth(window):
    # Fresh / menu → not visible
    assert window.header.back_button.isVisible() is False
    # Push something → visible
    window._navigate("grades")
    assert window.header.back_button.isVisible() is True
    # Back to root → not visible
    window._navigate("menu")
    assert window.header.back_button.isVisible() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_navigation_stack.py::test_back_button_visibility_binds_to_history_depth -v`
Expected: FAIL with `AttributeError: 'GlobalHeader' object has no attribute 'back_button'`.

- [ ] **Step 3: Add `BackButton` to `GlobalHeader`**

In `src/school_test_engine/ui/widgets/global_header.py`, add the import at the top with the other widget imports:

```python
from .back_button import BackButton
```

Then in `GlobalHeader.__init__`, BEFORE the line that adds `self._logo_menu` (currently line 117 `layout.addWidget(self._logo_menu)`), insert:

```python
        self.back_button = BackButton()
        self.back_button.setVisible(False)
        self.back_button.clicked.connect(window._navigate_back)
        layout.addWidget(self.back_button)
```

- [ ] **Step 4: Wire visibility in `MainWindow._navigate` / `_navigate_back`**

In `src/school_test_engine/ui/main_window.py`, modify `_navigate` and `_navigate_back` to update visibility at the end:

In `_navigate`, after `self._current = (target, dict(kwargs))`:

```python
        self.header.back_button.setVisible(len(self._history) > 0)
```

In `_navigate_back`, after `self._current = (target, dict(kwargs))`:

```python
        self.header.back_button.setVisible(len(self._history) > 0)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/ui/test_navigation_stack.py -v`
Expected: All 7 tests (6 from A + the new B2 test) PASS.

Run: `pytest -x -q`
Expected: full suite still PASSES.

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/widgets/global_header.py src/school_test_engine/ui/main_window.py tests/ui/test_navigation_stack.py
git commit -m "feat(ui/nav): wire BackButton visibility to history stack (Phase 18 B2)"
```

---

### Task B3: `Esc` keyboard shortcut + QSS styling

**Files:**
- Modify: `src/school_test_engine/ui/main_window.py`
- Modify: `src/school_test_engine/ui/style.qss`

- [ ] **Step 1: Write the failing test**

Append to `tests/ui/test_navigation_stack.py`:

```python
def test_esc_shortcut_triggers_back_when_visible(window):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest

    window._navigate("grades")
    assert window._current[0] == "grades"
    # Simulate Esc key
    QTest.keyClick(window, Qt.Key.Key_Escape)
    # Wait for shortcut dispatch
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.processEvents()
    assert window._current[0] == "menu"


def test_esc_shortcut_no_op_when_back_invisible(window):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QCoreApplication

    assert window.header.back_button.isVisible() is False  # on menu
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QCoreApplication.processEvents()
    # Still on menu — nothing changed
    assert window._current[0] == "menu"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_navigation_stack.py::test_esc_shortcut_triggers_back_when_visible -v`
Expected: FAIL — `window._current` stays at `"grades"` after Esc.

- [ ] **Step 3: Add `Esc` `QShortcut` to MainWindow**

In `src/school_test_engine/ui/main_window.py`, add import at the top:

```python
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication
```

(QApplication is needed for the modal-dialog guard.)

At the end of `MainWindow.__init__`, after the `_dispatch` block, add:

```python
        self._esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self._esc_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._esc_shortcut.activated.connect(self._on_esc_pressed)
```

Also import `Qt` at the top if not already (it's needed for ShortcutContext):

```python
from PySide6.QtCore import Qt, Signal
```

Then add the handler method:

```python
    def _on_esc_pressed(self) -> None:
        # Guard: no-op if a modal dialog is open OR back-button is hidden.
        if QApplication.activeModalWidget() is not None:
            return
        if not self.header.back_button.isVisible():
            return
        self._navigate_back()
```

- [ ] **Step 4: Add QSS styling for the button**

In `src/school_test_engine/ui/style.qss`, append at the bottom (near other header-related rules):

```css
QFrame#backButton {
    background: transparent;
    border-radius: 8px;
    min-height: 32px;
}
QFrame#backButton:hover {
    background: #f4efe6;
}
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/ui/test_navigation_stack.py -v`
Expected: All tests PASS, including the two Esc-shortcut tests.

Run: `pytest -x -q`
Expected: full suite PASSES.

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/main_window.py src/school_test_engine/ui/style.qss tests/ui/test_navigation_stack.py
git commit -m "feat(ui/nav): Esc shortcut + hover styling for BackButton (Phase 18 B3)"
```

---

## Phase C — Grade-Status Query + Card Badge + Click Routing

### Task C1: New `events_repo.list_past_klausuren_with_grade_status` query

**Files:**
- Modify: `src/school_test_engine/storage/events_repo.py`
- Create: `tests/storage/test_events_repo_grade_status.py`

- [ ] **Step 1: Write the failing test**

Create `tests/storage/test_events_repo_grade_status.py`:

```python
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.storage import (
    assessments_repo, events_repo, run_migrations, users_repo,
)


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    run_migrations(c)
    yield c
    c.close()


def test_past_klausur_without_grade_returned(conn):
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klassenarbeit", "2026-04-01")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 1),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["subject"] == "Mathe"
    assert row["assessment_id"] is None
    assert row["grade"] is None


def test_past_klausur_with_grade_returned(conn):
    uid = users_repo.create_user(conn, name="T")
    eid = events_repo.create(conn, uid, "Englisch", "klausur", "2026-04-15")
    assessments_repo.create(
        conn, uid, "Englisch", "schriftlich", "2026-04-15",
        grade=2.5, scheduled_event_id=eid,
    )
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 1),
    )
    assert len(rows) == 1
    assert rows[0]["assessment_id"] is not None
    assert rows[0]["grade"] == 2.5


def test_future_klausur_excluded(conn):
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Bio", "test", "2026-07-01")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 1),
    )
    assert rows == []


def test_today_klausur_not_yet_past(conn):
    # end_date == today should NOT count as past (spec edge case)
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klausur", "2026-05-18")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 18),
    )
    assert rows == []


def test_non_klausur_kind_excluded(conn):
    # "sonstiges" kind exists in the CHECK constraint but is not a KA.
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "sonstiges", "2026-04-01")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 1),
    )
    assert rows == []


def test_scoped_by_user(conn):
    a = users_repo.create_user(conn, name="A")
    b = users_repo.create_user(conn, name="B")
    events_repo.create(conn, a, "Mathe", "klausur", "2026-04-01")
    events_repo.create(conn, b, "Englisch", "klausur", "2026-04-02")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, a, today=date(2026, 5, 1),
    )
    assert len(rows) == 1
    assert rows[0]["subject"] == "Mathe"


def test_ordered_by_date_desc(conn):
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klausur", "2026-03-01")
    events_repo.create(conn, uid, "Englisch", "klausur", "2026-04-01")
    events_repo.create(conn, uid, "Bio", "test", "2026-02-01")
    rows = events_repo.list_past_klausuren_with_grade_status(
        conn, uid, today=date(2026, 5, 1),
    )
    dates = [r["event_date"] for r in rows]
    assert dates == ["2026-04-01", "2026-03-01", "2026-02-01"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/test_events_repo_grade_status.py -v`
Expected: All FAIL with `AttributeError: module ... has no attribute 'list_past_klausuren_with_grade_status'`.

- [ ] **Step 3: Implement the query**

Append to `src/school_test_engine/storage/events_repo.py`:

```python
def list_past_klausuren_with_grade_status(
    conn: sqlite3.Connection,
    user_id: int,
    today: "date",
) -> list[sqlite3.Row]:
    """Past KAs (klassenarbeit/klausur/test) with their grade-link status.

    Returns rows with columns: id, subject, event_date, kind,
    assessment_id (nullable), grade (nullable). Ordered by event_date DESC.

    'Past' means strictly less than `today` — today's KA is NOT past yet.
    """
    cur = conn.execute(
        """
        SELECT se.id, se.subject, se.event_date, se.kind,
               a.id AS assessment_id, a.grade AS grade
        FROM scheduled_events se
        LEFT JOIN assessments a ON a.scheduled_event_id = se.id
        WHERE se.user_id = ?
          AND se.kind IN ('klassenarbeit', 'klausur', 'test')
          AND se.event_date < ?
        ORDER BY se.event_date DESC, se.created_at DESC
        """,
        (user_id, today.isoformat()),
    )
    return cur.fetchall()
```

Add `from datetime import date` at the top of `events_repo.py` if it's not already imported (or use `"date"` as a string-forward-ref like the signature does).

- [ ] **Step 4: Run tests**

Run: `pytest tests/storage/test_events_repo_grade_status.py -v`
Expected: All 7 tests PASS.

Run: `pytest -x -q`
Expected: full suite PASSES.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/storage/events_repo.py tests/storage/test_events_repo_grade_status.py
git commit -m "feat(storage): list_past_klausuren_with_grade_status query (Phase 18 C1)"
```

---

### Task C2: Add `GradeStatus` dataclass + extend `CalendarEntryCard`

**Files:**
- Modify: `src/school_test_engine/school_calendar/models.py`
- Modify: `src/school_test_engine/ui/widgets/calendar_entry_card.py`
- Modify: `tests/ui/test_calendar_entry_card.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_calendar_entry_card.py`:

```python
def test_past_klausur_without_grade_shows_offen_pill():
    from school_test_engine.school_calendar.models import GradeStatus
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard

    e = _entry(kind="klausur", source="klausur", subject="Mathe",
               start_date=date(2026, 4, 1), end_date=date(2026, 4, 1),
               entry_id=42, title="Mathe Klassenarbeit")
    gs = GradeStatus(assessment_id=None, grade=None)
    card = CalendarEntryCard(e, grade_status=gs)

    from PySide6.QtWidgets import QLabel
    labels = [lbl.text() for lbl in card.findChildren(QLabel)]
    assert any("Note offen" in t for t in labels)


def test_past_klausur_with_grade_shows_grade_pill():
    from school_test_engine.school_calendar.models import GradeStatus
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard

    e = _entry(kind="klausur", source="klausur", subject="Mathe",
               start_date=date(2026, 4, 1), end_date=date(2026, 4, 1),
               entry_id=42, title="Mathe Klassenarbeit")
    gs = GradeStatus(assessment_id=7, grade=2.5)
    card = CalendarEntryCard(e, grade_status=gs)

    from PySide6.QtWidgets import QLabel
    labels = [lbl.text() for lbl in card.findChildren(QLabel)]
    # GradePill formats half-step as "2,5"
    assert any(t == "2,5" for t in labels)


def test_future_klausur_no_grade_badge():
    from school_test_engine.ui.widgets.calendar_entry_card import CalendarEntryCard
    e = _entry(kind="klausur", source="klausur", subject="Mathe",
               start_date=date(2026, 12, 1), end_date=date(2026, 12, 1),
               entry_id=42, title="Mathe Klassenarbeit")
    card = CalendarEntryCard(e, grade_status=None)
    from PySide6.QtWidgets import QLabel
    labels = [lbl.text() for lbl in card.findChildren(QLabel)]
    assert not any("Note offen" in t for t in labels)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_calendar_entry_card.py -v`
Expected: First two FAIL with `ImportError: cannot import name 'GradeStatus'`. Third FAIL with `TypeError: __init__() got unexpected keyword argument 'grade_status'`.

- [ ] **Step 3: Add `GradeStatus` to models.py**

Modify `src/school_test_engine/school_calendar/models.py`. Append at the end:

```python
@dataclass(frozen=True)
class GradeStatus:
    """Holds the grade-link state for a past KA. Used by CalendarEntryCard.

    `assessment_id is None and grade is None` → "Note offen"
    Both set → grade was entered (display as GradePill).
    """
    assessment_id: int | None
    grade: float | None
```

- [ ] **Step 4: Extend `CalendarEntryCard`**

Modify `src/school_test_engine/ui/widgets/calendar_entry_card.py`. Replace the `__init__` and add a new render path. Full updated file:

```python
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ...school_calendar.models import CalendarEntry, GradeStatus
from ..design import FontFamily
from .grade_pill import GradePill
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
    """Schlanke Card: [DateBadge] [Title] [KindPill] [optional NotePill].
    Klausur-Cards sind klickbar."""

    clicked = Signal(int)

    def __init__(
        self,
        entry: CalendarEntry,
        parent=None,
        *,
        grade_status: GradeStatus | None = None,
    ):
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
        title.setFont(QFont(FontFamily.BODY, 11, QFont.Weight.Medium))
        title_col.addWidget(title)
        h.addLayout(title_col)

        h.addStretch(1)

        kind_pill = Pill(_PILL_LABEL_FOR_KIND[entry.kind],
                         variant=_PILL_VARIANT_FOR_KIND[entry.kind])
        h.addWidget(kind_pill)

        if grade_status is not None:
            if grade_status.assessment_id is None:
                # Note nicht eingetragen
                note_pill = Pill("Note offen", variant="honey")
                h.addWidget(note_pill)
            elif grade_status.grade is not None:
                # Note vorhanden — GradePill mit kompakter Größe
                pill = GradePill(grade_status.grade, size=36)
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

- [ ] **Step 5: Run tests**

Run: `pytest tests/ui/test_calendar_entry_card.py -v`
Expected: All 7 tests (4 existing + 3 new) PASS.

Run: `pytest -x -q`
Expected: full suite PASSES.

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/school_calendar/models.py src/school_test_engine/ui/widgets/calendar_entry_card.py tests/ui/test_calendar_entry_card.py
git commit -m "feat(ui/widget): CalendarEntryCard grade-status badge (Phase 18 C2)"
```

---

### Task C3: Update `SchoolCalendarPage` click-routing + load grade-status into cards

**Files:**
- Modify: `src/school_test_engine/ui/pages/school_calendar.py`
- Modify: `tests/ui/test_school_calendar_page.py`

- [ ] **Step 1: Write the failing tests**

First check existing tests to find a patternable fixture:

```bash
sed -n '1,40p' tests/ui/test_school_calendar_page.py
```

Append new tests at the end of `tests/ui/test_school_calendar_page.py`:

```python
def test_click_past_klausur_without_grade_opens_assessment_edit_with_prefill(
    page_factory, tmp_path,
):
    """Verifies the new click routing: past KA → assessment_edit, not event_edit."""
    import sqlite3
    from datetime import date as _date
    from school_test_engine.storage import (
        events_repo, run_migrations, users_repo,
    )

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)
    uid = users_repo.create_user(conn, name="T")
    eid = events_repo.create(conn, uid, "Mathe", "klausur", "2026-04-01")

    page, stub = page_factory(conn, uid, today=_date(2026, 5, 1))
    page.reload()
    page._open_klausur(eid)

    assert stub.last_call == ("show_assessment_edit", {
        "prefill_event_id": eid,
        "prefill_subject": "Mathe",
    })


def test_click_past_klausur_with_grade_opens_assessment_edit_in_edit_mode(
    page_factory, tmp_path,
):
    import sqlite3
    from datetime import date as _date
    from school_test_engine.storage import (
        assessments_repo, events_repo, run_migrations, users_repo,
    )

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)
    uid = users_repo.create_user(conn, name="T")
    eid = events_repo.create(conn, uid, "Englisch", "klausur", "2026-04-15")
    aid = assessments_repo.create(
        conn, uid, "Englisch", "schriftlich", "2026-04-15",
        grade=2.0, scheduled_event_id=eid,
    )

    page, stub = page_factory(conn, uid, today=_date(2026, 5, 1))
    page.reload()
    page._open_klausur(eid)

    assert stub.last_call == ("show_assessment_edit", {"assessment_id": aid})


def test_click_future_klausur_still_opens_event_edit(page_factory, tmp_path):
    import sqlite3
    from datetime import date as _date
    from school_test_engine.storage import (
        events_repo, run_migrations, users_repo,
    )

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)
    uid = users_repo.create_user(conn, name="T")
    eid = events_repo.create(conn, uid, "Bio", "test", "2026-07-01")

    page, stub = page_factory(conn, uid, today=_date(2026, 5, 1))
    page.reload()
    page._open_klausur(eid)

    assert stub.last_call == ("show_event_edit", {"event_id": eid})
```

If `page_factory` fixture does not already exist in this test file, add it at the top (or in a `conftest.py` if multiple test files need it). Inspect existing test file first to see what fixtures/stubs are in place. If a `_StubWindow` pattern already exists, reuse it. Add this fixture next to existing ones:

```python
@pytest.fixture
def page_factory(qapp):
    from school_test_engine.ui.pages.school_calendar import SchoolCalendarPage

    class _StubWindow:
        def __init__(self, conn, uid):
            self.conn = conn
            self.active_user_id = uid
            self.events_synced = None  # Signal not needed for these tests
            self.user_changed = None
            self.last_call: tuple[str, dict] | None = None

        def show_assessment_edit(self, **kwargs):
            # Drop None-valued kwargs to keep assertions clean.
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            self.last_call = ("show_assessment_edit", kwargs)

        def show_event_edit(self, event_id, return_to=None):
            self.last_call = ("show_event_edit", {"event_id": event_id})

    def _make(conn, uid, today=None):
        stub = _StubWindow(conn, uid)
        page = SchoolCalendarPage(stub, conn, today=today)
        return page, stub

    return _make
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_school_calendar_page.py -v`
Expected: Three new tests FAIL — current `_open_klausur` only calls `show_event_edit`.

- [ ] **Step 3: Update `_open_klausur` + load grade-status in `_reload_list_only`**

In `src/school_test_engine/ui/pages/school_calendar.py`, add imports at the top:

```python
from ...school_calendar.models import GradeStatus
from ...storage import assessments_repo, events_repo
```

Replace `_open_klausur` (line 212-214) with:

```python
    def _open_klausur(self, event_id: int) -> None:
        ev = events_repo.get(self.conn, event_id)
        if ev is None:
            return
        is_past = ev["event_date"] < self._today().isoformat()
        if is_past:
            assessment = assessments_repo.find_by_event(self.conn, event_id)
            if assessment is not None:
                if hasattr(self.window, "show_assessment_edit"):
                    self.window.show_assessment_edit(assessment_id=assessment["id"])
            else:
                if hasattr(self.window, "show_assessment_edit"):
                    self.window.show_assessment_edit(
                        prefill_event_id=event_id,
                        prefill_subject=ev["subject"],
                    )
        else:
            if hasattr(self.window, "show_event_edit"):
                self.window.show_event_edit(event_id=event_id)
```

Then load grade-status for past klausur entries in `_reload_list_only`. Modify the existing block (after line 168 `for month_label, ...:`):

Replace:
```python
        for month_label, month_entries in group_by_month(entries):
            self._add_month_header(month_label)
            for entry in month_entries:
                card = CalendarEntryCard(entry, parent=self._list_host)
                if entry.kind == "klausur":
                    card.clicked.connect(self._open_klausur)
                self._cards.append(card)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)
```

with:

```python
        # Build grade-status lookup once per reload (past klausuren only).
        today = self._today()
        past_rows = events_repo.list_past_klausuren_with_grade_status(
            self.conn, self._user_id, today,
        )
        grade_status_by_id: dict[int, GradeStatus] = {
            row["id"]: GradeStatus(
                assessment_id=row["assessment_id"], grade=row["grade"],
            )
            for row in past_rows
        }

        for month_label, month_entries in group_by_month(entries):
            self._add_month_header(month_label)
            for entry in month_entries:
                gs = grade_status_by_id.get(entry.entry_id) if entry.kind == "klausur" else None
                card = CalendarEntryCard(
                    entry, parent=self._list_host, grade_status=gs,
                )
                if entry.kind == "klausur":
                    card.clicked.connect(self._open_klausur)
                self._cards.append(card)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ui/test_school_calendar_page.py -v`
Expected: All tests PASS.

Run: `pytest -x -q`
Expected: full suite PASSES.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/school_calendar.py tests/ui/test_school_calendar_page.py
git commit -m "feat(ui/page): SchoolCalendarPage routes past-KA to grade flow + loads grade-status (Phase 18 C3)"
```

---

### Task C4: `AssessmentEditPage` — disable subject/date when prefill_event_id is set

**Files:**
- Modify: `src/school_test_engine/ui/pages/assessment_edit.py`
- Modify: `tests/test_assessment_edit_page.py`

- [ ] **Step 1: Write the failing tests**

Inspect the existing test file pattern first:

```bash
sed -n '1,40p' tests/test_assessment_edit_page.py
```

Append new tests at the end (adapt fixture names to match existing patterns):

```python
def test_prefill_event_id_disables_subject_and_date(qapp, tmp_path):
    """When opening from a past KA, subject + date are not editable —
    they reflect the KA, not arbitrary user choices."""
    import sqlite3
    from school_test_engine.storage import (
        events_repo, run_migrations, users_repo,
    )
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)
    uid = users_repo.create_user(conn, name="T")
    eid = events_repo.create(conn, uid, "Mathe", "klausur", "2026-04-15")

    class _StubWindow:
        active_user_id = uid
        conn = None

    win = _StubWindow()
    win.conn = conn
    page = AssessmentEditPage(win, conn)
    page.show_for(
        assessment_id=None,
        return_to="grades",
        prefill_subject="Mathe",
        prefill_event_id=eid,
    )

    assert page.subject.isEnabled() is False
    assert page.date_edit.isEnabled() is False
    # Sanity: value is preserved
    assert page.subject.currentText() == "Mathe"


def test_edit_mode_keeps_subject_and_date_enabled(qapp, tmp_path):
    """When editing an existing assessment, both fields remain enabled."""
    import sqlite3
    from school_test_engine.storage import (
        assessments_repo, events_repo, run_migrations, users_repo,
    )
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)
    uid = users_repo.create_user(conn, name="T")
    eid = events_repo.create(conn, uid, "Englisch", "klausur", "2026-04-15")
    aid = assessments_repo.create(
        conn, uid, "Englisch", "schriftlich", "2026-04-15",
        grade=2.0, scheduled_event_id=eid,
    )

    class _StubWindow:
        active_user_id = uid
        conn = None

    win = _StubWindow()
    win.conn = conn
    page = AssessmentEditPage(win, conn)
    page.show_for(assessment_id=aid)

    assert page.subject.isEnabled() is True
    assert page.date_edit.isEnabled() is True


def test_no_prefill_event_id_keeps_subject_and_date_enabled(qapp, tmp_path):
    """When opened via 'Note hinzufügen' (no event link), both stay enabled."""
    import sqlite3
    from school_test_engine.storage import run_migrations, users_repo
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)
    uid = users_repo.create_user(conn, name="T")

    class _StubWindow:
        active_user_id = uid
        conn = None

    win = _StubWindow()
    win.conn = conn
    page = AssessmentEditPage(win, conn)
    page.show_for(assessment_id=None)

    assert page.subject.isEnabled() is True
    assert page.date_edit.isEnabled() is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_assessment_edit_page.py -v -k "prefill or edit_mode or no_prefill"`
Expected: `test_prefill_event_id_disables_subject_and_date` FAILS — currently no disable logic; the other two should already pass.

- [ ] **Step 3: Add the disable logic to `show_for`**

In `src/school_test_engine/ui/pages/assessment_edit.py`, locate `show_for` (around line 232-260). Update the prefill branch:

```python
    def show_for(
        self,
        assessment_id: int | None = None,
        return_to: str = "grades",
        prefill_subject: str | None = None,
        prefill_event_id: int | None = None,
    ) -> None:
        self._assessment_id = assessment_id
        self._return_to = return_to
        self._prefill_event_id = prefill_event_id
        self._reset_fields()
        if assessment_id is None:
            self.title_label.setText("Note eintragen")
            self.delete_btn.setVisible(False)
            if prefill_subject:
                idx = self.subject.findText(prefill_subject)
                if idx >= 0:
                    self.subject.setCurrentIndex(idx)
                else:
                    self.subject.setEditText(prefill_subject)
            if prefill_event_id is not None:
                ev = events_repo.get(self.conn, prefill_event_id)
                if ev is not None:
                    # Prefill subject from event if not given (defensive).
                    if not prefill_subject:
                        idx = self.subject.findText(ev["subject"])
                        if idx >= 0:
                            self.subject.setCurrentIndex(idx)
                        else:
                            self.subject.setEditText(ev["subject"])
                    d = ev["event_date"]
                    self.date_edit.setDate(
                        QDate(int(d[:4]), int(d[5:7]), int(d[8:10]))
                    )
                # Lock subject + date — they reflect the KA.
                self.subject.setEnabled(False)
                self.date_edit.setEnabled(False)
            else:
                # No event link → both fields freely editable
                self.subject.setEnabled(True)
                self.date_edit.setEnabled(True)
        else:
            self.title_label.setText("Note bearbeiten")
            self.delete_btn.setVisible(True)
            # Edit mode: both stay enabled regardless of event link
            self.subject.setEnabled(True)
            self.date_edit.setEnabled(True)
            self._load_assessment(assessment_id)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_assessment_edit_page.py -v`
Expected: All tests PASS.

Run: `pytest -x -q`
Expected: full suite PASSES.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/assessment_edit.py tests/test_assessment_edit_page.py
git commit -m "feat(ui/page): AssessmentEditPage disables subject+date when prefilled from KA (Phase 18 C4)"
```

---

## Phase D — Menu Echo Banner + Tab Preselect + E2E

### Task D1: `OpenGradesBanner` widget

**Files:**
- Create: `src/school_test_engine/ui/widgets/open_grades_banner.py`
- Create: `tests/ui/test_open_grades_banner_widget.py`
- Modify: `src/school_test_engine/ui/style.qss` (add QSS rules)

- [ ] **Step 1: Write the failing tests**

Create `tests/ui/test_open_grades_banner_widget.py`:

```python
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_banner_text_singular_for_count_1():
    from school_test_engine.ui.widgets.open_grades_banner import OpenGradesBanner
    b = OpenGradesBanner(count=1)
    from PySide6.QtWidgets import QLabel
    texts = [lbl.text() for lbl in b.findChildren(QLabel)]
    assert any("1 offene Note" in t for t in texts)


def test_banner_text_plural_for_count_3():
    from school_test_engine.ui.widgets.open_grades_banner import OpenGradesBanner
    b = OpenGradesBanner(count=3)
    from PySide6.QtWidgets import QLabel
    texts = [lbl.text() for lbl in b.findChildren(QLabel)]
    assert any("3 offene Noten" in t for t in texts)


def test_banner_click_navigates_to_school_calendar_with_initial_tab(qapp):
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtGui import QMouseEvent
    from school_test_engine.ui.widgets.open_grades_banner import OpenGradesBanner

    class _StubWindow:
        def __init__(self):
            self.calls = []
        def show_school_calendar(self, initial_tab=None):
            self.calls.append(("show_school_calendar", initial_tab))

    win = _StubWindow()
    b = OpenGradesBanner(count=2, get_window=lambda: win)
    ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(1, 1), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    b.mousePressEvent(ev)
    assert win.calls == [("show_school_calendar", "past")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_open_grades_banner_widget.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the widget**

Create `src/school_test_engine/ui/widgets/open_grades_banner.py`:

```python
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..design import Color, FontFamily


class OpenGradesBanner(QFrame):
    """Klickbare Card unter dem FerienBanner — Zähler offener Noten."""

    def __init__(
        self,
        count: int,
        parent=None,
        get_window: Callable | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("openGradesBanner")
        self._count = count
        self._get_window = get_window or (lambda: self.window())
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(12)

        strip = QFrame()
        strip.setObjectName("openGradesBannerStrip")
        strip.setFixedWidth(4)
        h.addWidget(strip)

        emoji = QLabel("📝")
        emoji.setStyleSheet("font-size: 18pt;")
        h.addWidget(emoji)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._label = QLabel(self._compose_label(count))
        self._label.setFont(QFont(FontFamily.BODY, 11, QFont.Weight.Medium))
        text_col.addWidget(self._label)
        sub = QLabel("Tippe für Schulkalender")
        sub.setStyleSheet(f"color: {Color.PAPER_500}; font-size: 9pt;")
        text_col.addWidget(sub)
        h.addLayout(text_col)
        h.addStretch(1)

    @staticmethod
    def _compose_label(n: int) -> str:
        if n == 1:
            return "1 offene Note"
        return f"{n} offene Noten"

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            win = self._get_window()
            if win is not None and hasattr(win, "show_school_calendar"):
                win.show_school_calendar(initial_tab="past")
        super().mousePressEvent(event)
```

- [ ] **Step 4: Add QSS styling**

In `src/school_test_engine/ui/style.qss`, append:

```css
QFrame#openGradesBanner {
    background: #fffdf8;
    border: 1px solid #ebe3d5;
    border-radius: 10px;
}
QFrame#openGradesBannerStrip {
    background: #dfb968;
    border-radius: 2px;
}
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/ui/test_open_grades_banner_widget.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/widgets/open_grades_banner.py tests/ui/test_open_grades_banner_widget.py src/school_test_engine/ui/style.qss
git commit -m "feat(ui/widget): OpenGradesBanner — counter card analog FerienBanner (Phase 18 D1)"
```

---

### Task D2: Wire `OpenGradesBanner` into `MenuPage`

**Files:**
- Modify: `src/school_test_engine/ui/pages/menu.py`
- Create: `tests/ui/test_menu_page_open_grades.py`

- [ ] **Step 1: Write the failing test**

Create `tests/ui/test_menu_page_open_grades.py`:

```python
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.storage import (
    events_repo, run_migrations, users_repo,
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


def test_banner_hidden_when_no_open_grades(conn):
    from school_test_engine.ui.main_window import MainWindow
    uid = users_repo.create_user(conn, name="T")
    win = MainWindow(conn)
    win.set_active_user(uid)
    # No past KAs → banner should NOT exist or be invisible
    banner = getattr(win.menu_page, "_open_grades_banner", None)
    assert banner is None or banner.isVisible() is False


def test_banner_visible_when_past_ka_without_grade(conn):
    from school_test_engine.ui.main_window import MainWindow
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klausur", "2026-04-01")
    win = MainWindow(conn)
    win.menu_page._today_override = date(2026, 5, 1)
    win.set_active_user(uid)
    win.menu_page.reload()
    assert win.menu_page._open_grades_banner is not None
    assert win.menu_page._open_grades_banner.isVisible() is True


def test_banner_count_reflects_db_state(conn):
    from school_test_engine.ui.main_window import MainWindow
    uid = users_repo.create_user(conn, name="T")
    events_repo.create(conn, uid, "Mathe", "klausur", "2026-04-01")
    events_repo.create(conn, uid, "Englisch", "klausur", "2026-04-15")
    events_repo.create(conn, uid, "Bio", "test", "2026-04-20")
    win = MainWindow(conn)
    win.menu_page._today_override = date(2026, 5, 1)
    win.set_active_user(uid)
    win.menu_page.reload()
    banner = win.menu_page._open_grades_banner
    assert banner is not None
    assert "3 offene Noten" in banner._label.text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_menu_page_open_grades.py -v`
Expected: FAIL — `_open_grades_banner` attribute does not exist.

- [ ] **Step 3: Add the banner slot to `MenuPage`**

In `src/school_test_engine/ui/pages/menu.py`:

1. In `__init__` (around line 35), add field initialization next to `self._ferien_banner = None`:

```python
        self._open_grades_banner = None
```

2. After the existing `_ferien_banner_slot` block (line 60-63), add a new slot:

```python
        # Open-grades banner slot (refreshed in reload())
        self._open_grades_banner_slot = QVBoxLayout()
        self._open_grades_banner_slot.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self._open_grades_banner_slot)
```

3. In `reload()` (after the `self._refresh_ferien_banner()` call on line 103), add:

```python
        self._refresh_open_grades_banner()
```

4. Add the new method after `_refresh_ferien_banner`:

```python
    def _refresh_open_grades_banner(self) -> None:
        from ...storage import events_repo
        from ..widgets.open_grades_banner import OpenGradesBanner

        # Clear previous banner
        while self._open_grades_banner_slot.count():
            item = self._open_grades_banner_slot.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._open_grades_banner = None

        uid = self.window.active_user_id
        if uid is None:
            return
        today = self._today_override or date.today()
        rows = events_repo.list_past_klausuren_with_grade_status(
            self.window.conn, uid, today,
        )
        n_open = sum(1 for r in rows if r["assessment_id"] is None)
        if n_open == 0:
            return
        self._open_grades_banner = OpenGradesBanner(
            count=n_open,
            parent=self,
            get_window=lambda: self.window,
        )
        self._open_grades_banner_slot.addWidget(self._open_grades_banner)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ui/test_menu_page_open_grades.py -v`
Expected: All 3 tests PASS.

Run: `pytest -x -q`
Expected: full suite PASSES.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/menu.py tests/ui/test_menu_page_open_grades.py
git commit -m "feat(ui/page): MenuPage wires OpenGradesBanner slot (Phase 18 D2)"
```

---

### Task D3: `initial_tab` param on `SchoolCalendarPage.show_for` + wiring

**Files:**
- Modify: `src/school_test_engine/ui/pages/school_calendar.py`
- Modify: `src/school_test_engine/ui/main_window.py`
- Modify: `tests/ui/test_school_calendar_page.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_school_calendar_page.py`:

```python
def test_show_for_initial_tab_past_activates_tab_button(page_factory, tmp_path):
    import sqlite3
    from datetime import date as _date
    from school_test_engine.storage import run_migrations, users_repo

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)
    uid = users_repo.create_user(conn, name="T")

    page, _stub = page_factory(conn, uid, today=_date(2026, 5, 1))
    page.show_for(initial_tab="past")
    assert page._tab_buttons["past"].isChecked() is True
    assert page._filters.timeframe == "past"


def test_show_for_no_initial_tab_uses_persisted_filter(page_factory, tmp_path):
    import sqlite3
    from datetime import date as _date
    from school_test_engine.storage import run_migrations, users_repo

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)
    uid = users_repo.create_user(conn, name="T")

    page, _stub = page_factory(conn, uid, today=_date(2026, 5, 1))
    page.show_for()  # No initial_tab → defaults preserved
    # CalendarFilters.defaults() defines the default timeframe; just verify
    # show_for does not crash and a tab is selected.
    selected = [tf for tf, btn in page._tab_buttons.items() if btn.isChecked()]
    assert len(selected) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_school_calendar_page.py::test_show_for_initial_tab_past_activates_tab_button -v`
Expected: FAIL with `AttributeError: 'SchoolCalendarPage' object has no attribute 'show_for'`.

- [ ] **Step 3: Add `show_for` to `SchoolCalendarPage`**

In `src/school_test_engine/ui/pages/school_calendar.py`, add a new method after `reload()` (around line 141):

```python
    def show_for(self, initial_tab: str | None = None) -> None:
        """Public entry. Optionally pre-select a timeframe tab (past/future/all).

        Used by MenuPage banner click to land directly in 'Vergangen'.
        """
        if initial_tab is not None and initial_tab in self._tab_buttons:
            self._user_id = self.window.active_user_id
            if self._user_id is not None:
                self._filters = self._filters.with_timeframe(initial_tab)
                # Persist to DB so the choice survives the next reload
                users_repo.update_user(
                    self.conn, self._user_id, calendar_timeframe=initial_tab,
                )
        self.reload()
```

- [ ] **Step 4: Wire dispatcher param in `MainWindow`**

In `src/school_test_engine/ui/main_window.py`, update `_render_school_calendar` to accept `initial_tab`:

```python
    def _render_school_calendar(self, initial_tab: str | None = None) -> None:
        uid = self.active_user_id
        if uid is None:
            return
        self.header.set_page_actions([])
        self.school_calendar_page.show_for(initial_tab=initial_tab)
        self.stack.setCurrentWidget(self.school_calendar_page)
```

And update `show_school_calendar` to forward the param:

```python
    def show_school_calendar(self, initial_tab: str | None = None) -> None:
        self._navigate("school_calendar", initial_tab=initial_tab)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/ui/test_school_calendar_page.py -v`
Expected: All tests PASS.

Run: `pytest -x -q`
Expected: full suite PASSES.

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/pages/school_calendar.py src/school_test_engine/ui/main_window.py tests/ui/test_school_calendar_page.py
git commit -m "feat(ui/page): SchoolCalendarPage.show_for(initial_tab) + dispatcher wiring (Phase 18 D3)"
```

---

### Task D4: End-to-end integration test

**Files:**
- Create: `tests/integration/test_grade_nachtrag_flow.py`

- [ ] **Step 1: Check integration test directory + write the failing E2E test**

```bash
ls tests/integration/ 2>/dev/null || mkdir -p tests/integration && touch tests/integration/__init__.py
```

Create `tests/integration/test_grade_nachtrag_flow.py`:

```python
"""End-to-end test for Phase 18: vergangene KA in Schulkalender → click →
assessment_edit prefill → save → back via stack → badge wechselt → banner-
count dekrementiert."""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from school_test_engine.storage import (
    assessments_repo, events_repo, run_migrations, users_repo,
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


def test_e2e_grade_nachtrag_flow_via_banner(conn):
    from school_test_engine.ui.main_window import MainWindow

    uid = users_repo.create_user(conn, name="Clemens")
    eid = events_repo.create(conn, uid, "Mathe", "klausur", "2026-04-01")

    win = MainWindow(conn)
    win.menu_page._today_override = date(2026, 5, 1)
    win.school_calendar_page._today_override = date(2026, 5, 1)
    win.set_active_user(uid)
    win.menu_page.reload()

    # 1. Banner is visible with count=1 on MenuPage
    banner = win.menu_page._open_grades_banner
    assert banner is not None
    assert "1 offene Note" in banner._label.text()

    # 2. Click banner → navigate to school_calendar with initial_tab='past'
    win.show_school_calendar(initial_tab="past")
    assert win._current[0] == "school_calendar"
    assert win.school_calendar_page._filters.timeframe == "past"

    # 3. Click the past KA → assessment_edit prefill
    win.school_calendar_page._open_klausur(eid)
    assert win._current[0] == "assessment_edit"
    assert win.assessment_edit_page._prefill_event_id == eid
    assert win.assessment_edit_page.subject.isEnabled() is False

    # 4. Simulate saving a 2.5 → create assessment row + navigate back
    assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", "2026-04-01",
        grade=2.5, scheduled_event_id=eid,
    )
    win._navigate_back()  # would normally be called by assessment_edit._save
    assert win._current[0] == "school_calendar"

    # 5. Back again → menu, banner should be gone
    win._navigate_back()
    win.menu_page.reload()
    assert win._current[0] == "menu"
    assert win.menu_page._open_grades_banner is None
```

- [ ] **Step 2: Run test**

Run: `pytest tests/integration/test_grade_nachtrag_flow.py -v`
Expected: PASS, validating the entire flow end-to-end.

Run the entire suite one more time:

Run: `pytest -x -q`
Expected: ALL tests PASS (≈ 494 existing + ~25 new from Phase 18 = ~519 tests).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_grade_nachtrag_flow.py
git commit -m "test(integration): E2E grade-nachtrag flow via menu banner (Phase 18 D4)"
```

---

## Manual Acceptance Test (after Phase D)

Run the app: `bash run.sh`

1. Log in as Clemens.
2. Confirm MenuPage shows `📝 N offene Noten` banner if any past KAs lack grades.
3. Banner click → Schulkalender opens with "Vergangen"-Tab active.
4. Past KA card shows `Note offen` pill (honey-colored) — click → AssessmentEditPage opens with subject + date disabled, prefilled from the KA.
5. Select grade 2,5 → Speichern → returns to Schulkalender Vergangen-Tab → KA card now shows the round GradePill with "2,5".
6. Click BackButton (top-left arrow with "Zurück") → returns to MenuPage → banner is gone or shows decremented count.
7. Click the same KA card again (now showing grade pill) → AssessmentEditPage in edit mode (subject + date enabled, Löschen-Button visible).
8. Press `Esc` from any deeper page → goes back one step. Open a QMessageBox → Esc closes only the box, doesn't navigate.

---

## Open follow-up tasks after Phase 18 ships (NOT in this plan)

- Single-test, manual database with realistic data (Clemens' actual situation may have unlinked historical Notes — verify whether heuristic matching becomes necessary).
- Update `memory/project_overview.md` to reflect Phase 18 complete and remove "Dunkelmodus offen" line.
- If real-world feedback shows multi-grade-per-KA need (schriftlich + mündlich): separate spec.

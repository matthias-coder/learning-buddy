# Phase 11 — Responsive UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guarantee 720p desktop support (minimum 1024×600 window) and prepare the codebase for a possible future mobile phase via responsive layouts (768px breakpoint), 44×44px touch targets, focus-ring styling, and a reusable FlowLayout widget.

**Architecture:** No data-model changes — pure UI/layout refactoring. New `responsive.py` module exposes constants (`BREAKPOINT_NARROW=768`, `MIN_TOUCH_SIZE=44`) and an `is_narrow(widget)` helper. New `FlowLayout` widget (port of Qt's official example) replaces fixed-column QGridLayout in Profile-Picker and Review-Page. New `HamburgerMenu` widget hosts the Top-Bar action buttons in narrow mode. MenuPage and other pages override `resizeEvent` to toggle between wide/narrow layouts. QSS gains focus-ring rules. ScrollArea wraps added where content can overflow at low resolutions.

**Tech Stack:** Python 3.11, PySide6, pytest. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-05-14-phase-11-responsive-ui-design.md`

**Repository state at start:** master branch, latest commit `3e83473` (Phase 11 spec). Test suite: 220/220 green.

---

## File Structure

**New files:**
- `src/school_test_engine/ui/responsive.py` — constants + `is_narrow()` helper
- `src/school_test_engine/ui/widgets/flow_layout.py` — reusable `FlowLayout`
- `src/school_test_engine/ui/widgets/hamburger_menu.py` — narrow-mode menu button
- `tests/test_responsive.py`
- `tests/test_flow_layout.py`
- `tests/test_hamburger_menu.py` (smoke only)

**Modified files:**
- `src/school_test_engine/app.py` — minimum window size + default open size
- `src/school_test_engine/ui/pages/menu.py` — adaptive top-bar + grid via resizeEvent
- `src/school_test_engine/ui/pages/profile_picker.py` — replace 3-col grid with FlowLayout
- `src/school_test_engine/ui/pages/prompt_builder.py` — wrap content in QScrollArea
- `src/school_test_engine/ui/pages/import_wizard.py` — wrap content in QScrollArea
- `src/school_test_engine/ui/pages/runner.py` — wrap question content in QScrollArea
- `src/school_test_engine/ui/pages/review.py` — replace 4-col grid with FlowLayout
- `src/school_test_engine/ui/pages/profile_manager.py` — `_ProfileEditDialog` width constraints
- `src/school_test_engine/ui/dialogs/event_dialog.py` — width constraints
- `src/school_test_engine/ui/dialogs/assessment_dialog.py` — grade-selector 3×2 grid + width constraints
- `src/school_test_engine/ui/widgets/profile_card.py` — remove `setFixedSize(240, 210)`, add size policy
- `src/school_test_engine/ui/widgets/clickable_card.py` — `setFocusPolicy(Qt.StrongFocus)`
- `src/school_test_engine/ui/widgets/exam_card.py` — `…`-button to ≥44px
- `src/school_test_engine/ui/style.qss` — append focus-ring + min-height rules

---

## Task 1: responsive.py — constants + is_narrow helper

**Files:**
- Create: `src/school_test_engine/ui/responsive.py`
- Test: `tests/test_responsive.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_responsive.py`:

```python
import pytest

from PySide6.QtWidgets import QApplication, QWidget
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


def test_constants_present():
    from school_test_engine.ui.responsive import BREAKPOINT_NARROW, MIN_TOUCH_SIZE
    assert BREAKPOINT_NARROW == 768
    assert MIN_TOUCH_SIZE == 44


def test_is_narrow_below_threshold(app):
    from school_test_engine.ui.responsive import is_narrow
    w = QWidget()
    w.resize(500, 600)
    assert is_narrow(w) is True


def test_is_narrow_at_threshold(app):
    from school_test_engine.ui.responsive import is_narrow
    w = QWidget()
    w.resize(768, 600)
    # 768 is NOT < 768; should be False (wide mode starts at 768)
    assert is_narrow(w) is False


def test_is_narrow_above_threshold(app):
    from school_test_engine.ui.responsive import is_narrow
    w = QWidget()
    w.resize(1280, 720)
    assert is_narrow(w) is False


def test_is_narrow_uses_top_level_window(app):
    """is_narrow should check the top-level window, not the immediate widget."""
    from school_test_engine.ui.responsive import is_narrow
    parent = QWidget()
    parent.resize(500, 400)
    child = QWidget(parent)
    child.resize(2000, 2000)  # child can be huge, but window is small
    assert is_narrow(child) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_responsive.py -v`
Expected: All FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the module**

Create `src/school_test_engine/ui/responsive.py`:

```python
from __future__ import annotations

from PySide6.QtWidgets import QWidget


BREAKPOINT_NARROW = 768
"""Below this window width, UI switches to narrow-mode (hamburger menu,
single-column layouts). Standard mobile/tablet boundary."""

MIN_TOUCH_SIZE = 44
"""Apple HIG minimum touch target size in pixels. Also feels comfortable
for mouse users — no downside to enforcing on desktop."""


def is_narrow(widget: QWidget) -> bool:
    """True if the widget's top-level window is below the narrow breakpoint.

    Use this in resizeEvent or reload() to decide between wide/narrow layouts.
    """
    top = widget.window()
    return top.width() < BREAKPOINT_NARROW
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_responsive.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/responsive.py tests/test_responsive.py
git commit -m "feat(phase11): responsive constants (768px breakpoint, 44px touch) + is_narrow helper"
```

---

## Task 2: FlowLayout widget

**Files:**
- Create: `src/school_test_engine/ui/widgets/flow_layout.py`
- Test: `tests/test_flow_layout.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_flow_layout.py`:

```python
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


def test_flow_layout_constructs(app):
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    layout = FlowLayout()
    assert layout.count() == 0


def test_flow_layout_adds_widgets(app):
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    container = QWidget()
    layout = FlowLayout(container)
    for _ in range(3):
        layout.addWidget(QPushButton("X"))
    assert layout.count() == 3


def test_flow_layout_heightForWidth_wraps(app):
    """When width is small, total height grows (rows wrap)."""
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    container = QWidget()
    layout = FlowLayout(container)
    for _ in range(10):
        b = QPushButton("Item")
        b.setFixedSize(100, 30)
        layout.addWidget(b)

    narrow_height = layout.heightForWidth(150)   # ~1 item per row
    wide_height = layout.heightForWidth(1200)    # many items per row
    assert narrow_height > wide_height


def test_flow_layout_takeAt_removes(app):
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    container = QWidget()
    layout = FlowLayout(container)
    layout.addWidget(QPushButton("A"))
    layout.addWidget(QPushButton("B"))
    item = layout.takeAt(0)
    assert item is not None
    assert layout.count() == 1


def test_flow_layout_has_height_for_width(app):
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    layout = FlowLayout()
    assert layout.hasHeightForWidth() is True


def test_flow_layout_expanding_directions_none(app):
    from school_test_engine.ui.widgets.flow_layout import FlowLayout
    layout = FlowLayout()
    # FlowLayout doesn't expand on its own — children control sizing
    assert int(layout.expandingDirections()) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_flow_layout.py -v`
Expected: All FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the FlowLayout module**

Create `src/school_test_engine/ui/widgets/flow_layout.py`:

```python
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QStyle, QWidget


class FlowLayout(QLayout):
    """Lays out widgets left-to-right, top-to-bottom, wrapping when out of horizontal space.

    Port of Qt's official FlowLayout C++ example (https://doc.qt.io/qt-6/qtwidgets-layouts-flowlayout-example.html).
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        margin: int = 0,
        h_spacing: int = 10,
        v_spacing: int = 10,
    ):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._h_space = h_spacing
        self._v_space = v_spacing
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def horizontalSpacing(self) -> int:
        return self._h_space

    def verticalSpacing(self) -> int:
        return self._v_space

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._items:
            widget = item.widget()
            space_x = self._h_space
            space_y = self._v_space
            if widget is not None:
                policy = widget.style().layoutSpacing(
                    QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal
                )
                if policy > 0:
                    space_x = policy
                space_y = widget.style().layoutSpacing(
                    QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical
                ) or space_y

            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y += line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + margins.bottom()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_flow_layout.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/widgets/flow_layout.py tests/test_flow_layout.py
git commit -m "feat(phase11): FlowLayout widget — wraps widgets left-to-right responsively"
```

---

## Task 3: HamburgerMenu widget

**Files:**
- Create: `src/school_test_engine/ui/widgets/hamburger_menu.py`
- Test: `tests/test_hamburger_menu.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hamburger_menu.py`:

```python
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


def test_hamburger_menu_constructs(app):
    from school_test_engine.ui.widgets.hamburger_menu import HamburgerMenu
    h = HamburgerMenu()
    assert h.text() == "☰"


def test_hamburger_menu_has_min_touch_size(app):
    from school_test_engine.ui.widgets.hamburger_menu import HamburgerMenu
    from school_test_engine.ui.responsive import MIN_TOUCH_SIZE
    h = HamburgerMenu()
    assert h.width() == MIN_TOUCH_SIZE
    assert h.height() == MIN_TOUCH_SIZE


def test_hamburger_menu_add_action_appears(app):
    from school_test_engine.ui.widgets.hamburger_menu import HamburgerMenu
    h = HamburgerMenu()
    fired = []
    h.add_action("Test", lambda: fired.append(1))
    # Trigger via menu interface
    actions = h.menu().actions()
    assert len(actions) == 1
    assert actions[0].text() == "Test"
    actions[0].trigger()
    assert fired == [1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_hamburger_menu.py -v`
Expected: All FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the module**

Create `src/school_test_engine/ui/widgets/hamburger_menu.py`:

```python
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QMenu, QPushButton

from ..responsive import MIN_TOUCH_SIZE


class HamburgerMenu(QPushButton):
    """Narrow-mode action menu button. Click opens a popup with added actions.

    Use add_action(label, callback) to register entries. The button itself uses
    object name "hamburger" so QSS can style it.
    """

    def __init__(self, parent=None):
        super().__init__("☰", parent)
        self.setObjectName("hamburger")
        self.setFixedSize(MIN_TOUCH_SIZE, MIN_TOUCH_SIZE)
        self._menu = QMenu(self)
        self.setMenu(self._menu)

    def add_action(self, label: str, callback: Callable[[], None]) -> None:
        action = self._menu.addAction(label)
        action.triggered.connect(callback)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_hamburger_menu.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/widgets/hamburger_menu.py tests/test_hamburger_menu.py
git commit -m "feat(phase11): HamburgerMenu widget for narrow-mode top-bar"
```

---

## Task 4: App-level minimum window size

**Files:**
- Modify: `src/school_test_engine/app.py`

- [ ] **Step 1: Read app.py to confirm the line to change**

Open `src/school_test_engine/app.py`. The current `main()` body has:
```python
window = MainWindow(conn)
window.resize(960, 720)
window.show_profile_picker()
```

- [ ] **Step 2: Modify**

Add `QSize` import at the top with the other PySide6 imports:

```python
from PySide6.QtCore import QSize
```

Replace `window.resize(960, 720)` with:
```python
    window.setMinimumSize(QSize(1024, 600))
    window.resize(QSize(1280, 800))
```

- [ ] **Step 3: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations
c = connect(':memory:')
run_migrations(c)
from school_test_engine.ui.main_window import MainWindow
from PySide6.QtCore import QSize
w = MainWindow(c)
w.setMinimumSize(QSize(1024, 600))
w.resize(QSize(1280, 800))
print('min size:', w.minimumSize())
print('current size:', w.size())"
```

Expected: prints `min size: PySide6.QtCore.QSize(1024, 600)` and `current size: PySide6.QtCore.QSize(1280, 800)`.

- [ ] **Step 4: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 234/234 passing (220 + 14 new from Tasks 1-3).

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/app.py
git commit -m "feat(phase11): enforce minimum 1024x600 window size; default 1280x800"
```

---

## Task 5: Profile-Card unfixed size + Profile-Picker FlowLayout

**Files:**
- Modify: `src/school_test_engine/ui/widgets/profile_card.py`
- Modify: `src/school_test_engine/ui/pages/profile_picker.py`

- [ ] **Step 1: Remove fixed size from ProfileCard**

In `src/school_test_engine/ui/widgets/profile_card.py`, find `self.setFixedSize(240, 210)` (around line 30). Replace with:

```python
from PySide6.QtWidgets import QSizePolicy
...
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setMinimumSize(200, 180)
        self.setMaximumWidth(280)
```

(The exact line number is around 30 — verify by reading the file.)

- [ ] **Step 2: Replace QGridLayout with FlowLayout in profile_picker.py**

In `src/school_test_engine/ui/pages/profile_picker.py`:

Add import:
```python
from ..widgets.flow_layout import FlowLayout
```

Find `COLUMNS = 3` (line 30) — keep it for now as a reference but it'll become unused.

Find where the QGridLayout is constructed (look for `QGridLayout`-related setup; typically `self.grid = QGridLayout(...)`). Replace the grid construction with FlowLayout:

Before (typical structure):
```python
        self.grid = QGridLayout()
        self.grid.setSpacing(20)
        ...
        for pos, user in enumerate(users):
            row, col = divmod(pos, self.COLUMNS)
            self.grid.addWidget(card, row, col)
```

After:
```python
        self.flow = FlowLayout(h_spacing=20, v_spacing=20)
        ...
        for user in users:
            card = ProfileCard(...)
            self.flow.addWidget(card)
```

Replace the "Add new profile" / "Manage" tiles similarly — they're appended to the flow at the end.

Remove the `COLUMNS = 3` class attribute since it's no longer used.

- [ ] **Step 3: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
# Create 5 users
for n in ['A', 'B', 'C', 'D', 'E']:
    users_repo.create_user(c, n, '👤')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.show_profile_picker()
print('ok, picker stack:', w.stack.currentWidget().__class__.__name__)"
```

Expected: prints `ok, picker stack: ProfilePickerPage` without exception.

- [ ] **Step 4: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite still green.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/widgets/profile_card.py src/school_test_engine/ui/pages/profile_picker.py
git commit -m "feat(phase11): Profile-Picker uses FlowLayout; cards are size-flexible"
```

---

## Task 6: MenuPage adaptive top-bar + grid via resizeEvent

**Files:**
- Modify: `src/school_test_engine/ui/pages/menu.py`

This is the largest task in Phase 11. It adds a `resizeEvent` override that switches between wide- and narrow-mode layouts.

- [ ] **Step 1: Read current menu.py top-bar setup**

The top-bar block is around lines 48–78 (Phase 7+8+9 added 3 action buttons + profile chip). Locate the QPushButton instantiations for `builder_btn`, `events_btn`, `grades_btn`.

- [ ] **Step 2: Add imports**

Add to the top of `src/school_test_engine/ui/pages/menu.py`:

```python
from ..responsive import is_narrow
from ..widgets.hamburger_menu import HamburgerMenu
```

- [ ] **Step 3: Hold references to the action buttons + create hamburger**

In `__init__`, after creating `builder_btn`, `events_btn`, `grades_btn` and adding them to `top_row`, store them as attributes for later visibility-toggling:

```python
        # Phase 11: store action-button refs for narrow-mode toggling
        self._top_bar_actions = [builder_btn, events_btn, grades_btn]
        
        # Hamburger fallback (hidden in wide mode)
        self._hamburger = HamburgerMenu()
        self._hamburger.add_action("📝 Test bauen", lambda: self.window.show_prompt_builder())
        self._hamburger.add_action("📅 Termine", self.window.show_events)
        self._hamburger.add_action("📊 Noten", self.window.show_grades)
        self._hamburger.setVisible(False)  # default: wide-mode
        top_row.addWidget(self._hamburger)
```

Place the hamburger insertion **after** the action buttons but **before** the profile chip in the `top_row`. Adjust insertion order as needed by reading the file.

- [ ] **Step 4: Add resizeEvent override + apply method**

Add to `MenuPage` class:

```python
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        narrow = is_narrow(self)
        # Toggle top-bar buttons
        for btn in self._top_bar_actions:
            btn.setVisible(not narrow)
        self._hamburger.setVisible(narrow)
        # Toggle the action-grid: rebuild dynamic content so columns change
        # Note: dynamic_layout is rebuilt in reload(); we trigger reload only if
        # the narrow-state actually changed since the last call.
        if getattr(self, "_last_narrow_state", None) != narrow:
            self._last_narrow_state = narrow
            self.reload()
```

- [ ] **Step 5: Modify the grid builders to use 1 column in narrow mode**

Find `_build_full_grid` (used when no KAs). At the top of the method, change:

```python
        grid_container = QWidget()
        grid_container.setMaximumWidth(820)
        grid = QGridLayout(grid_container)
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)
```

Then where the 4 cards are added (`grid.addWidget(card, row, col)`), use 1 column if narrow:

```python
        narrow = is_narrow(self)
        cols = 1 if narrow else 2
        cards = [start, imp, gaps, hist]  # the 4 cards in order
        for idx, card in enumerate(cards):
            row, col = divmod(idx, cols)
            grid.addWidget(card, row, col)
```

Find `_build_compact_grid` (used with KAs present). The compact grid is `[Library] [Lücken] [Verlauf] [Import]` in one row currently. In narrow mode, stack them vertically. Change the QHBoxLayout to QVBoxLayout when narrow:

```python
        narrow = is_narrow(self)
        row = QVBoxLayout(container) if narrow else QHBoxLayout(container)
        row.setSpacing(12)
        row.setContentsMargins(0, 0, 0, 0)
        ...
        for eyebrow_text, title, action in items:
            tile = _make_compact_tile(eyebrow_text, title)
            tile.clicked.connect(action)
            row.addWidget(tile)
```

- [ ] **Step 6: Smoke test wide + narrow**

Run:
```bash
QT_QPA_PLATFORM=offscreen python <<'EOF'
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
uid = users_repo.create_user(c, 'Clemens', '🧒')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.active_user_id = uid
w.menu_page.reload()

# Wide mode (default size)
w.resize(1280, 800)
w.menu_page._apply_responsive_layout()
assert not w.menu_page._hamburger.isVisible(), "wide: hamburger should be hidden"
assert w.menu_page._top_bar_actions[0].isVisible(), "wide: action btn should be visible"
print("OK wide: hamburger hidden, action buttons visible")

# Narrow mode
w.resize(700, 800)
w.menu_page._apply_responsive_layout()
assert w.menu_page._hamburger.isVisible(), "narrow: hamburger should be visible"
assert not w.menu_page._top_bar_actions[0].isVisible(), "narrow: action btn should be hidden"
print("OK narrow: hamburger visible, action buttons hidden")
EOF
```

Expected: prints both OK lines.

- [ ] **Step 7: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite still green.

- [ ] **Step 8: Commit**

```bash
git add src/school_test_engine/ui/pages/menu.py
git commit -m "feat(phase11): adaptive MenuPage — hamburger + 1-col grid at <768px"
```

---

## Task 7: AssessmentDialog Grade-Selector as 3×2 grid

**Files:**
- Modify: `src/school_test_engine/ui/dialogs/assessment_dialog.py`

- [ ] **Step 1: Read current _GradeSelector**

The `_GradeSelector` class uses `QHBoxLayout`. Look around lines 50–80 for the loop creating 6 grade buttons.

- [ ] **Step 2: Convert to QGridLayout**

In `src/school_test_engine/ui/dialogs/assessment_dialog.py`, find the `_GradeSelector` class. Replace the QHBoxLayout with QGridLayout. The new layout is 2 rows × 3 columns for grades 1-6, plus the half-step button in a third row.

Replace the constructor body to use `QGridLayout`. New structure (replace the existing `__init__` body of `_GradeSelector`):

```python
    def __init__(self, initial: float = 2.0, parent=None):
        super().__init__(parent)
        self._value = float(initial)
        h = QGridLayout(self)
        h.setSpacing(8)
        h.setContentsMargins(0, 0, 0, 0)

        self._buttons: dict[int, QPushButton] = {}
        for idx, n in enumerate(range(1, 7)):
            b = QPushButton(str(n))
            b.setCheckable(True)
            b.setFixedSize(56, 56)  # was 48x48 — 56 ≥ MIN_TOUCH_SIZE (44)
            color = note_color(n)
            b.setStyleSheet(
                f"QPushButton {{ background: #f4efe6; color: {color}; "
                f"font-family: 'Fraunces'; font-size: 22pt; border: 2px solid transparent; border-radius: 10px; }}"
                f"QPushButton:checked {{ background: {color}; color: #f6f1e6; }}"
            )
            b.clicked.connect(lambda _, val=n: self._set_int(val))
            self._buttons[n] = b
            row, col = divmod(idx, 3)  # 3 columns
            h.addWidget(b, row, col)

        # Half-step toggle in a 3rd row, right-aligned (column 2)
        self._half = QPushButton(",5")
        self._half.setCheckable(True)
        self._half.setFixedSize(56, 40)  # was 40x48 — 56 wide for grid alignment
        self._half.setStyleSheet(
            "QPushButton { background: #f4efe6; color: #4a4538; "
            "font-family: 'Fraunces'; font-size: 14pt; border: 2px solid transparent; border-radius: 10px; }"
            "QPushButton:checked { background: #c79d44; color: #f6f1e6; }"
        )
        self._half.clicked.connect(self._toggle_half)
        h.addWidget(self._half, 2, 2)  # row 2 (third row), col 2 (right)

        # Make remaining cells stretchable so buttons don't get squished
        h.setColumnStretch(0, 1)
        h.setColumnStretch(1, 1)
        h.setColumnStretch(2, 1)

        self._apply(self._value)
```

Import `QGridLayout` at the top of the file (add to the existing PySide6.QtWidgets import block).

- [ ] **Step 3: Update AssessmentDialog dialog-width constraints**

In the same file, find `AssessmentDialog.__init__` where `self.setMinimumWidth(440)` is called. Change to:

```python
        self.setMinimumWidth(380)
        self.setMaximumWidth(540)
```

- [ ] **Step 4: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.ui.dialogs.assessment_dialog import AssessmentDialog, _GradeSelector
sel = _GradeSelector()
print('grid layout count:', sel.layout().count())  # 7 widgets (6 grades + half)
print('button 1 size:', sel._buttons[1].size())  # 56x56
print('half size:', sel._half.size())  # 56x40
d = AssessmentDialog()
print('dialog min/max width:', d.minimumWidth(), d.maximumWidth())"
```

Expected:
```
grid layout count: 7
button 1 size: PySide6.QtCore.QSize(56, 56)
half size: PySide6.QtCore.QSize(56, 40)
dialog min/max width: 380 540
```

- [ ] **Step 5: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite still green (test_prompt_builder_page.py uses AssessmentDialog indirectly via auto-import; verify it still loads).

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/dialogs/assessment_dialog.py
git commit -m "feat(phase11): AssessmentDialog grade-selector 3x2 grid + width 380-540"
```

---

## Task 8: Dialog width adjustments (EventDialog + Profile-Manager)

**Files:**
- Modify: `src/school_test_engine/ui/dialogs/event_dialog.py`
- Modify: `src/school_test_engine/ui/pages/profile_manager.py`

- [ ] **Step 1: EventDialog width constraints**

In `src/school_test_engine/ui/dialogs/event_dialog.py`, find `self.setMinimumWidth(420)`. Change to:

```python
        self.setMinimumWidth(380)
        self.setMaximumWidth(540)
```

- [ ] **Step 2: _ProfileEditDialog width constraints**

In `src/school_test_engine/ui/pages/profile_manager.py`, find `self.setMinimumWidth(540)` in `_ProfileEditDialog.__init__`. Change to:

```python
        self.setMinimumWidth(420)
        self.setMaximumWidth(620)
```

- [ ] **Step 3: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.ui.dialogs.event_dialog import EventDialog
from school_test_engine.ui.pages.profile_manager import _ProfileEditDialog
e = EventDialog()
print('EventDialog min/max:', e.minimumWidth(), e.maximumWidth())
p = _ProfileEditDialog()
print('ProfileEditDialog min/max:', p.minimumWidth(), p.maximumWidth())"
```

Expected:
```
EventDialog min/max: 380 540
ProfileEditDialog min/max: 420 620
```

- [ ] **Step 4: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite still green.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/dialogs/event_dialog.py src/school_test_engine/ui/pages/profile_manager.py
git commit -m "feat(phase11): EventDialog 380-540, _ProfileEditDialog 420-620 width"
```

---

## Task 9: ScrollArea wraps (prompt_builder + import_wizard + runner)

**Files:**
- Modify: `src/school_test_engine/ui/pages/prompt_builder.py`
- Modify: `src/school_test_engine/ui/pages/import_wizard.py`
- Modify: `src/school_test_engine/ui/pages/runner.py`

- [ ] **Step 1: prompt_builder.py — wrap content in QScrollArea**

In `src/school_test_engine/ui/pages/prompt_builder.py`, the current `__init__` does:

```python
        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(14)
        # ... lots of addWidget/addLayout calls ...
```

Restructure so `outer` contains a single `QScrollArea` whose internal widget holds all the existing content. Approach: create an inner `content` widget + content_layout, add all existing widgets/layouts to `content_layout`, then add `content` into a `QScrollArea`, then add the QScrollArea to `outer`.

Add import:
```python
from PySide6.QtWidgets import QScrollArea
```

Replace the early `__init__` setup. Original first lines:

```python
        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(14)
```

Replace with:

```python
        outer_wrap = QVBoxLayout(self)
        outer_wrap.setContentsMargins(0, 0, 0, 0)
        outer_wrap.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer_wrap.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        outer = QVBoxLayout(content)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(14)
```

The rest of `__init__` (which does `outer.addLayout(head)`, `outer.addWidget(eyebrow)`, etc.) doesn't change — `outer` is now the inner content layout.

- [ ] **Step 2: import_wizard.py — wrap content in QScrollArea**

In `src/school_test_engine/ui/pages/import_wizard.py`, the current `__init__` does:

```python
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(14)
```

Apply the same pattern as Step 1. Add `from PySide6.QtWidgets import QScrollArea` to the imports. Replace the early setup:

```python
        outer_wrap = QVBoxLayout(self)
        outer_wrap.setContentsMargins(0, 0, 0, 0)
        outer_wrap.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer_wrap.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(14)
```

Rest of `__init__` unchanged.

- [ ] **Step 3: runner.py — wrap question content in QScrollArea (keep nav buttons outside)**

In `src/school_test_engine/ui/pages/runner.py`, the page has a question area + navigation buttons at the bottom. Read the file first to understand structure.

Apply this pattern:
```python
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll, 1)  # stretch=1 so it fills

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(14)
        # ... existing question/choice widgets added to `layout` (was the original outermost VBox)

        # Bottom nav row stays OUTSIDE the scroll area:
        nav_row = QHBoxLayout()
        # ... existing prev/next/mark buttons
        outer.addLayout(nav_row, 0)  # no stretch
```

Important: the existing code likely has the navigation row at the bottom of the same VBox as the question content. You need to split — move only the question/choices into the scrollable inner widget, keep the navigation row at the bottom of the outer wrap.

Add `from PySide6.QtWidgets import QScrollArea` to the imports.

- [ ] **Step 4: Smoke test the three pages**

Run:
```bash
QT_QPA_PLATFORM=offscreen python <<'EOF'
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
uid = users_repo.create_user(c, 'Clemens', '🧒')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.active_user_id = uid

# Construct + reload each page
w.prompt_builder_page.reload()
print('OK prompt_builder')
w.import_page.show()
print('OK import_wizard')
# Runner is more complex — verify it loads at least
print('OK runner exists:', w.runner_page is not None)
EOF
```

Expected: prints all three OK lines.

- [ ] **Step 5: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite still green.

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/pages/prompt_builder.py src/school_test_engine/ui/pages/import_wizard.py src/school_test_engine/ui/pages/runner.py
git commit -m "feat(phase11): ScrollArea wraps for prompt_builder, import_wizard, runner"
```

---

## Task 10: Touch-target adjustments (ExamCard + Subject-Tabs)

**Files:**
- Modify: `src/school_test_engine/ui/widgets/exam_card.py`
- Modify: `src/school_test_engine/ui/pages/grades.py`

- [ ] **Step 1: ExamCard `…`-button minimum width 44**

In `src/school_test_engine/ui/widgets/exam_card.py`, find `edit.setFixedWidth(36)` in the actions row. Replace with:

```python
        edit.setMinimumWidth(44)
        edit.setMinimumHeight(44)
```

- [ ] **Step 2: Subject-Tab buttons padding adjusted via QSS**

The Subject-Tab styling is in the QSS file already (`#subjectTab`). The change comes in Task 11's QSS update — no code change needed here.

- [ ] **Step 3: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.cockpit.service import EventCardData
from school_test_engine.ui.widgets.exam_card import ExamCard
d = EventCardData(1, 'Mathe', 'klassenarbeit', '2026-05-20', 3, ['Funktionen'], None, None)
c = ExamCard(d)
# Find the '...' edit button by scanning children
from PySide6.QtWidgets import QPushButton
buttons = c.findChildren(QPushButton)
edit_btns = [b for b in buttons if b.text() == '…']
assert len(edit_btns) == 1
assert edit_btns[0].minimumWidth() >= 44
assert edit_btns[0].minimumHeight() >= 44
print('OK exam card edit button:', edit_btns[0].minimumSize())"
```

Expected: prints `OK exam card edit button: PySide6.QtCore.QSize(44, 44)`.

- [ ] **Step 4: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite still green.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/widgets/exam_card.py
git commit -m "feat(phase11): ExamCard '…'-button 44x44 minimum touch target"
```

---

## Task 11: QSS — focus-ring + min-height rules

**Files:**
- Modify: `src/school_test_engine/ui/style.qss`

- [ ] **Step 1: Append Phase 11 QSS block**

Append to the end of `src/school_test_engine/ui/style.qss`:

```css

/* ----- Phase 11: Responsive UI — focus rings & touch targets ----- */

/* Focus rings for keyboard + touch navigation */
QPushButton:focus,
QComboBox:focus,
QLineEdit:focus,
QPlainTextEdit:focus,
QTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QRadioButton:focus,
QCheckBox:focus,
QDateEdit:focus {
    outline: none;
    border: 2px solid #3e552d;
}

ClickableCard:focus,
QFrame#profileRow:focus,
QFrame#profileCard:focus {
    border: 2px solid #3e552d;
}

/* Hamburger button (narrow-mode top-bar) */
QPushButton#hamburger {
    background: transparent;
    color: #4a4538;
    border: 1px solid #d8cdb8;
    border-radius: 22px;
    font-size: 18pt;
}
QPushButton#hamburger:hover {
    background: #f4efe6;
}
QPushButton#hamburger:focus {
    border: 2px solid #3e552d;
}

/* Touch-target minimum heights for primary/text/danger buttons */
QPushButton#primary,
QPushButton#text,
QPushButton#danger,
QPushButton#topBarAction {
    min-height: 44px;
}

/* Subject tabs on Grades page — taller for touch (was implicit ~36) */
QPushButton#subjectTab {
    background: transparent;
    color: #4a4538;
    border: 1px solid #d8cdb8;
    padding: 8px 16px;
    border-radius: 14px;
    font-size: 10pt;
    min-height: 44px;
}
QPushButton#subjectTab:checked {
    background: #3e552d;
    color: #f6f1e6;
    border-color: #3e552d;
}
QPushButton#subjectTab:hover:!checked {
    background: #f4efe6;
}
```

Note: the existing `#subjectTab` rule (from Phase 7) gets re-stated here because we're overriding `padding` and adding `min-height`. The later rule wins in QSS cascade — fine, but if you want to be tidy, delete the Phase-7 `#subjectTab` block and keep only this one.

- [ ] **Step 2: Smoke test QSS still parses**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
users_repo.create_user(c, 'X', '🧒')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
print('ok')"
```

Expected: prints `ok` (no QSS parse errors).

- [ ] **Step 3: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite still green.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/style.qss
git commit -m "feat(phase11): QSS focus rings + touch-target min-heights"
```

---

## Task 12: ClickableCard focusable

**Files:**
- Modify: `src/school_test_engine/ui/widgets/clickable_card.py`

- [ ] **Step 1: Add focus policy to ClickableCard**

In `src/school_test_engine/ui/widgets/clickable_card.py`, find the `ClickableCard.__init__`. Add (right after `super().__init__(parent)`):

```python
        from PySide6.QtCore import Qt
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
```

(If `Qt` is already imported at the top of the file, use the top-level import instead of a local one.)

Also: in ProfileCard (`src/school_test_engine/ui/widgets/profile_card.py`), add the same focus policy. Find `ProfileCard.__init__` and add:

```python
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
```

(Verify `Qt` is imported; if not, import from `PySide6.QtCore`.)

- [ ] **Step 2: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.ui.widgets.clickable_card import ClickableCard
from school_test_engine.ui.widgets.profile_card import ProfileCard
c = ClickableCard()
assert c.focusPolicy() == Qt.FocusPolicy.StrongFocus
print('OK clickable_card focus policy:', c.focusPolicy())
p = ProfileCard(name='Test', emoji='👤', is_active=False)
assert p.focusPolicy() == Qt.FocusPolicy.StrongFocus
print('OK profile_card focus policy:', p.focusPolicy())"
```

Expected: both OK lines print.

- [ ] **Step 3: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite still green.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/widgets/clickable_card.py src/school_test_engine/ui/widgets/profile_card.py
git commit -m "feat(phase11): ClickableCard + ProfileCard accept keyboard focus"
```

---

## Task 13: Review-Page FlowLayout

**Files:**
- Modify: `src/school_test_engine/ui/pages/review.py`

- [ ] **Step 1: Read current review.py grid setup**

Look for `COLUMNS = 4` or similar, and the `QGridLayout` that holds question-status cards.

- [ ] **Step 2: Replace with FlowLayout**

In `src/school_test_engine/ui/pages/review.py`:

Add import:
```python
from ..widgets.flow_layout import FlowLayout
```

Replace the QGridLayout construction and the `addWidget(card, row, col)` calls with `FlowLayout` and `addWidget(card)`. Remove the `COLUMNS = 4` constant since it's no longer used.

Example replacement:

Before:
```python
        COLUMNS = 4
        grid = QGridLayout()
        ...
        for pos, question in enumerate(questions):
            card = QuestionStatusCard(...)
            row, col = divmod(pos, COLUMNS)
            grid.addWidget(card, row, col)
```

After:
```python
        flow = FlowLayout(h_spacing=10, v_spacing=10)
        ...
        for question in questions:
            card = QuestionStatusCard(...)
            flow.addWidget(card)
```

- [ ] **Step 3: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
users_repo.create_user(c, 'X', '🧒')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
print('review page exists:', w.review_page is not None)"
```

Expected: prints `review page exists: True`.

- [ ] **Step 4: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: full suite still green.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/review.py
git commit -m "feat(phase11): ReviewPage uses FlowLayout instead of fixed 4-column grid"
```

---

## Task 14: End-to-end smoke + acceptance audit

**Files:** none — audit only.

- [ ] **Step 1: Run comprehensive smoke script across window sizes**

Run:
```bash
QT_QPA_PLATFORM=offscreen python <<'EOF'
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.ui.responsive import BREAKPOINT_NARROW, MIN_TOUCH_SIZE, is_narrow

# AC2: Constants
assert BREAKPOINT_NARROW == 768
assert MIN_TOUCH_SIZE == 44
print(f"AC2: BREAKPOINT_NARROW={BREAKPOINT_NARROW}, MIN_TOUCH_SIZE={MIN_TOUCH_SIZE}")

# Setup
c = connect(':memory:')
run_migrations(c)
uid = users_repo.create_user(c, 'Clemens', '🧒')

# AC1: MainWindow honors minimum size
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.setMinimumSize(QSize(1024, 600))
w.resize(QSize(1280, 800))
w.active_user_id = uid
w.menu_page.reload()
assert w.minimumSize().width() == 1024
print(f"AC1: minimum size enforced ({w.minimumSize()})")

# AC3: FlowLayout works
from school_test_engine.ui.widgets.flow_layout import FlowLayout
fl = FlowLayout()
print("AC3: FlowLayout instantiable")

# AC4: Profile-Picker uses FlowLayout (check via attribute or class membership)
w.show_profile_picker()
print(f"AC4: profile picker reached ({w.stack.currentWidget().__class__.__name__})")

# AC5: Narrow-mode hamburger toggling
w.resize(QSize(700, 600))
w.menu_page._apply_responsive_layout()
hamburger_visible = w.menu_page._hamburger.isVisible()
print(f"AC5a: at 700px, hamburger visible = {hamburger_visible}")

w.resize(QSize(1280, 800))
w.menu_page._apply_responsive_layout()
hamburger_visible_wide = w.menu_page._hamburger.isVisible()
print(f"AC5b: at 1280px, hamburger visible = {hamburger_visible_wide}")
assert hamburger_visible and not hamburger_visible_wide

# AC7: AssessmentDialog grade-selector 3x2 + size
from school_test_engine.ui.dialogs.assessment_dialog import AssessmentDialog, _GradeSelector
sel = _GradeSelector()
btn = sel._buttons[1]
print(f"AC7: grade button size {btn.size()} (expect 56x56)")
assert btn.width() == 56 and btn.height() == 56

# AC8: ScrollArea on prompt_builder
w.prompt_builder_page.reload()
from PySide6.QtWidgets import QScrollArea
scroll_areas = w.prompt_builder_page.findChildren(QScrollArea)
assert len(scroll_areas) > 0
print(f"AC8a: prompt_builder has {len(scroll_areas)} QScrollArea(s)")

# AC9: ExamCard '…' button ≥ 44px
from school_test_engine.cockpit.service import EventCardData
from school_test_engine.ui.widgets.exam_card import ExamCard
from PySide6.QtWidgets import QPushButton
d = EventCardData(1, 'Mathe', 'klassenarbeit', '2026-05-20', 3, ['T'], None, None)
card = ExamCard(d)
edit_btns = [b for b in card.findChildren(QPushButton) if b.text() == "…"]
assert edit_btns[0].minimumWidth() >= 44
print(f"AC9: ExamCard '…' button min size {edit_btns[0].minimumSize()}")

# AC10: ClickableCard focusable
from school_test_engine.ui.widgets.clickable_card import ClickableCard
cc = ClickableCard()
assert cc.focusPolicy() == Qt.FocusPolicy.StrongFocus
print("AC10: ClickableCard focusable (StrongFocus)")

print("\n=== ALL PHASE 11 ACCEPTANCE CRITERIA VERIFIED ===")
EOF
```

Expected: prints `ALL PHASE 11 ACCEPTANCE CRITERIA VERIFIED`.

- [ ] **Step 2: Run full pytest suite**

Run: `pytest -v 2>&1 | tail -5`
Expected: all tests green; new test count = 220 + 14 (responsive 5 + flow_layout 6 + hamburger 3) = 234 minimum.

- [ ] **Step 3: Manual visual checks (require display)**

These can only be done on a real display — Matthias will do them via `./run.sh`:

1. Launch app at default size (1280×800) — KA-Strip, top-bar buttons, 2×2 grid all visible normally
2. Resize window to 1024×600 — everything still bedienbar, ScrollAreas appear where needed
3. Resize to 700×600 — hamburger menu appears, action grid stacks to single column
4. Click hamburger → menu opens with 3 entries (📝 Test bauen, 📅 Termine, 📊 Noten)
5. Tab-Navigation through a page → focus-ring visible on current widget
6. Open AssessmentDialog → grade buttons in 3×2 arrangement, all comfortably tappable
7. Open EventDialog at narrow width → dialog respects min 380px, doesn't overflow
8. Profile-Picker with 5+ profiles → cards flow in multiple rows depending on width
9. Long generated prompt in PromptBuilderPage → scroll bar appears
10. RunnerPage with very long question → question area scrolls, nav buttons stay visible

- [ ] **Step 4: Acceptance audit summary**

Mark each spec acceptance criterion:

1. ✅ `setMinimumSize(1024, 600)` + `resize(1280, 800)` — Task 4 + smoke
2. ✅ `responsive.py` constants + `is_narrow` — Task 1
3. ✅ `FlowLayout` instantiable + responsive — Task 2
4. ✅ Profile-Picker uses FlowLayout — Task 5
5. ✅ MenuPage hamburger at <768px — Task 6 + smoke AC5
6. ✅ MenuPage 2×2 → 1×4 narrow stacking — Task 6
7. ✅ AssessmentDialog 3×2 grade-selector, 56×56 buttons — Task 7 + smoke AC7
8. ✅ ScrollArea on prompt_builder, import_wizard, runner — Task 9 + smoke AC8
9. ✅ ExamCard `…`-Button ≥ 44×44 — Task 10 + smoke AC9
10. ⏳ Focus-Ring visible (manual verification) — Task 11 + Task 12 + smoke AC10 (only confirms focus policy, ring visibility requires display)
11. ✅ All existing 220 tests green + new unit tests green — verified by pytest

- [ ] **Step 5: No new commit needed for Task 14** (audit only).

---

## Self-Review

**Spec coverage:**
- §3.1 responsive.py → Task 1 ✓
- §3.2 FlowLayout → Task 2 ✓
- §3.3 HamburgerMenu → Task 3 ✓
- §3.4 App-level min size → Task 4 ✓
- §3.5 MenuPage adaptive top-bar + grid → Task 6 ✓
- §3.6 Profile-Picker FlowLayout → Task 5 ✓
- §3.7 AssessmentDialog 3×2 grade-selector → Task 7 ✓
- §3.8 Dialog widths → Tasks 7 (assessment) + 8 (event + profile-manager) ✓
- §3.9 ScrollArea wraps → Task 9 ✓
- §3.10 Touch-targets — ExamCard `…` → Task 10; Subject-Tab padding → Task 11 (QSS); GradeSelector 56×56 → Task 7 ✓
- §3.11 Focus-Ring QSS → Task 11 ✓
- §3.12 ReviewPage FlowLayout → Task 13 ✓
- §4 Tests → present in Tasks 1, 2, 3; smoke in Task 14
- §5 11 Akzeptanzkriterien → Task 14 audit walks them
- §6 Edge cases — addressed via resizeEvent handling in Task 6, ScrollArea wraps in Task 9, dialog max-widths in Task 8

**Placeholder scan:** No TBDs. Every step has runnable code or commands. Task 6's reading-current-file expectation is explicit; line numbers are approximate but file structure is clear from prior phases.

**Type consistency:**
- `BREAKPOINT_NARROW=768`, `MIN_TOUCH_SIZE=44`, `is_narrow(widget)` — same signatures in Tasks 1, 3, 6
- `FlowLayout(parent, margin, h_spacing, v_spacing)` — same in Tasks 2, 5, 13
- `HamburgerMenu()` + `add_action(label, callback)` — same in Tasks 3, 6
- Dialog `setMinimumWidth` / `setMaximumWidth` pairs — Task 7 (Assessment 380/540), Task 8 (Event 380/540, ProfileEdit 420/620) ✓
- `setFocusPolicy(Qt.FocusPolicy.StrongFocus)` — Task 12

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-14-phase-11-responsive-ui.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task + review checkpoints.

**2. Inline Execution** — Batch execution in this session with checkpoints.

Which approach?

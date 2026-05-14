# Phase 12 — UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four UX pain points found during Phase 11 manual walk-through: clearer test-exit navigation, profile-edit as inline page (not modal popup), avatar-photo-only (remove emoji selection, use generic placeholder), and profile-picker layout constrained to max 3 cards per row.

**Architecture:** Pure UI refactoring — no data model changes, no new repos. New `ProfileEditPage` extracted from `_ProfileEditDialog` (which is removed entirely). Avatar display logic in `avatar_badge.py` + `profile_card.py` switches from emoji text fallback to generic graphic placeholder. Runner/Review pages get clearer button labels. Profile-Picker container gets `setMaximumWidth(880)`.

**Tech Stack:** Python 3.11, PySide6, pytest. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-05-14-phase-12-ux-polish-design.md`

**Repository state at start:** master branch, latest commit `540e9ba` (Phase 12 spec). Test suite: 234/234 green.

---

## File Structure

**New files:**
- `src/school_test_engine/ui/pages/profile_edit.py` — `ProfileEditPage` (replaces `_ProfileEditDialog`)
- `tests/test_profile_edit_page.py` — unit tests for the new page

**Modified files:**
- `src/school_test_engine/ui/pages/runner.py` — rename "Pausieren" button to "Zurück zum Menü" + tooltip
- `src/school_test_engine/ui/pages/review.py` — add "Zurück zum Menü" button
- `src/school_test_engine/ui/widgets/avatar_badge.py` — replace emoji text fallback with generic placeholder
- `src/school_test_engine/ui/widgets/profile_card.py` — same placeholder logic
- `src/school_test_engine/ui/main_window.py` — register `profile_edit_page`, add `show_profile_edit()` method
- `src/school_test_engine/ui/pages/profile_manager.py` — remove `_ProfileEditDialog`, route via `show_profile_edit`
- `src/school_test_engine/ui/pages/profile_picker.py` — route "neues Profil" via `show_profile_edit`, set container `setMaximumWidth(880)`

---

## Task 1: Runner — rename "Pausieren" → "Zurück zum Menü"

**Files:**
- Modify: `src/school_test_engine/ui/pages/runner.py`

- [ ] **Step 1: Update button label + add tooltip**

In `src/school_test_engine/ui/pages/runner.py`, find the line (around 108):
```python
        self.abort_btn = QPushButton("Pausieren")
```

Replace with:
```python
        self.abort_btn = QPushButton("Zurück zum Menü")
        self.abort_btn.setToolTip(
            "Fortschritt wird gespeichert — du kannst später weitermachen"
        )
```

- [ ] **Step 2: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
uid = users_repo.create_user(c, 'X', '👤')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.active_user_id = uid
btn = w.runner_page.abort_btn
print('button label:', btn.text())
print('tooltip:', btn.toolTip())"
```

Expected:
```
button label: Zurück zum Menü
tooltip: Fortschritt wird gespeichert — du kannst später weitermachen
```

- [ ] **Step 3: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 234/234 still passing.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/pages/runner.py
git commit -m "feat(phase12): runner button 'Pausieren' → 'Zurück zum Menü' + tooltip"
```

---

## Task 2: Review-Page — add "Zurück zum Menü" button

**Files:**
- Modify: `src/school_test_engine/ui/pages/review.py`

- [ ] **Step 1: Read review.py current bottom button row**

The current code (around line 50-58) has:
```python
        back = QPushButton("← Weiter üben")
        back.clicked.connect(self._back_to_runner)
        bottom.addWidget(back)
        
        submit = QPushButton("Abgeben ✓")
        ...
```

- [ ] **Step 2: Insert "Zurück zum Menü" button**

Add a new button between `back` and `submit`. Insert this code right after `bottom.addWidget(back)`:

```python
        to_menu = QPushButton("← Zurück zum Menü")
        to_menu.setObjectName("text")
        to_menu.clicked.connect(self._back_to_menu)
        bottom.addWidget(to_menu)
```

Then add the handler method (alongside `_back_to_runner`):
```python
    def _back_to_menu(self) -> None:
        self.window.show_menu()
```

- [ ] **Step 3: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication, QPushButton
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
uid = users_repo.create_user(c, 'X', '👤')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.active_user_id = uid
btns = [b.text() for b in w.review_page.findChildren(QPushButton)]
print('review buttons:', btns)
assert '← Zurück zum Menü' in btns, 'missing menu button'
print('ok')"
```

Expected: prints button list containing `← Zurück zum Menü` + `ok`.

- [ ] **Step 4: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 234/234 still passing.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/pages/review.py
git commit -m "feat(phase12): review page adds 'Zurück zum Menü' button"
```

---

## Task 3: AvatarBadge — generic placeholder replaces emoji fallback

**Files:**
- Modify: `src/school_test_engine/ui/widgets/avatar_badge.py`

The current `AvatarBadge` is a `QLabel` that shows either a photo pixmap (if `image_bytes`) or the emoji text (if not). We'll replace the emoji-text fallback with a generic person-silhouette placeholder rendered as a styled QLabel.

- [ ] **Step 1: Read current avatar_badge.py**

The class structure:
- `__init__(emoji: str, image_bytes: bytes | None, diameter: int)` — constructor
- `set_avatar(*, emoji, image_bytes)` — updates display

Note: keep the `emoji` parameter in the constructor + `set_avatar` signature for backward compatibility (callers still pass it), but **ignore it** — always render placeholder if no image.

- [ ] **Step 2: Modify `set_avatar` logic**

Open `src/school_test_engine/ui/widgets/avatar_badge.py`. Find the `set_avatar` method. The existing logic looks roughly like:

```python
def set_avatar(self, *, emoji: str, image_bytes: bytes | None) -> None:
    if image_bytes:
        pm = QPixmap()
        if pm.loadFromData(image_bytes):
            self.setPixmap(round_pixmap(pm, self._diameter))
            self.setText("")
            return
    # Fallback: emoji
    self.setText(emoji)
    self.setFont(self._emoji_font)
```

Replace with:

```python
def set_avatar(self, *, emoji: str, image_bytes: bytes | None) -> None:
    # emoji parameter retained for backward-compat but ignored — Phase 12 uses
    # a generic graphic placeholder when no image is available.
    if image_bytes:
        pm = QPixmap()
        if pm.loadFromData(image_bytes):
            self.setPixmap(round_pixmap(pm, self._diameter))
            self.setText("")
            return
    # Generic placeholder: paper-tinted circle with person silhouette
    self._render_placeholder()


def _render_placeholder(self) -> None:
    """Render a generic person-silhouette placeholder inside the badge."""
    self.setText("👤")  # Unicode person silhouette as glyph (one consistent choice across the app)
    self.setFont(self._emoji_font)
    self.setStyleSheet(
        f"background: #f4efe6; color: #b3a98e; border-radius: {self._diameter // 2}px;"
    )
```

Note: The simplest "generic placeholder" implementation uses the Unicode person silhouette `👤` rendered in a muted grey color on a paper-50 background, with a circular shape. This avoids needing a new SVG asset while still being visually distinct from user-chosen emojis (which used colorful glyphs like 🧒). Save the `_diameter` value as an attribute in `__init__` if not already present.

If `_diameter` is not stored as `self._diameter` in `__init__`, add it. Find `__init__`:
```python
def __init__(self, *, emoji: str, image_bytes: bytes | None, diameter: int = 56, parent=None):
    super().__init__(parent)
    self._diameter = diameter   # <- ensure this is here
    self.setFixedSize(diameter, diameter)
    self.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._emoji_font = QFont()
    self._emoji_font.setPointSize(max(12, diameter // 2 - 4))
    self.set_avatar(emoji=emoji, image_bytes=image_bytes)
```

- [ ] **Step 3: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.ui.widgets.avatar_badge import AvatarBadge
# Without image_bytes → placeholder
a = AvatarBadge(emoji='🧒', image_bytes=None, diameter=56)
print('placeholder text:', repr(a.text()))  # should be '👤' (generic)
print('stylesheet contains background:', 'background:' in a.styleSheet())
print('ok')"
```

Expected:
```
placeholder text: '👤'
stylesheet contains background: True
ok
```

- [ ] **Step 4: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 234/234 still passing.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/widgets/avatar_badge.py
git commit -m "feat(phase12): AvatarBadge uses generic placeholder instead of emoji fallback"
```

---

## Task 4: ProfileCard — apply same placeholder logic

**Files:**
- Modify: `src/school_test_engine/ui/widgets/profile_card.py`

`ProfileCard` (used in Profile-Picker) shows an avatar at the top. It has similar logic to AvatarBadge but renders differently.

- [ ] **Step 1: Read profile_card.py avatar block**

Find the avatar-rendering block (around lines 40-60). It checks `image_bytes` first and falls back to displaying the `avatar` (emoji) string.

- [ ] **Step 2: Replace emoji fallback with placeholder**

In `profile_card.py`, find the part that displays the avatar (likely a QLabel with the emoji text). Replace the emoji fallback path with the same `👤` placeholder rendered in muted grey on paper background.

Specifically, find code like:
```python
if image_bytes:
    pm = QPixmap()
    pm.loadFromData(image_bytes)
    self.avatar_label.setPixmap(round_pixmap(pm, 96))
else:
    self.avatar_label.setText(avatar)
    self.avatar_label.setFont(QFont(...))
```

Replace the `else` branch with:
```python
else:
    # Phase 12: generic placeholder instead of emoji
    self.avatar_label.setText("👤")
    self.avatar_label.setFont(QFont("", 56))  # match existing size
    self.avatar_label.setStyleSheet(
        "background: #f4efe6; color: #b3a98e; border-radius: 48px;"
    )
```

Verify the existing font-size + border-radius numbers match the avatar's diameter in this file (typically 96px diameter → 48px radius). Read the file to confirm.

- [ ] **Step 3: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.ui.widgets.profile_card import ProfileCard
# Create card without image
card = ProfileCard(name='Test', avatar='🧒', image_bytes=None)
print('ok card created without image')"
```

Expected: prints `ok card created without image` without exception.

- [ ] **Step 4: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 234/234 still passing.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/ui/widgets/profile_card.py
git commit -m "feat(phase12): ProfileCard uses generic placeholder instead of emoji"
```

---

## Task 5: ProfileEditPage — new inline page replacing _ProfileEditDialog

**Files:**
- Create: `src/school_test_engine/ui/pages/profile_edit.py`
- Test: `tests/test_profile_edit_page.py`

This is the largest task in Phase 12. The new page must replicate ALL the form fields of the old `_ProfileEditDialog`:
- Name (required, QLineEdit)
- Avatar photo (QFileDialog upload + preview)
- Birthday (QDateEdit with clear-option)
- KI-Stil-Hinweis (Phase 8 — QPlainTextEdit)
- Schul-Kontext (Phase 9 — 5 fields: grade, school_type, bundesland, school_name, school_year)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_profile_edit_page.py`:

```python
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from school_test_engine.storage import connect, run_migrations, users_repo


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


class FakeWindow:
    def __init__(self, conn):
        self.conn = conn
        self.active_user_id = None
        self.shown = []  # records show_X calls

    def show_profile_picker(self):
        self.shown.append("picker")

    def show_profile_manager(self, return_to: str = "picker"):
        self.shown.append(f"manager({return_to})")

    def show_menu(self):
        self.shown.append("menu")


def test_create_mode_empty_fields(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    p = ProfileEditPage(FakeWindow(conn), conn)
    p.show_for(user_id=None, return_to="picker")
    assert p.name_edit.text() == ""


def test_edit_mode_loads_existing_user(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    uid = users_repo.create_user(conn, "Bestand", "👤")
    users_repo.update_user(conn, uid, ai_style_briefing="Mein Stil")
    p = ProfileEditPage(FakeWindow(conn), conn)
    p.show_for(user_id=uid, return_to="manager")
    assert p.name_edit.text() == "Bestand"
    assert p.style_edit.toPlainText() == "Mein Stil"


def test_save_create_mode_creates_user(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    win = FakeWindow(conn)
    p = ProfileEditPage(win, conn)
    p.show_for(user_id=None, return_to="picker")
    p.name_edit.setText("NeuerUser")
    p._save()
    users = users_repo.list_users(conn)
    assert any(u["name"] == "NeuerUser" for u in users)
    assert win.shown == ["picker"]


def test_save_edit_mode_updates_user(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    uid = users_repo.create_user(conn, "Alt", "👤")
    win = FakeWindow(conn)
    p = ProfileEditPage(win, conn)
    p.show_for(user_id=uid, return_to="manager")
    p.name_edit.setText("Neu")
    p._save()
    row = users_repo.get_user(conn, uid)
    assert row["name"] == "Neu"
    assert win.shown == ["manager(manager)"]


def test_save_empty_name_does_not_create(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    win = FakeWindow(conn)
    p = ProfileEditPage(win, conn)
    p.show_for(user_id=None, return_to="picker")
    p.name_edit.setText("   ")  # whitespace only
    # Save should be blocked — count users before/after
    n_before = len(users_repo.list_users(conn))
    p._save()
    n_after = len(users_repo.list_users(conn))
    assert n_after == n_before


def test_cancel_creates_nothing(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    win = FakeWindow(conn)
    p = ProfileEditPage(win, conn)
    p.show_for(user_id=None, return_to="picker")
    p.name_edit.setText("Cancelled")
    n_before = len(users_repo.list_users(conn))
    p._cancel()
    n_after = len(users_repo.list_users(conn))
    assert n_after == n_before
    assert win.shown == ["picker"]


def test_return_to_routes_correctly(app, conn):
    from school_test_engine.ui.pages.profile_edit import ProfileEditPage
    for target, expected in [("picker", "picker"), ("manager", "manager(manager)"), ("menu", "menu")]:
        win = FakeWindow(conn)
        p = ProfileEditPage(win, conn)
        p.show_for(user_id=None, return_to=target)
        p.name_edit.setText(f"User-{target}")
        p._save()
        assert win.shown == [expected], f"target={target}: got {win.shown}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_profile_edit_page.py -v`
Expected: All FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the ProfileEditPage module**

Create `src/school_test_engine/ui/pages/profile_edit.py`:

```python
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QDate, QIODevice, Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
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

from ...prompt_builder.school_context import BUNDESLAENDER, SCHOOL_TYPES
from ...storage import users_repo
from .._layouts import row_get
from ..design import Color, FontFamily, Semantic
from ..widgets.avatar_badge import AvatarBadge


def _pixmap_to_png_bytes(pm: QPixmap, max_dim: int = 256) -> bytes:
    if pm.width() > max_dim or pm.height() > max_dim:
        pm = pm.scaled(
            max_dim, max_dim,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pm.save(buf, "PNG")
    return bytes(ba.data())


class ProfileEditPage(QWidget):
    """Inline page for creating or editing a user profile. Replaces the old
    _ProfileEditDialog from Phase 6+."""

    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._user_id: int | None = None
        self._return_to: str = "picker"
        self._avatar_image: bytes | None = None
        self._birthday_set: bool = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(48, 36, 48, 36)
        layout.setSpacing(14)

        # Header
        head = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(self._cancel)
        head.addWidget(back)
        head.addStretch(1)
        self.save_btn = QPushButton("Speichern")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        head.addWidget(self.save_btn)
        layout.addLayout(head)

        eyebrow = QLabel("PROFIL")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)

        self.title_label = QLabel("Neues Profil")
        self.title_label.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        layout.addWidget(self.title_label)

        # Avatar block
        avatar_row = QHBoxLayout()
        avatar_row.setSpacing(16)
        self.avatar_preview = AvatarBadge(emoji="👤", image_bytes=None, diameter=96)
        avatar_row.addWidget(self.avatar_preview)
        avatar_buttons = QVBoxLayout()
        upload = QPushButton("Foto auswählen…")
        upload.setObjectName("text")
        upload.clicked.connect(self._upload_photo)
        avatar_buttons.addWidget(upload)
        self.remove_photo_btn = QPushButton("Foto entfernen")
        self.remove_photo_btn.setObjectName("text")
        self.remove_photo_btn.clicked.connect(self._remove_photo)
        self.remove_photo_btn.setVisible(False)
        avatar_buttons.addWidget(self.remove_photo_btn)
        avatar_buttons.addStretch(1)
        avatar_row.addLayout(avatar_buttons, 1)
        layout.addLayout(avatar_row)

        # Form
        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("z. B. Clemens")
        form.addRow("Name:", self.name_edit)

        self.birthday_edit = QDateEdit()
        self.birthday_edit.setCalendarPopup(True)
        self.birthday_edit.setDisplayFormat("dd.MM.yyyy")
        self.birthday_edit.setDate(QDate(1900, 1, 1))
        clear_bd = QPushButton("löschen")
        clear_bd.setObjectName("text")
        clear_bd.clicked.connect(self._clear_birthday)
        bd_row = QHBoxLayout()
        bd_row.addWidget(self.birthday_edit, 1)
        bd_row.addWidget(clear_bd)
        form.addRow("Geburtstag:", bd_row)

        layout.addLayout(form)

        # Style-Briefing (Phase 8)
        style_label = QLabel("KI-Stil-Hinweis (optional)")
        style_label.setStyleSheet("color: #4a4538; font-weight: 500; padding-top: 8px;")
        layout.addWidget(style_label)
        self.style_edit = QPlainTextEdit()
        self.style_edit.setPlaceholderText(
            "z. B.: Schreibstil: Du-Form, freundlich.\n"
            "Mathe: saubere Äquivalenzumformungen in der Erklärung."
        )
        self.style_edit.setMaximumHeight(110)
        layout.addWidget(self.style_edit)

        # Schul-Kontext (Phase 9)
        ctx_label = QLabel("Schul-Kontext")
        ctx_label.setStyleSheet("color: #4a4538; font-weight: 500; padding-top: 8px;")
        layout.addWidget(ctx_label)

        ctx_form = QFormLayout()
        ctx_form.setSpacing(8)

        self.grade_combo = QComboBox()
        self.grade_combo.addItem("—", None)
        for g in range(5, 14):
            self.grade_combo.addItem(f"Klasse {g}", g)
        ctx_form.addRow("Klassenstufe:", self.grade_combo)

        self.school_type_combo = QComboBox()
        self.school_type_combo.addItem("—", None)
        for st in SCHOOL_TYPES:
            self.school_type_combo.addItem(st, st)
        self.school_type_combo.addItem("Andere…", "__OTHER__")
        self.school_type_combo.activated.connect(self._on_school_type_activated)
        ctx_form.addRow("Schultyp:", self.school_type_combo)

        self.bundesland_combo = QComboBox()
        self.bundesland_combo.addItem("—", None)
        for bl in BUNDESLAENDER:
            self.bundesland_combo.addItem(bl, bl)
        self.bundesland_combo.addItem("Andere…", "__OTHER__")
        self.bundesland_combo.activated.connect(self._on_bundesland_activated)
        ctx_form.addRow("Bundesland:", self.bundesland_combo)

        self.school_name_edit = QLineEdit()
        self.school_name_edit.setPlaceholderText("z. B. Heinrich-Heine-Realschule")
        ctx_form.addRow("Schul-Name:", self.school_name_edit)

        self.school_year_edit = QLineEdit()
        self.school_year_edit.setPlaceholderText("2025/26")
        ctx_form.addRow("Schuljahr:", self.school_year_edit)

        layout.addLayout(ctx_form)

        # Footer: Delete (visible only in edit mode)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.delete_btn = QPushButton("Löschen")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete)
        self.delete_btn.setVisible(False)
        footer.addWidget(self.delete_btn)
        layout.addLayout(footer)

        layout.addStretch(1)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def show_for(self, user_id: int | None = None, return_to: str = "picker") -> None:
        self._user_id = user_id
        self._return_to = return_to
        self._reset_fields()
        if user_id is None:
            self.title_label.setText("Neues Profil")
            self.delete_btn.setVisible(False)
        else:
            self.title_label.setText("Profil bearbeiten")
            self.delete_btn.setVisible(True)
            self._load_user(user_id)

    def _reset_fields(self) -> None:
        self.name_edit.setText("")
        self._avatar_image = None
        self.avatar_preview.set_avatar(emoji="👤", image_bytes=None)
        self.remove_photo_btn.setVisible(False)
        self._birthday_set = False
        self.birthday_edit.setDate(QDate(1900, 1, 1))
        self.style_edit.setPlainText("")
        self.grade_combo.setCurrentIndex(0)
        self.school_type_combo.setCurrentIndex(0)
        self.bundesland_combo.setCurrentIndex(0)
        self.school_name_edit.setText("")
        self.school_year_edit.setText("")

    def _load_user(self, user_id: int) -> None:
        u = users_repo.get_user(self.conn, user_id)
        if u is None:
            return
        self.name_edit.setText(u["name"] or "")
        self._avatar_image = row_get(u, "avatar_image")
        self.avatar_preview.set_avatar(emoji="👤", image_bytes=self._avatar_image)
        self.remove_photo_btn.setVisible(self._avatar_image is not None)
        bd = row_get(u, "birthday")
        if bd:
            try:
                d = datetime.fromisoformat(bd).date()
                self.birthday_edit.setDate(QDate(d.year, d.month, d.day))
                self._birthday_set = True
            except ValueError:
                pass
        briefing = row_get(u, "ai_style_briefing")
        if briefing:
            self.style_edit.setPlainText(briefing)
        grade = row_get(u, "grade")
        if grade is not None:
            idx = self.grade_combo.findData(int(grade))
            if idx >= 0:
                self.grade_combo.setCurrentIndex(idx)
        st = row_get(u, "school_type")
        if st:
            idx = self.school_type_combo.findData(st)
            if idx >= 0:
                self.school_type_combo.setCurrentIndex(idx)
            else:
                last_idx = self.school_type_combo.count() - 1
                self.school_type_combo.insertItem(last_idx, st, st)
                self.school_type_combo.setCurrentIndex(last_idx)
        bl = row_get(u, "bundesland")
        if bl:
            idx = self.bundesland_combo.findData(bl)
            if idx >= 0:
                self.bundesland_combo.setCurrentIndex(idx)
            else:
                last_idx = self.bundesland_combo.count() - 1
                self.bundesland_combo.insertItem(last_idx, bl, bl)
                self.bundesland_combo.setCurrentIndex(last_idx)
        sn = row_get(u, "school_name")
        if sn:
            self.school_name_edit.setText(sn)
        sy = row_get(u, "school_year")
        if sy:
            self.school_year_edit.setText(sy)

    # ------------------------------------------------------------------
    # Field helpers
    # ------------------------------------------------------------------

    def _upload_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Foto auswählen", "", "Bilder (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return
        pm = QPixmap(path)
        if pm.isNull():
            QMessageBox.warning(self, "Fehler", "Bild konnte nicht geladen werden.")
            return
        self._avatar_image = _pixmap_to_png_bytes(pm)
        self.avatar_preview.set_avatar(emoji="👤", image_bytes=self._avatar_image)
        self.remove_photo_btn.setVisible(True)

    def _remove_photo(self) -> None:
        self._avatar_image = None
        self.avatar_preview.set_avatar(emoji="👤", image_bytes=None)
        self.remove_photo_btn.setVisible(False)

    def _clear_birthday(self) -> None:
        self._birthday_set = False
        self.birthday_edit.blockSignals(True)
        self.birthday_edit.setDate(QDate(1900, 1, 1))
        self.birthday_edit.blockSignals(False)

    def _on_school_type_activated(self, idx: int) -> None:
        self._handle_other_trigger(
            self.school_type_combo, idx, "Schultyp eingeben", "Eigener Schultyp:"
        )

    def _on_bundesland_activated(self, idx: int) -> None:
        self._handle_other_trigger(
            self.bundesland_combo, idx, "Bundesland eingeben", "Eigenes Bundesland:"
        )

    def _handle_other_trigger(self, combo: QComboBox, idx: int, title: str, label: str) -> None:
        if combo.itemData(idx) != "__OTHER__":
            return
        text, ok = QInputDialog.getText(self, title, label)
        text = text.strip() if ok else ""
        if not text:
            combo.setCurrentIndex(0)
            return
        last_idx = combo.count() - 1
        existing = combo.findData(text)
        if existing >= 0:
            combo.setCurrentIndex(existing)
            return
        combo.insertItem(last_idx, text, text)
        combo.setCurrentIndex(last_idx)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _save(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Name fehlt", "Bitte einen Namen vergeben.")
            return

        birthday = None
        if self._birthday_set:
            d = self.birthday_edit.date()
            if d.year() > 1900:
                birthday = d.toString("yyyy-MM-dd")

        style_text = self.style_edit.toPlainText().strip() or None
        grade_val = self.grade_combo.currentData()
        school_type_val = self.school_type_combo.currentData()
        if school_type_val == "__OTHER__":
            school_type_val = None
        bundesland_val = self.bundesland_combo.currentData()
        if bundesland_val == "__OTHER__":
            bundesland_val = None
        school_name_val = self.school_name_edit.text().strip() or None
        school_year_val = self.school_year_edit.text().strip() or None

        if self._user_id is None:
            # Create new user (with default avatar emoji — column stays for backward compat)
            new_uid = users_repo.create_user(
                self.conn, name, "👤",
                avatar_image=self._avatar_image,
                birthday=birthday,
            )
            users_repo.update_user(
                self.conn, new_uid,
                ai_style_briefing=style_text,
                grade=grade_val,
                school_type=school_type_val,
                bundesland=bundesland_val,
                school_name=school_name_val,
                school_year=school_year_val,
            )
        else:
            users_repo.update_user(
                self.conn, self._user_id,
                name=name,
                avatar_image=self._avatar_image,
                birthday=birthday,
                ai_style_briefing=style_text,
                grade=grade_val,
                school_type=school_type_val,
                bundesland=bundesland_val,
                school_name=school_name_val,
                school_year=school_year_val,
            )
            if self.window.active_user_id == self._user_id and hasattr(self.window, "user_changed"):
                self.window.user_changed.emit(self._user_id)

        self._navigate_back()

    def _cancel(self) -> None:
        self._navigate_back()

    def _delete(self) -> None:
        if self._user_id is None:
            return
        if self.window.active_user_id == self._user_id:
            QMessageBox.information(
                self, "Aktives Profil",
                "Du kannst das aktive Profil nicht löschen. Wechsle zuerst.",
            )
            return
        reply = QMessageBox.question(
            self, "Profil löschen?",
            f"Profil und alle zugehörigen Daten endgültig löschen?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        users_repo.delete_user(self.conn, self._user_id)
        self._navigate_back()

    def _navigate_back(self) -> None:
        target = self._return_to
        if target == "manager":
            self.window.show_profile_manager("manager")
        elif target == "menu":
            self.window.show_menu()
        else:
            self.window.show_profile_picker()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_profile_edit_page.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 241/241 passing (234 + 7 new).

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/pages/profile_edit.py tests/test_profile_edit_page.py
git commit -m "feat(phase12): ProfileEditPage replaces _ProfileEditDialog as inline page"
```

---

## Task 6: MainWindow — register ProfileEditPage + show_profile_edit method

**Files:**
- Modify: `src/school_test_engine/ui/main_window.py`

- [ ] **Step 1: Add import + page instance + navigation method**

In `src/school_test_engine/ui/main_window.py`:

Add import near other page imports:
```python
from .pages.profile_edit import ProfileEditPage
```

After existing page instances in `__init__`, add:
```python
        self.profile_edit_page = ProfileEditPage(self, conn)
```

Add `self.profile_edit_page` to the stack-registration tuple (the `for page in (...):` loop).

Add navigation method after `show_profile_manager`:
```python
    def show_profile_edit(self, user_id: int | None = None, return_to: str = "picker") -> None:
        self.profile_edit_page.show_for(user_id, return_to)
        self.stack.setCurrentWidget(self.profile_edit_page)
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
print('has show_profile_edit:', hasattr(w, 'show_profile_edit'))
print('stack count:', w.stack.count())
w.show_profile_edit()
print('routed to edit page:', w.stack.currentWidget() is w.profile_edit_page)"
```

Expected:
```
has show_profile_edit: True
stack count: 14
routed to edit page: True
```

- [ ] **Step 3: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 241/241 passing.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/main_window.py
git commit -m "feat(phase12): MainWindow registers ProfileEditPage + show_profile_edit method"
```

---

## Task 7: ProfileManager + ProfilePicker route via show_profile_edit; remove _ProfileEditDialog

**Files:**
- Modify: `src/school_test_engine/ui/pages/profile_manager.py`
- Modify: `src/school_test_engine/ui/pages/profile_picker.py`

- [ ] **Step 1: Modify ProfileManagerPage._create + _edit**

In `src/school_test_engine/ui/pages/profile_manager.py`:

Replace the `_create` method body with:
```python
    def _create(self) -> None:
        self.window.show_profile_edit(user_id=None, return_to="manager")
```

Replace the `_edit(user_id)` method body with:
```python
    def _edit(self, user_id: int) -> None:
        self.window.show_profile_edit(user_id=user_id, return_to="manager")
```

- [ ] **Step 2: Remove _ProfileEditDialog class**

In the same file, delete the entire `_ProfileEditDialog` class. Also remove the `_pixmap_to_png_bytes` helper if it's only used by `_ProfileEditDialog` (verify with `grep _pixmap_to_png_bytes src/`).

Also remove now-unused imports (e.g. `QInputDialog`, `QFileDialog`, `QPlainTextEdit`, `QDateEdit`, `QComboBox`, etc. if they're only used by the deleted dialog). Use Read + Edit to safely prune imports.

Remove the `ProfileValues` dataclass if it's only used by `_ProfileEditDialog`.

Remove the `BUNDESLAENDER`, `SCHOOL_TYPES`, `COMMON_AVATARS` imports/usage if exclusive to the deleted dialog.

- [ ] **Step 3: Modify ProfilePickerPage "Neues Profil" tile**

In `src/school_test_engine/ui/pages/profile_picker.py`, find the "Neues Profil" or `+`-tile click handler (it likely calls `self.window.show_profile_manager()` or similar). Replace its click handler with:

```python
        self.window.show_profile_edit(user_id=None, return_to="picker")
```

(The exact location depends on file structure — search for `Neues Profil` or `"+"` literals in the picker code.)

- [ ] **Step 4: Smoke test**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
users_repo.create_user(c, 'Test', '👤')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
# Verify _ProfileEditDialog no longer exists
try:
    from school_test_engine.ui.pages.profile_manager import _ProfileEditDialog
    print('FAIL: _ProfileEditDialog still exists')
except ImportError:
    print('OK: _ProfileEditDialog removed')
# Verify _create / _edit route to show_profile_edit
w.show_profile_manager()
print('ok manager loaded')"
```

Expected:
```
OK: _ProfileEditDialog removed
ok manager loaded
```

- [ ] **Step 5: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 241/241 passing.

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/pages/profile_manager.py src/school_test_engine/ui/pages/profile_picker.py
git commit -m "feat(phase12): route profile-edit via show_profile_edit; remove _ProfileEditDialog"
```

---

## Task 8: Profile-Picker container max-width 880

**Files:**
- Modify: `src/school_test_engine/ui/pages/profile_picker.py`

- [ ] **Step 1: Add max-width constraint**

In `src/school_test_engine/ui/pages/profile_picker.py`, find where the FlowLayout container is created (the QWidget that holds the cards). Add:

```python
        grid_container.setMaximumWidth(880)
```

(Replace `grid_container` with whatever the actual variable is named — verify by reading the file. It should be a QWidget that has the FlowLayout applied to it via `FlowLayout(grid_container, ...)`.)

- [ ] **Step 2: Smoke test with multiple users**

Run:
```bash
QT_QPA_PLATFORM=offscreen python -c "
from PySide6.QtWidgets import QApplication
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo
c = connect(':memory:')
run_migrations(c)
# Create 7 users to test wrapping
for n in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
    users_repo.create_user(c, n, '👤')
from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.show_profile_picker()
# Find the FlowLayout container
from school_test_engine.ui.widgets.flow_layout import FlowLayout
from PySide6.QtWidgets import QWidget
containers = [c for c in w.profile_picker_page.findChildren(QWidget) if c.maximumWidth() == 880]
print('containers with max-width 880:', len(containers))
assert len(containers) >= 1, 'expected one container with maximumWidth=880'
print('ok')"
```

Expected: prints `containers with max-width 880: 1` + `ok`.

- [ ] **Step 3: Run full suite**

Run: `pytest -v 2>&1 | tail -3`
Expected: 241/241 passing.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/pages/profile_picker.py
git commit -m "feat(phase12): Profile-Picker container max-width 880px (max 3 cards/row)"
```

---

## Task 9: End-to-end smoke + acceptance audit

**Files:** none — audit only.

- [ ] **Step 1: Run comprehensive smoke script**

Run:
```bash
QT_QPA_PLATFORM=offscreen python <<'EOF'
from PySide6.QtWidgets import QApplication, QPushButton, QWidget
app = QApplication([])
from school_test_engine.storage import connect, run_migrations, users_repo

# AC1+AC2: Navigation buttons
c = connect(':memory:')
run_migrations(c)
uid = users_repo.create_user(c, 'Clemens', '👤')

from school_test_engine.ui.main_window import MainWindow
w = MainWindow(c)
w.active_user_id = uid

# AC1: Runner button "Zurück zum Menü"
btn = w.runner_page.abort_btn
assert btn.text() == "Zurück zum Menü"
assert "gespeichert" in btn.toolTip().lower()
print("AC1: runner button label =", btn.text())

# AC2: Review page has menu button
review_btns = [b.text() for b in w.review_page.findChildren(QPushButton)]
assert "← Zurück zum Menü" in review_btns
print("AC2: review page has menu button =", "← Zurück zum Menü" in review_btns)

# AC3: ProfileEditPage exists
assert hasattr(w, 'profile_edit_page')
assert hasattr(w, 'show_profile_edit')
print("AC3: ProfileEditPage in stack")

# AC4: show_profile_edit routes correctly
w.show_profile_edit(user_id=None, return_to="picker")
assert w.stack.currentWidget() is w.profile_edit_page
print("AC4: show_profile_edit routes to ProfileEditPage")

# AC5: ProfileEditPage has NO emoji tile selection (just verify no AvatarTile widgets)
from school_test_engine.ui.widgets.avatar_tile import AvatarTile
avatar_tiles = w.profile_edit_page.findChildren(AvatarTile)
assert len(avatar_tiles) == 0, f"Expected 0 AvatarTile widgets, got {len(avatar_tiles)}"
print(f"AC5: ProfileEditPage has 0 AvatarTile widgets (was 12 in dialog)")

# AC6: _ProfileEditDialog removed
try:
    from school_test_engine.ui.pages.profile_manager import _ProfileEditDialog
    print("AC6: FAIL — _ProfileEditDialog still exists")
except ImportError:
    print("AC6: _ProfileEditDialog removed from profile_manager module")

# AC7: Avatar placeholder for profiles without image
from school_test_engine.ui.widgets.avatar_badge import AvatarBadge
ab = AvatarBadge(emoji='🧒', image_bytes=None, diameter=56)
assert ab.text() == "👤", f"Expected generic placeholder, got {ab.text()!r}"
print(f"AC7: AvatarBadge without image renders generic '{ab.text()}' (not emoji)")

# AC8: Profile-Picker container max-width 880
w.show_profile_picker()
containers_880 = [
    child for child in w.profile_picker_page.findChildren(QWidget)
    if child.maximumWidth() == 880
]
assert len(containers_880) >= 1
print(f"AC8: Profile-Picker has container with maxWidth=880 ({len(containers_880)} found)")

print("\n=== ALL PHASE 12 ACCEPTANCE CRITERIA VERIFIED ===")
EOF
```

Expected: prints `ALL PHASE 12 ACCEPTANCE CRITERIA VERIFIED`.

- [ ] **Step 2: Run full pytest suite**

Run: `pytest -v 2>&1 | tail -5`
Expected: all tests green; new test count = 234 + 7 (ProfileEditPage) = 241 minimum.

- [ ] **Step 3: Acceptance audit summary**

Walk each spec acceptance criterion:

1. ✅ Runner button = "Zurück zum Menü" + tooltip — Task 1 + smoke AC1
2. ✅ Review page has "Zurück zum Menü" — Task 2 + smoke AC2
3. ✅ ProfileEditPage in stack — Task 5+6 + smoke AC3
4. ✅ Profile-Manager + Picker route via show_profile_edit — Task 7
5. ✅ Profile-Picker "Neues Profil" routes via show_profile_edit — Task 7
6. ✅ _ProfileEditDialog removed — Task 7 + smoke AC6
7. ✅ ProfileEditPage has no emoji tile selection — smoke AC5
8. ✅ AvatarBadge + ProfileCard render generic placeholder — Tasks 3+4 + smoke AC7
9. ✅ Profile-Picker container max-width 880 — Task 8 + smoke AC8
10. ✅ Tests grün (234 + 7 = 241) — smoke + pytest

- [ ] **Step 4: No commit needed for Task 9** (audit only). If small polish:

```bash
git add -A
git commit -m "fix(phase12): smoke-test polish"
```

---

## Self-Review

**Spec coverage:**
- §3.1 Navigation-Fixes → Tasks 1, 2 ✓
- §3.2 ProfileEditPage → Task 5 ✓
- §3.3 MainWindow integration → Task 6 ✓
- §3.4 ProfileManager refactoring → Task 7 ✓
- §3.5 Avatar placeholder → Tasks 3, 4 ✓
- §3.6 Profile-Picker max-width → Task 8 ✓
- §4 Tests → Task 5 (7 pytest tests) + Task 9 (smoke)
- §5 10 Akzeptanzkriterien → Task 9 audit walks them
- §7 Risiken — Avatar single-source-of-truth via avatar_badge.py + profile_card.py (Tasks 3+4); ProfileEditPage field-completeness verified in Task 5 (all fields from old dialog explicitly copied)

**Placeholder scan:** No TBDs. Every step has runnable code or commands.

**Type consistency:**
- `ProfileEditPage(window, conn)` + `show_for(user_id, return_to)` — same signature in Tasks 5, 6, 7
- `window.show_profile_edit(user_id=None, return_to="picker")` — same in Tasks 6, 7
- `AvatarBadge(emoji, image_bytes, diameter)` — emoji parameter kept for backward compat
- Avatar placeholder uses `"👤"` Unicode glyph + paper background — consistent across Tasks 3, 4

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-14-phase-12-ux-polish.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task + review checkpoints.

**2. Inline Execution** — Batch execution with checkpoints.

Which approach?

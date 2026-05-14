# Phase 13 — Design-System Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the UI to "alles aus einem Guss" — convert the last two modal dialogs to inline pages, strip emoji from UI chrome, enforce three button styles consistently, and replace the OS-color-emoji avatar placeholder with a static SVG.

**Architecture:** Pure UI-refactoring. No data model, repo, or migration changes. Two new `QWidget`-based pages parallel to Phase 12's `ProfileEditPage`. One new SVG asset. Mechanical objectName audit across all `QPushButton` instances.

**Tech Stack:** PySide6 (Qt6), Python 3.12, SQLite, pytest, `QT_QPA_PLATFORM=offscreen` for headless tests.

**Spec:** `docs/superpowers/specs/2026-05-14-phase-13-design-consolidation-design.md`

---

## File Structure

### Created
- `assets/avatar-placeholder.svg` — static person silhouette
- `src/school_test_engine/ui/pages/event_edit.py` — `EventEditPage` (replaces `EventDialog`)
- `src/school_test_engine/ui/pages/assessment_edit.py` — `AssessmentEditPage` + `_GradeSelector` (replaces `AssessmentDialog`)
- `tests/test_event_edit_page.py` — page tests
- `tests/test_assessment_edit_page.py` — page tests

### Modified
- `src/school_test_engine/ui/widgets/avatar_badge.py` — render SVG fallback
- `src/school_test_engine/ui/widgets/profile_card.py` — render SVG fallback
- `src/school_test_engine/ui/main_window.py` — wire new pages + `show_event_edit` / `show_assessment_edit`
- `src/school_test_engine/ui/pages/events.py` — call new page instead of dialog
- `src/school_test_engine/ui/pages/grades.py` — call new page instead of dialog
- `src/school_test_engine/ui/pages/menu.py` — strip emoji from top-bar + hamburger + call new page
- `src/school_test_engine/ui/pages/prompt_builder.py` — strip emoji from copy-btn + output-header
- `src/school_test_engine/ui/widgets/exam_card.py` — strip emoji from `Test bauen`
- `src/school_test_engine/ui/pages/history.py` — strip emoji from CSV-export, add objectName
- `src/school_test_engine/ui/pages/runner.py` — strip emoji from `Markieren`, add objectNames
- `src/school_test_engine/ui/pages/review.py` — add objectNames
- `src/school_test_engine/ui/pages/results.py` — add objectNames
- `src/school_test_engine/ui/pages/library.py` — add objectNames
- `src/school_test_engine/ui/pages/gaps.py` — add objectName
- `src/school_test_engine/ui/pages/import_wizard.py` — add objectName
- `src/school_test_engine/ui/pages/profile_manager.py` — add objectNames
- `src/school_test_engine/ui/widgets/daily_card.py` — add objectName
- `src/school_test_engine/ui/style.qss` — top comment with button convention

### Deleted
- `src/school_test_engine/ui/dialogs/event_dialog.py`
- `src/school_test_engine/ui/dialogs/assessment_dialog.py`

---

## Task Overview

1. Add avatar-placeholder SVG asset
2. AvatarBadge + ProfileCard render SVG instead of emoji
3. Create `EventEditPage`
4. Create `AssessmentEditPage` (with `_GradeSelector`)
5. Wire pages into MainWindow + migrate Events callsites
6. Migrate Grades + Menu callsites
7. Delete old dialog files
8. Strip emoji from UI chrome (top-bar, hamburger, prompt_builder, exam_card, history, runner)
9. Button-style audit across remaining pages
10. Document button convention in style.qss + smoke test
11. Final commit + acceptance check

---

### Task 1: Add avatar-placeholder SVG asset

**Files:**
- Create: `assets/avatar-placeholder.svg`

- [ ] **Step 1: Verify asset directory exists**

Run: `ls /home/matthias/Dokumente/Claude/ai-projects/school-test-engine/assets/`
Expected: shows `logomark.svg` (and possibly others). The directory exists.

- [ ] **Step 2: Create the SVG**

Write `assets/avatar-placeholder.svg`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="50" fill="#f4efe6"/>
  <circle cx="50" cy="38" r="14" fill="#b3a98e"/>
  <path d="M22 88 Q22 64 50 64 Q78 64 78 88 Z" fill="#b3a98e"/>
</svg>
```

- [ ] **Step 3: Verify SVG is well-formed**

Run: `python3 -c "from xml.etree import ElementTree; ElementTree.parse('/home/matthias/Dokumente/Claude/ai-projects/school-test-engine/assets/avatar-placeholder.svg'); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add assets/avatar-placeholder.svg
git commit -m "feat(phase13): add avatar-placeholder SVG asset"
```

---

### Task 2: AvatarBadge + ProfileCard render SVG instead of emoji

**Files:**
- Modify: `src/school_test_engine/ui/widgets/avatar_badge.py`
- Modify: `src/school_test_engine/ui/widgets/profile_card.py`
- Test: extend `tests/test_responsive.py` (or wherever AvatarBadge already smoke-tests; if no existing test for avatar, write a new one inline)

- [ ] **Step 1: Write the failing test**

Create `tests/test_avatar_placeholder.py`:

```python
"""Phase 13: AvatarBadge and ProfileCard render the SVG placeholder
instead of OS-color-emoji when no image is set."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from school_test_engine.ui.widgets.avatar_badge import AvatarBadge
from school_test_engine.ui.widgets.profile_card import ProfileCard


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_avatar_badge_placeholder_renders_pixmap_not_text():
    _ensure_app()
    badge = AvatarBadge(emoji="ignored", image_bytes=None, diameter=64)
    # Phase 13: placeholder is rendered as pixmap from SVG, not text
    assert badge.text() == ""
    pm = badge.pixmap()
    assert pm is not None and not pm.isNull(), "AvatarBadge placeholder must be a pixmap"


def test_avatar_badge_with_image_still_works():
    _ensure_app()
    # 1x1 transparent PNG
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c63000100000005000100"
        "0d0a2db40000000049454e44ae426082"
    )
    badge = AvatarBadge(emoji="ignored", image_bytes=png_bytes, diameter=64)
    assert badge.text() == ""
    pm = badge.pixmap()
    assert pm is not None and not pm.isNull()


def test_profile_card_placeholder_renders_pixmap_not_text():
    _ensure_app()
    card = ProfileCard(avatar="ignored", name="Test", meta=None, image_bytes=None)
    # Walk children to find the avatar QLabel — first QLabel with fixed height 90
    from PySide6.QtWidgets import QLabel
    avatar_lbl = None
    for child in card.findChildren(QLabel):
        if child.height() == 90 or child.minimumHeight() == 90 or child.maximumHeight() == 90:
            avatar_lbl = child
            break
        # Fallback: first QLabel with no objectName starting with "profileCard"
        if not child.objectName().startswith("profileCard"):
            avatar_lbl = child
            break
    assert avatar_lbl is not None, "could not find avatar label in ProfileCard"
    assert avatar_lbl.text() == "", "Phase 13: avatar label must not render emoji text"
    pm = avatar_lbl.pixmap()
    assert pm is not None and not pm.isNull(), "ProfileCard placeholder must be a pixmap"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_avatar_placeholder.py -v`
Expected: 3 failures (badge text is `"\U0001f464"`, not `""`).

- [ ] **Step 3: Modify AvatarBadge to render SVG**

Replace the whole file `src/school_test_engine/ui/widgets/avatar_badge.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPixmap, QPixmapCache
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QWidget

from ..design import Semantic


PLACEHOLDER_SVG_PATH = (
    Path(__file__).resolve().parents[3].parent / "assets" / "avatar-placeholder.svg"
)


class AvatarBadge(QLabel):
    """Rundes Avatar — Foto wenn vorhanden, sonst SVG-Silhouette.

    Bytes werden über QPixmapCache gecacht (Schlüssel = sha1+Durchmesser),
    damit derselbe Avatar an mehreren Stellen (Chip, Liste, Picker) nicht
    bei jedem Rerender neu dekodiert wird. Der SVG-Placeholder wird ebenfalls
    pro Durchmesser einmal in den Cache gerendert.
    """

    def __init__(
        self,
        *,
        emoji: str,
        image_bytes: bytes | None = None,
        diameter: int = 56,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background: transparent; "
            f"border: 1px solid {Semantic.BORDER}; "
            f"border-radius: {diameter // 2}px;"
        )
        self.set_avatar(emoji=emoji, image_bytes=image_bytes)

    def set_avatar(self, *, emoji: str, image_bytes: bytes | None) -> None:
        # Phase 13: emoji parameter retained for backward compat but ignored.
        # Display SVG-silhouette placeholder when no image.
        if image_bytes:
            pm = _cached_round_pixmap(image_bytes, self._diameter - 4)
            if pm is not None:
                self.setPixmap(pm)
                self.setText("")
                return
        self._render_placeholder()

    def _render_placeholder(self) -> None:
        self.clear()
        pm = _cached_placeholder_pixmap(self._diameter)
        self.setPixmap(pm)
        self.setStyleSheet(
            f"background: transparent; border-radius: {self._diameter // 2}px;"
        )


def round_pixmap(pm: QPixmap, diameter: int) -> QPixmap:
    target = QPixmap(diameter, diameter)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addEllipse(0, 0, diameter, diameter)
    painter.setClipPath(path)
    src = pm.scaled(
        diameter, diameter,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = (diameter - src.width()) // 2
    y = (diameter - src.height()) // 2
    painter.drawPixmap(QRect(x, y, src.width(), src.height()), src)
    painter.end()
    return target


def _cached_round_pixmap(image_bytes: bytes, diameter: int) -> QPixmap | None:
    digest = hashlib.sha1(image_bytes).hexdigest()[:16]
    key = f"avatar:{digest}:{diameter}"
    cached = QPixmapCache.find(key)
    if cached is not None:
        return cached
    pm = QPixmap()
    if not pm.loadFromData(image_bytes):
        return None
    rounded = round_pixmap(pm, diameter)
    QPixmapCache.insert(key, rounded)
    return rounded


def _cached_placeholder_pixmap(diameter: int) -> QPixmap:
    key = f"avatar-placeholder:{diameter}"
    cached = QPixmapCache.find(key)
    if cached is not None:
        return cached
    pm = QPixmap(diameter, diameter)
    pm.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(str(PLACEHOLDER_SVG_PATH))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    QPixmapCache.insert(key, pm)
    return pm
```

- [ ] **Step 4: Modify ProfileCard to render SVG**

In `src/school_test_engine/ui/widgets/profile_card.py`, replace the avatar-fallback block (lines 48–54). Find:

```python
        if not avatar_lbl.pixmap():
            # Phase 12: generic placeholder instead of emoji (avatar param ignored)
            avatar_lbl.setText("\U0001f464")
            big = QFont(); big.setPointSize(48); avatar_lbl.setFont(big)
            avatar_lbl.setStyleSheet(
                "background: #f4efe6; color: #b3a98e; border-radius: 42px;"
            )
```

Replace with:

```python
        if not avatar_lbl.pixmap():
            # Phase 13: SVG placeholder instead of OS-color-emoji
            from .avatar_badge import _cached_placeholder_pixmap
            avatar_lbl.setPixmap(_cached_placeholder_pixmap(84))
            avatar_lbl.setStyleSheet("background: transparent; border-radius: 42px;")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_avatar_placeholder.py -v`
Expected: 3 passes.

- [ ] **Step 6: Run full test suite to catch regressions**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q`
Expected: all green (≥241 + 3 new). If anything in profile_picker / profile_edit / menu tests breaks because they assert `text() == "\U0001f464"`, update those assertions to check `pixmap() is not None` instead.

- [ ] **Step 7: Commit**

```bash
git add tests/test_avatar_placeholder.py \
        src/school_test_engine/ui/widgets/avatar_badge.py \
        src/school_test_engine/ui/widgets/profile_card.py
git commit -m "feat(phase13): SVG avatar placeholder instead of color-emoji"
```

---

### Task 3: Create EventEditPage

**Files:**
- Create: `src/school_test_engine/ui/pages/event_edit.py`
- Test: `tests/test_event_edit_page.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_event_edit_page.py`:

```python
"""Phase 13: EventEditPage is the inline-page replacement for EventDialog."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.storage import events_repo, users_repo
from school_test_engine.storage.migrator import migrate


@pytest.fixture(scope="module")
def app():
    inst = QApplication.instance() or QApplication([])
    return inst


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    migrate(c)
    yield c
    c.close()


class _StubWindow:
    def __init__(self, conn):
        self.conn = conn
        self.active_user_id: int | None = None
        self.navigated_to: str | None = None

    def show_events(self):
        self.navigated_to = "events"

    def show_menu(self):
        self.navigated_to = "menu"


def test_event_edit_page_constructs(app, conn):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    win = _StubWindow(conn)
    page = EventEditPage(win, conn)
    assert page is not None


def test_event_edit_page_new_mode_shows_no_delete(app, conn):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    page = EventEditPage(win, conn)
    page.show_for(event_id=None, return_to="events")
    assert page.delete_btn.isVisible() is False
    assert "Klassenarbeit" in page.title_label.text() or "Termin" in page.title_label.text()


def test_event_edit_page_save_creates_event(app, conn):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    page = EventEditPage(win, conn)
    page.show_for(event_id=None, return_to="events")
    page.subject.setCurrentText("Mathe")
    page.date_edit.setDate(page.date_edit.date())  # use default = today + 7
    page.topics_edit.setPlainText("Bruchrechnung\nGleichungen")
    page.note_edit.setText("Formelsammlung erlaubt")
    page._save()
    rows = events_repo.list_all(conn, uid)
    assert len(rows) == 1
    assert rows[0]["subject"] == "Mathe"
    assert rows[0]["note"] == "Formelsammlung erlaubt"
    assert win.navigated_to == "events"


def test_event_edit_page_edit_mode_loads_and_updates(app, conn):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    eid = events_repo.create(
        conn, uid, "Englisch", "test", "2026-06-01",
        topics=["Vocab"], note=None,
    )
    page = EventEditPage(win, conn)
    page.show_for(event_id=eid, return_to="events")
    assert page.delete_btn.isVisible() is True
    assert page.subject.currentText() == "Englisch"
    page.note_edit.setText("neue Notiz")
    page._save()
    row = events_repo.get(conn, eid)
    assert row["note"] == "neue Notiz"
    assert win.navigated_to == "events"


def test_event_edit_page_delete_removes_event(app, conn):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    eid = events_repo.create(
        conn, uid, "Mathe", "klassenarbeit", "2026-06-01",
        topics=[], note=None,
    )
    page = EventEditPage(win, conn)
    page.show_for(event_id=eid, return_to="menu")
    page._delete()
    assert events_repo.get(conn, eid) is None
    assert win.navigated_to == "menu"


def test_event_edit_page_cancel_navigates_back(app, conn):
    from school_test_engine.ui.pages.event_edit import EventEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    page = EventEditPage(win, conn)
    page.show_for(event_id=None, return_to="menu")
    page._cancel()
    assert win.navigated_to == "menu"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_event_edit_page.py -v`
Expected: 6 failures (ModuleNotFoundError: `event_edit`).

- [ ] **Step 3: Create EventEditPage**

Create `src/school_test_engine/ui/pages/event_edit.py`:

```python
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...storage import events_repo
from .._subjects import SUBJECTS_ALL
from ..design import FontFamily


KIND_LABELS = [
    ("klassenarbeit", "Klassenarbeit"),
    ("klausur", "Klausur"),
    ("test", "Test"),
    ("sonstiges", "Sonstiges"),
]


class EventEditPage(QWidget):
    """Inline page for adding or editing a scheduled_event. Replaces the
    old EventDialog from Phases 7+."""

    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._event_id: int | None = None
        self._return_to: str = "events"

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

        eyebrow = QLabel("TERMIN")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)

        self.title_label = QLabel("Klassenarbeit")
        self.title_label.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        layout.addWidget(self.title_label)

        form = QFormLayout()
        form.setSpacing(10)

        self.subject = QComboBox()
        self.subject.addItems(SUBJECTS_ALL)
        self.subject.setEditable(True)
        form.addRow("Fach:", self.subject)

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

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        form.addRow("Datum:", self.date_edit)

        self.topics_edit = QPlainTextEdit()
        self.topics_edit.setPlaceholderText("Eine Zeile = ein Thema")
        self.topics_edit.setMaximumHeight(140)
        form.addRow("Themen:", self.topics_edit)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("optional, z. B. „Formelsammlung erlaubt“")
        form.addRow("Notiz:", self.note_edit)

        layout.addLayout(form)

        # Footer: delete (only in edit mode)
        footer = QHBoxLayout()
        self.delete_btn = QPushButton("Löschen")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete)
        self.delete_btn.setVisible(False)
        footer.addWidget(self.delete_btn)
        footer.addStretch(1)
        layout.addLayout(footer)

        layout.addStretch(1)

    def show_for(self, event_id: int | None = None, return_to: str = "events") -> None:
        self._event_id = event_id
        self._return_to = return_to
        self._reset_fields()
        if event_id is None:
            self.title_label.setText("Klassenarbeit")
            self.delete_btn.setVisible(False)
        else:
            self.title_label.setText("Termin bearbeiten")
            self.delete_btn.setVisible(True)
            self._load_event(event_id)

    def _reset_fields(self) -> None:
        self.subject.setCurrentIndex(0)
        self._kind_buttons["klassenarbeit"].setChecked(True)
        default_date = date.today() + timedelta(days=7)
        self.date_edit.setDate(QDate(default_date.year, default_date.month, default_date.day))
        self.topics_edit.setPlainText("")
        self.note_edit.setText("")

    def _load_event(self, event_id: int) -> None:
        row = events_repo.get(self.conn, event_id)
        if row is None:
            return
        idx = self.subject.findText(row["subject"])
        if idx >= 0:
            self.subject.setCurrentIndex(idx)
        else:
            self.subject.setEditText(row["subject"])
        if row["kind"] in self._kind_buttons:
            self._kind_buttons[row["kind"]].setChecked(True)
        d = row["event_date"]
        self.date_edit.setDate(QDate(int(d[:4]), int(d[5:7]), int(d[8:10])))
        topics = json.loads(row["topics"] or "[]")
        self.topics_edit.setPlainText("\n".join(topics))
        if row["note"]:
            self.note_edit.setText(row["note"])

    def _collect_data(self) -> dict:
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

    def _save(self) -> None:
        data = self._collect_data()
        if not data["subject"]:
            QMessageBox.information(self, "Fach fehlt", "Bitte ein Fach wählen.")
            return
        if self._event_id is None:
            events_repo.create(
                self.conn, self.window.active_user_id,
                data["subject"], data["kind"], data["event_date"],
                topics=data["topics"], note=data["note"],
            )
        else:
            events_repo.update(
                self.conn, self._event_id,
                subject=data["subject"], kind=data["kind"], event_date=data["event_date"],
                topics=data["topics"], note=data["note"],
            )
        self._navigate_back()

    def _delete(self) -> None:
        if self._event_id is None:
            return
        reply = QMessageBox.question(
            self, "Termin löschen?",
            "Termin endgültig löschen?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        events_repo.delete(self.conn, self._event_id)
        self._navigate_back()

    def _cancel(self) -> None:
        self._navigate_back()

    def _navigate_back(self) -> None:
        if self._return_to == "menu":
            self.window.show_menu()
        else:
            self.window.show_events()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_event_edit_page.py -v`
Expected: 6 passes.

- [ ] **Step 5: Commit**

```bash
git add tests/test_event_edit_page.py \
        src/school_test_engine/ui/pages/event_edit.py
git commit -m "feat(phase13): EventEditPage replaces EventDialog"
```

---

### Task 4: Create AssessmentEditPage

**Files:**
- Create: `src/school_test_engine/ui/pages/assessment_edit.py`
- Test: `tests/test_assessment_edit_page.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_assessment_edit_page.py`:

```python
"""Phase 13: AssessmentEditPage is the inline-page replacement for AssessmentDialog."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.storage import assessments_repo, events_repo, users_repo
from school_test_engine.storage.migrator import migrate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    migrate(c)
    yield c
    c.close()


class _StubWindow:
    def __init__(self, conn):
        self.conn = conn
        self.active_user_id: int | None = None
        self.navigated_to: str | None = None

    def show_grades(self):
        self.navigated_to = "grades"

    def show_menu(self):
        self.navigated_to = "menu"

    def show_events(self):
        self.navigated_to = "events"


def test_assessment_edit_page_constructs(app, conn):
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    page = AssessmentEditPage(win, conn)
    assert page is not None


def test_assessment_edit_page_save_creates(app, conn):
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    page = AssessmentEditPage(win, conn)
    page.show_for(assessment_id=None, return_to="grades", prefill_subject="Mathe")
    page.grade.set_value(2.0)
    page._save()
    rows = assessments_repo.list_by_subject(conn, uid, "Mathe")
    assert len(rows) == 1
    assert rows[0]["grade"] == 2.0
    assert win.navigated_to == "grades"


def test_assessment_edit_page_edit_mode_loads(app, conn):
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    aid = assessments_repo.create(
        conn, uid, "Englisch", "schriftlich", "2026-04-15",
        grade=2.5, points=None, max_points=None, note=None,
        scheduled_event_id=None,
    )
    page = AssessmentEditPage(win, conn)
    page.show_for(assessment_id=aid, return_to="grades")
    assert page.delete_btn.isVisible() is True
    assert abs(page.grade.value() - 2.5) < 0.01
    assert page.subject.currentText() == "Englisch"


def test_assessment_edit_page_delete(app, conn):
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    aid = assessments_repo.create(
        conn, uid, "Mathe", "schriftlich", "2026-04-15",
        grade=3.0, points=None, max_points=None, note=None,
        scheduled_event_id=None,
    )
    page = AssessmentEditPage(win, conn)
    page.show_for(assessment_id=aid, return_to="menu")
    page._delete()
    assert assessments_repo.get(conn, aid) is None
    assert win.navigated_to == "menu"


def test_assessment_edit_page_prefill_event_id(app, conn):
    from school_test_engine.ui.pages.assessment_edit import AssessmentEditPage
    win = _StubWindow(conn)
    uid = users_repo.create_user(conn, "Test", "👤")
    win.active_user_id = uid
    eid = events_repo.create(
        conn, uid, "Bio", "klassenarbeit", "2026-04-20",
        topics=[], note=None,
    )
    page = AssessmentEditPage(win, conn)
    page.show_for(
        assessment_id=None, return_to="menu",
        prefill_subject="Bio", prefill_event_id=eid,
    )
    page.grade.set_value(2.0)
    page._save()
    rows = assessments_repo.list_by_subject(conn, uid, "Bio")
    assert len(rows) == 1
    assert rows[0]["scheduled_event_id"] == eid


def test_grade_selector_half_step(app, conn):
    from school_test_engine.ui.pages.assessment_edit import _GradeSelector
    sel = _GradeSelector(initial=2.0)
    assert sel.value() == 2.0
    sel.set_value(2.5)
    assert sel.value() == 2.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_assessment_edit_page.py -v`
Expected: 6 failures (ModuleNotFoundError).

- [ ] **Step 3: Create AssessmentEditPage**

Create `src/school_test_engine/ui/pages/assessment_edit.py`:

```python
from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...storage import assessments_repo
from .._subjects import SUBJECTS_ALL, note_color
from ..design import FontFamily


CATEGORY_LABELS = [
    ("schriftlich", "schriftlich"),
    ("muendlich", "mündlich"),
    ("sonstige", "sonstige"),
]


class _GradeSelector(QFrame):
    """Big-button row 1..6 with ½-step toggle. Identical to former
    AssessmentDialog._GradeSelector."""

    changed = Signal(float)

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
            b.setFixedSize(56, 56)
            color = note_color(n)
            b.setStyleSheet(
                f"QPushButton {{ background: #f4efe6; color: {color}; "
                f"font-family: 'Fraunces'; font-size: 22pt; border: 2px solid transparent; border-radius: 10px; }}"
                f"QPushButton:checked {{ background: {color}; color: #f6f1e6; }}"
            )
            b.clicked.connect(lambda _, val=n: self._set_int(val))
            self._buttons[n] = b
            row, col = divmod(idx, 3)
            h.addWidget(b, row, col)

        self._half = QPushButton(",5")
        self._half.setCheckable(True)
        self._half.setFixedSize(56, 40)
        self._half.setStyleSheet(
            "QPushButton { background: #f4efe6; color: #4a4538; "
            "font-family: 'Fraunces'; font-size: 14pt; border: 2px solid transparent; border-radius: 10px; }"
            "QPushButton:checked { background: #c79d44; color: #f6f1e6; }"
        )
        self._half.clicked.connect(self._toggle_half)
        h.addWidget(self._half, 2, 2)

        h.setColumnStretch(0, 1)
        h.setColumnStretch(1, 1)
        h.setColumnStretch(2, 1)

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


class AssessmentEditPage(QWidget):
    """Inline page for adding or editing an assessment. Replaces the old
    AssessmentDialog from Phase 7+."""

    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._assessment_id: int | None = None
        self._return_to: str = "grades"
        self._prefill_event_id: int | None = None

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

        eyebrow = QLabel("NOTE")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)

        self.title_label = QLabel("Note eintragen")
        self.title_label.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        layout.addWidget(self.title_label)

        # Grade selector
        grade_lbl = QLabel("Note")
        grade_lbl.setObjectName("eyebrow")
        layout.addWidget(grade_lbl)
        self.grade = _GradeSelector(initial=2.0)
        layout.addWidget(self.grade)

        # Compact form
        form = QFormLayout()
        form.setSpacing(8)

        self.subject = QComboBox()
        self.subject.addItems(SUBJECTS_ALL)
        self.subject.setEditable(True)
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
        form.addRow("Datum:", self.date_edit)

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

        # Footer
        footer = QHBoxLayout()
        self.delete_btn = QPushButton("Löschen")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete)
        self.delete_btn.setVisible(False)
        footer.addWidget(self.delete_btn)
        footer.addStretch(1)
        layout.addLayout(footer)

        layout.addStretch(1)

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
        else:
            self.title_label.setText("Note bearbeiten")
            self.delete_btn.setVisible(True)
            self._load_assessment(assessment_id)

    def _reset_fields(self) -> None:
        self.grade.set_value(2.0)
        self.subject.setCurrentIndex(0)
        self._cat_buttons["schriftlich"].setChecked(True)
        today = date.today()
        self.date_edit.setDate(QDate(today.year, today.month, today.day))
        self.points.setValue(0.0)
        self.max_points.setValue(0.0)
        self.note_edit.setText("")

    def _load_assessment(self, assessment_id: int) -> None:
        row = assessments_repo.get(self.conn, assessment_id)
        if row is None:
            return
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
        self._prefill_event_id = row["scheduled_event_id"]

    def _collect_data(self) -> dict:
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

    def _save(self) -> None:
        data = self._collect_data()
        if not data["subject"]:
            QMessageBox.information(self, "Fach fehlt", "Bitte ein Fach wählen.")
            return
        if self._assessment_id is None:
            assessments_repo.create(
                self.conn, self.window.active_user_id,
                data["subject"], data["category"], data["assessment_date"],
                grade=data["grade"], points=data["points"], max_points=data["max_points"],
                note=data["note"], scheduled_event_id=data["scheduled_event_id"],
            )
        else:
            assessments_repo.update(
                self.conn, self._assessment_id,
                subject=data["subject"], category=data["category"],
                assessment_date=data["assessment_date"],
                grade=data["grade"], points=data["points"], max_points=data["max_points"],
                note=data["note"], scheduled_event_id=data["scheduled_event_id"],
            )
        self._navigate_back()

    def _delete(self) -> None:
        if self._assessment_id is None:
            return
        reply = QMessageBox.question(
            self, "Note löschen?",
            "Note endgültig löschen?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        assessments_repo.delete(self.conn, self._assessment_id)
        self._navigate_back()

    def _cancel(self) -> None:
        self._navigate_back()

    def _navigate_back(self) -> None:
        if self._return_to == "menu":
            self.window.show_menu()
        elif self._return_to == "events":
            self.window.show_events()
        else:
            self.window.show_grades()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_assessment_edit_page.py -v`
Expected: 6 passes.

- [ ] **Step 5: Commit**

```bash
git add tests/test_assessment_edit_page.py \
        src/school_test_engine/ui/pages/assessment_edit.py
git commit -m "feat(phase13): AssessmentEditPage replaces AssessmentDialog"
```

---

### Task 5: Wire pages into MainWindow + migrate Events callsites

**Files:**
- Modify: `src/school_test_engine/ui/main_window.py`
- Modify: `src/school_test_engine/ui/pages/events.py`

- [ ] **Step 1: Add imports + page instantiation in MainWindow**

In `src/school_test_engine/ui/main_window.py`, add to the imports block (after the `from .pages.events import EventsPage` line, alphabetically):

Find:
```python
from .pages.events import EventsPage
from .pages.gaps import GapsPage
```

Replace with:
```python
from .pages.assessment_edit import AssessmentEditPage
from .pages.event_edit import EventEditPage
from .pages.events import EventsPage
from .pages.gaps import GapsPage
```

- [ ] **Step 2: Instantiate the pages and add to stack**

In `MainWindow.__init__`, find:
```python
        self.prompt_builder_page = PromptBuilderPage(self, conn)
```

Add immediately after:
```python
        self.event_edit_page = EventEditPage(self, conn)
        self.assessment_edit_page = AssessmentEditPage(self, conn)
```

In the same method, find the tuple of pages added to `self.stack`:
```python
            self.events_page,
            self.grades_page,
            self.prompt_builder_page,
        ):
```

Replace with:
```python
            self.events_page,
            self.grades_page,
            self.prompt_builder_page,
            self.event_edit_page,
            self.assessment_edit_page,
        ):
```

- [ ] **Step 3: Add navigation methods**

In `MainWindow`, after the `show_prompt_builder` method, add:

```python
    def show_event_edit(self, event_id: int | None = None, return_to: str = "events") -> None:
        self.event_edit_page.show_for(event_id, return_to)
        self.stack.setCurrentWidget(self.event_edit_page)

    def show_assessment_edit(
        self,
        assessment_id: int | None = None,
        return_to: str = "grades",
        prefill_subject: str | None = None,
        prefill_event_id: int | None = None,
    ) -> None:
        self.assessment_edit_page.show_for(
            assessment_id, return_to, prefill_subject, prefill_event_id,
        )
        self.stack.setCurrentWidget(self.assessment_edit_page)
```

- [ ] **Step 4: Migrate Events callsites**

In `src/school_test_engine/ui/pages/events.py`, remove these imports:
```python
from ..dialogs.event_dialog import EventDialog
from ..dialogs.assessment_dialog import AssessmentDialog
```

Also remove `QDialog` from the `from PySide6.QtWidgets import (` block.

Replace `_add_event` and `_edit_event`:

```python
    def _add_event(self):
        self.window.show_event_edit(event_id=None, return_to="events")

    def _edit_event(self, event_id: int):
        self.window.show_event_edit(event_id=event_id, return_to="events")
```

- [ ] **Step 5: Run full test suite**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q`
Expected: all green. The events.py edits should not break any test (events_repo tests do not touch the dialog).

- [ ] **Step 6: Commit**

```bash
git add src/school_test_engine/ui/main_window.py \
        src/school_test_engine/ui/pages/events.py
git commit -m "feat(phase13): wire EventEditPage + AssessmentEditPage into MainWindow; migrate Events callsites"
```

---

### Task 6: Migrate Grades + Menu callsites

**Files:**
- Modify: `src/school_test_engine/ui/pages/grades.py`
- Modify: `src/school_test_engine/ui/pages/menu.py`

- [ ] **Step 1: Migrate Grades callsites**

In `src/school_test_engine/ui/pages/grades.py`, remove:
```python
from ..dialogs.assessment_dialog import AssessmentDialog
```

Also remove `QDialog` from the `from PySide6.QtWidgets import (` block.

Replace `_add_assessment` and `_edit_assessment`:

```python
    def _add_assessment(self):
        self.window.show_assessment_edit(
            assessment_id=None,
            return_to="grades",
            prefill_subject=self._current_subject,
        )

    def _edit_assessment(self, assessment_id: int):
        self.window.show_assessment_edit(
            assessment_id=assessment_id,
            return_to="grades",
        )
```

- [ ] **Step 2: Migrate Menu callsites**

In `src/school_test_engine/ui/pages/menu.py`, find and remove imports of `EventDialog` and `AssessmentDialog` (if present). Search for usages of these dialog names — `_on_enter_grade` and `_on_edit_event` (or similar). Replace them so they call `self.window.show_assessment_edit(...)` / `self.window.show_event_edit(...)` with `return_to="menu"`.

Run to find exact callsites:
```bash
grep -n "EventDialog\|AssessmentDialog" /home/matthias/Dokumente/Claude/ai-projects/school-test-engine/src/school_test_engine/ui/pages/menu.py
```

For each match, replace the dialog-creation block. Example patterns:

**Before** (typical):
```python
def _on_edit_event(self, event_id: int):
    ev = events_repo.get(self.conn, event_id)
    if ev is None:
        return
    dlg = EventDialog(self, initial=ev)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    ...
```

**After:**
```python
def _on_edit_event(self, event_id: int):
    self.window.show_event_edit(event_id=event_id, return_to="menu")
```

**Before**:
```python
def _on_enter_grade(self, event_id: int):
    ev = events_repo.get(self.conn, event_id)
    if ev is None:
        return
    dlg = AssessmentDialog(self, prefill_subject=ev["subject"], prefill_event_id=event_id)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    ...
```

**After:**
```python
def _on_enter_grade(self, event_id: int):
    ev = events_repo.get(self.conn, event_id)
    if ev is None:
        return
    self.window.show_assessment_edit(
        assessment_id=None,
        return_to="menu",
        prefill_subject=ev["subject"],
        prefill_event_id=event_id,
    )
```

After all dialog-creating callsites are converted, remove the now-unused imports (`EventDialog`, `AssessmentDialog`, `QDialog` if no longer used elsewhere) at the top of `menu.py`.

- [ ] **Step 3: Run full test suite**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add src/school_test_engine/ui/pages/grades.py \
        src/school_test_engine/ui/pages/menu.py
git commit -m "feat(phase13): migrate Grades + Menu callsites to new edit pages"
```

---

### Task 7: Delete old dialog files

**Files:**
- Delete: `src/school_test_engine/ui/dialogs/event_dialog.py`
- Delete: `src/school_test_engine/ui/dialogs/assessment_dialog.py`

- [ ] **Step 1: Verify no remaining imports**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && grep -rn "EventDialog\|AssessmentDialog\|dialogs\.event_dialog\|dialogs\.assessment_dialog" src/ tests/`
Expected: no matches (or only matches in the dialog files themselves and their tests).

If any remaining hits in `src/`, fix them first.

- [ ] **Step 2: Check for tests against the old dialogs**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && grep -rln "EventDialog\|AssessmentDialog" tests/`
Expected: no matches. If there are matches, delete those test files (the new `test_event_edit_page.py` and `test_assessment_edit_page.py` cover the same logic).

- [ ] **Step 3: Delete the dialog files**

```bash
rm /home/matthias/Dokumente/Claude/ai-projects/school-test-engine/src/school_test_engine/ui/dialogs/event_dialog.py
rm /home/matthias/Dokumente/Claude/ai-projects/school-test-engine/src/school_test_engine/ui/dialogs/assessment_dialog.py
```

- [ ] **Step 4: Check whether dialogs/__init__.py is now empty**

Run: `cat /home/matthias/Dokumente/Claude/ai-projects/school-test-engine/src/school_test_engine/ui/dialogs/__init__.py`

If the file only contains re-exports of the deleted dialogs, leave it as an empty `__init__.py` (so the package still exists). Otherwise leave it untouched.

- [ ] **Step 5: Run full test suite**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add -A src/school_test_engine/ui/dialogs/
git commit -m "chore(phase13): delete EventDialog + AssessmentDialog (replaced by inline pages)"
```

---

### Task 8: Strip emoji from UI chrome

**Files:**
- Modify: `src/school_test_engine/ui/pages/menu.py` (top-bar buttons + hamburger entries + `+ Termin` + avatar fallback)
- Modify: `src/school_test_engine/ui/pages/prompt_builder.py` (copy-btn + output-header)
- Modify: `src/school_test_engine/ui/widgets/exam_card.py` (Test bauen)
- Modify: `src/school_test_engine/ui/pages/history.py` (CSV export)
- Modify: `src/school_test_engine/ui/pages/runner.py` (Markieren)

- [ ] **Step 1: Strip top-bar emojis in menu.py**

Run:
```bash
grep -n "📝 Test bauen\|📅 Termine\|📊 Noten\|👤" /home/matthias/Dokumente/Claude/ai-projects/school-test-engine/src/school_test_engine/ui/pages/menu.py
```

For each hit, edit `pages/menu.py`:

| Find | Replace |
|---|---|
| `QPushButton("📝 Test bauen")` | `QPushButton("Test bauen")` |
| `QPushButton("📅 Termine")` | `QPushButton("Termine")` |
| `QPushButton("📊 Noten")` | `QPushButton("Noten")` |
| `self._hamburger.add_action("📝 Test bauen",` | `self._hamburger.add_action("Test bauen",` |
| `self._hamburger.add_action("📅 Termine",` | `self._hamburger.add_action("Termine",` |
| `self._hamburger.add_action("📊 Noten",` | `self._hamburger.add_action("Noten",` |

For the `self.avatar = QLabel("👤")` on line 408 — this is in the user-switch chip at the top of menu. Replace it with the SVG placeholder:

Find:
```python
        self.avatar = QLabel("👤")
```

Replace with (using the existing AvatarBadge):
```python
        from ..widgets.avatar_badge import AvatarBadge
        self.avatar = AvatarBadge(emoji="ignored", image_bytes=None, diameter=40)
```

If the surrounding code sets the avatar via `setText` or styles it like an emoji-label, also remove those lines. Inspect 5–10 lines around 408 and adjust to use `set_avatar(emoji="ignored", image_bytes=image_bytes)` when an image is available.

Run:
```bash
sed -n '400,425p' /home/matthias/Dokumente/Claude/ai-projects/school-test-engine/src/school_test_engine/ui/pages/menu.py
```

…and adapt accordingly. The goal: the user-chip avatar renders the same SVG placeholder or the user's photo.

- [ ] **Step 2: Strip emojis in prompt_builder.py**

In `src/school_test_engine/ui/pages/prompt_builder.py`:

| Find | Replace |
|---|---|
| `output_header.addWidget(QLabel("🪄 Generierter Prompt:"))` | `_eyebrow = QLabel("GENERIERTER PROMPT"); _eyebrow.setObjectName("eyebrow"); output_header.addWidget(_eyebrow)` |
| `QPushButton("📋 Kopieren")` | `QPushButton("Kopieren")` |

- [ ] **Step 3: Strip emoji in exam_card.py**

In `src/school_test_engine/ui/widgets/exam_card.py`:

| Find | Replace |
|---|---|
| `QPushButton("✨ Test bauen")` | `QPushButton("Test bauen")` |

- [ ] **Step 4: Strip emoji in history.py**

In `src/school_test_engine/ui/pages/history.py`:

| Find | Replace |
|---|---|
| `QPushButton("📤  CSV exportieren")` | `QPushButton("CSV exportieren")` |

- [ ] **Step 5: Strip emoji in runner.py**

In `src/school_test_engine/ui/pages/runner.py`:

| Find | Replace |
|---|---|
| `QPushButton("🚩  Markieren")` | `QPushButton("Markieren")` |

- [ ] **Step 6: Run full test suite**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q`
Expected: all green. If tests assert button text with emoji prefix (`assert btn.text() == "📝 Test bauen"`), update them to the stripped text.

- [ ] **Step 7: Commit**

```bash
git add src/school_test_engine/ui/pages/menu.py \
        src/school_test_engine/ui/pages/prompt_builder.py \
        src/school_test_engine/ui/widgets/exam_card.py \
        src/school_test_engine/ui/pages/history.py \
        src/school_test_engine/ui/pages/runner.py
git commit -m "refactor(phase13): strip emoji from UI chrome (text-only buttons)"
```

---

### Task 9: Button-style audit across remaining pages

**Files:** see modifications below.

- [ ] **Step 1: gaps.py**

In `src/school_test_engine/ui/pages/gaps.py:182`, the `Üben` button has no objectName. Find:
```python
        practice = QPushButton("Üben")
```
Add immediately after:
```python
        practice.setObjectName("primary")
```

- [ ] **Step 2: library.py**

In `src/school_test_engine/ui/pages/library.py`:

After `self.discard_btn = QPushButton("Verwerfen")` (line 58), add:
```python
        self.discard_btn.setObjectName("danger")
```

After `self.resume_btn = QPushButton("Fortsetzen →")` (line 61), add:
```python
        self.resume_btn.setObjectName("primary")
```

- [ ] **Step 3: history.py**

In `src/school_test_engine/ui/pages/history.py`, after `export_btn = QPushButton("CSV exportieren")` (line 80, post Task 8 emoji strip):
```python
        export_btn.setObjectName("text")
```

- [ ] **Step 4: import_wizard.py**

In `src/school_test_engine/ui/pages/import_wizard.py:62`, after `choose = QPushButton("Datei auswählen …")`:
```python
        choose.setObjectName("primary")
```

- [ ] **Step 5: results.py**

In `src/school_test_engine/ui/pages/results.py`:

After `print_btn = QPushButton("Drucken")` (line 131):
```python
        print_btn.setObjectName("text")
```

After `practice = QPushButton("Schwächen üben  →")` (line 134):
```python
        practice.setObjectName("primary")
```

- [ ] **Step 6: runner.py**

In `src/school_test_engine/ui/pages/runner.py`:

After `self.overview_btn = QPushButton("Übersicht")` (line 65):
```python
        self.overview_btn.setObjectName("text")
```

After `self.mark_btn = QPushButton("Markieren")` (line 102, post Task 8):
```python
        self.mark_btn.setObjectName("text")
```

After `self.abort_btn = QPushButton("Zurück zum Menü")` (line 108):
```python
        self.abort_btn.setObjectName("text")
```

After `self.next_btn = QPushButton("Weiter →")` (line 115):
```python
        self.next_btn.setObjectName("primary")
```

- [ ] **Step 7: review.py**

In `src/school_test_engine/ui/pages/review.py`:

After `back = QPushButton("← Weiter üben")` (line 53):
```python
        back.setObjectName("text")
```

After `to_menu = QPushButton("← Zurück zum Menü")` (line 57):
```python
        to_menu.setObjectName("text")
```

After `submit = QPushButton("Abgeben ✓")` (line 62):
```python
        submit.setObjectName("primary")
```

The status-tile buttons on line 98 (`btn = QPushButton(text)`) have their own inline stylesheet and intentionally do not use the primary/text/danger pillows. Leave them alone — they are tiles, not pillows.

- [ ] **Step 8: menu.py extras**

In `src/school_test_engine/ui/pages/menu.py`:

After `btn = QPushButton("+ Termin")` (line ~215, the `+ Termin` button in the "Was kommt"-section):
```python
        btn.setObjectName("text")
```

After `switch = QPushButton("Wechseln")` (line ~418, in the user-chip):
```python
        switch.setObjectName("text")
```

- [ ] **Step 9: profile_manager.py**

In `src/school_test_engine/ui/pages/profile_manager.py`:

After `edit_btn = QPushButton("Bearbeiten")` (line 74):
```python
        edit_btn.setObjectName("text")
```

After `del_btn = QPushButton("Löschen")` (line 77):
```python
        del_btn.setObjectName("danger")
```

After `add = QPushButton("+  Neues Profil anlegen")` (line 110):
```python
        add.setObjectName("text")
```

- [ ] **Step 10: daily_card.py**

In `src/school_test_engine/ui/widgets/daily_card.py`, after `btn = QPushButton("Starten →")` (line ~92):
```python
        btn.setObjectName("primary")
```

- [ ] **Step 11: Run full test suite**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -x -q`
Expected: all green.

- [ ] **Step 12: Verify the audit caught everything**

Run:
```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && python3 -c "
import re, pathlib
src = pathlib.Path('src/school_test_engine/ui')
unstyled = []
for p in src.rglob('*.py'):
    text = p.read_text()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.search(r'= QPushButton\(|QPushButton\(', line)
        if not m:
            continue
        # Skip if next 5 lines contain setObjectName or setStyleSheet
        ctx = '\n'.join(lines[i:i+5])
        if 'setObjectName' in ctx or 'setStyleSheet' in ctx:
            continue
        # Skip if line has 'self._buttons' or similar internal helpers
        if 'subjectTab' in ctx:
            continue
        unstyled.append(f'{p}:{i+1}: {line.strip()}')
for u in unstyled:
    print(u)
print(f'TOTAL unstyled: {len(unstyled)}')
"
```
Expected: `TOTAL unstyled: 0` (or only buttons that intentionally have inline stylesheets, like the `_GradeSelector` buttons in assessment_edit.py — those use `setStyleSheet` so they are detected as OK).

If any remaining lines appear, add `setObjectName(...)` per the heuristic in the spec.

- [ ] **Step 13: Commit**

```bash
git add src/school_test_engine/ui/
git commit -m "refactor(phase13): button-style audit — every QPushButton has primary|text|danger objectName"
```

---

### Task 10: Document button convention in style.qss

**Files:**
- Modify: `src/school_test_engine/ui/style.qss`

- [ ] **Step 1: Add convention comment near top of QSS**

In `src/school_test_engine/ui/style.qss`, find the very first comment block:
```
/* Kessler Family Design System — Qt Style Sheet
   paper-and-ink Wärme · Clay-Terracotta · Tea-Green
   ============================================================= */
```

Replace with:
```
/* Kessler Family Design System — Qt Style Sheet
   paper-and-ink Wärme · Clay-Terracotta · Tea-Green
   =============================================================

   Button convention (Phase 13):
   Every QPushButton in the codebase MUST have one of three objectName values:
     - "primary"  Haupt-Aktion einer Seite/Form (orange filled pillow)
     - "text"     Sekundäre Aktion / Navigation (transparent pillow, hover effect)
     - "danger"   Destruktive Aktion (rose-tinted pillow)
   Exceptions: buttons with their own inline setStyleSheet() (tiles, grade
   selectors, subject tabs) are intentionally non-standard.
   ============================================================= */
```

- [ ] **Step 2: Commit**

```bash
git add src/school_test_engine/ui/style.qss
git commit -m "docs(phase13): document button convention in QSS header"
```

---

### Task 11: Final smoke + acceptance check

**Files:** none modified — verification only.

- [ ] **Step 1: Run full test suite**

Run: `cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q`
Expected: all green, count ≥ 247 (241 baseline + 3 avatar + 6 event-edit + 6 assessment-edit = ~256, minus any deleted dialog tests).

- [ ] **Step 2: Verify spec acceptance criteria 1–10**

Run each verification:

```bash
# 1. New pages exist
test -f src/school_test_engine/ui/pages/event_edit.py && echo "EventEditPage ✓"
test -f src/school_test_engine/ui/pages/assessment_edit.py && echo "AssessmentEditPage ✓"

# 2. Old dialogs deleted
test ! -f src/school_test_engine/ui/dialogs/event_dialog.py && echo "EventDialog deleted ✓"
test ! -f src/school_test_engine/ui/dialogs/assessment_dialog.py && echo "AssessmentDialog deleted ✓"

# 3. Callsites migrated
! grep -rn "EventDialog\|AssessmentDialog" src/ && echo "Callsites migrated ✓"

# 4. UI-chrome emoji-free (allowed emojis remain in achievement/feedback context)
! grep -rnE "QPushButton\(\"📝|QPushButton\(\"📅|QPushButton\(\"📊|QPushButton\(\"📋|QPushButton\(\"🪄|QPushButton\(\"✨|QPushButton\(\"📤|QPushButton\(\"🚩" src/ && echo "Emoji stripped from buttons ✓"

# 7. SVG asset
test -f assets/avatar-placeholder.svg && echo "SVG placeholder ✓"

# 8. Button audit (re-run Task 9 Step 12)
python3 -c "
import re, pathlib
unstyled = []
for p in pathlib.Path('src/school_test_engine/ui').rglob('*.py'):
    lines = p.read_text().splitlines()
    for i, line in enumerate(lines):
        if 'QPushButton(' not in line:
            continue
        ctx = '\n'.join(lines[i:i+5])
        if 'setObjectName' in ctx or 'setStyleSheet' in ctx or 'subjectTab' in ctx:
            continue
        unstyled.append(f'{p}:{i+1}: {line.strip()}')
print(f'Unstyled: {len(unstyled)}')
[print(u) for u in unstyled]
"
# Expected: Unstyled: 0

# 9. Button convention in QSS
head -15 src/school_test_engine/ui/style.qss | grep -q "Button convention" && echo "QSS convention documented ✓"
```

All checks should print ✓ or pass.

- [ ] **Step 3: Manual smoke (interactive — only if user runs it)**

```bash
cd /home/matthias/Dokumente/Claude/ai-projects/school-test-engine && .venv/bin/python -m school_test_engine
```

In the app, click through:
1. Profile-Picker → SVG avatar appears for users without a photo.
2. Menu → Top-bar shows `Test bauen`, `Termine`, `Noten` (no emoji).
3. Termine-Page → click `+ Termin` → inline page (not modal); fill + speichern; edit a row → inline page; löschen.
4. Noten-Page → click `+ Note` → inline page; fill + speichern; edit + löschen.
5. Daily-5-Card → still shows 🔥 and ✓ (achievement decoration retained).
6. Prompt-Builder → output-header reads `GENERIERTER PROMPT` (eyebrow style), copy button reads `Kopieren`.

(Skip this step in automated CI; record results in the final commit message if executed.)

- [ ] **Step 4: Final commit + close phase**

If all checks pass, no additional commits needed — every task already committed individually.

Run `git log --oneline -15` and verify the Phase 13 commit chain is clean (Task 1 → Task 10).

Mark TaskCreate #74 (Phase 13: Design-System Consolidation) as completed.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Covered by |
|---|---|
| §5.1 EventEditPage | Task 3 |
| §5.1 AssessmentEditPage | Task 4 |
| §5.1 MainWindow integration | Task 5 |
| §5.1 Callsite migration (Events) | Task 5 |
| §5.1 Callsite migration (Grades, Menu) | Task 6 |
| §5.1 Dialog cleanup | Task 7 |
| §5.2 Emoji-strip from Top-Bar / Hamburger | Task 8 (menu.py) |
| §5.2 Emoji-strip from Copy / Output-Header | Task 8 (prompt_builder.py) |
| §5.2 Emoji-strip from ExamCard | Task 8 (exam_card.py) |
| §5.3 Avatar SVG asset | Task 1 |
| §5.3 AvatarBadge + ProfileCard SVG rendering | Task 2 |
| §5.4 Button-style audit | Task 9 |
| §5.4 Button convention doc | Task 10 |
| §5.5 Tests | Tasks 2, 3, 4 |
| §6 Acceptance criteria | Task 11 |

No spec gaps.

**2. Placeholders:** None — every step has either complete code, exact commands, or specific find/replace pairs.

**3. Type consistency:**
- `EventEditPage` exposes `show_for(event_id, return_to)`, `_save`, `_delete`, `_cancel`, `delete_btn`, `save_btn`, `subject`, `date_edit`, `topics_edit`, `note_edit`, `title_label`, `_kind_buttons` — used consistently in tests and callsites.
- `AssessmentEditPage` exposes `show_for(assessment_id, return_to, prefill_subject, prefill_event_id)`, `_save`, `_delete`, `grade`, `subject`, `_cat_buttons`, `delete_btn`, `title_label` — used consistently.
- `MainWindow.show_event_edit(event_id, return_to)` and `MainWindow.show_assessment_edit(assessment_id, return_to, prefill_subject, prefill_event_id)` — called consistently from `events.py`, `grades.py`, `menu.py`.
- `_cached_placeholder_pixmap(diameter)` defined in `avatar_badge.py`, imported and used in `profile_card.py`.

All names are consistent across tasks.

"""GradesPage empty state: only one 'no grades' message, no Notenverlauf chart."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from school_test_engine.storage import run_migrations, users_repo


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    run_migrations(c)
    yield c
    c.close()


class _Win:
    def __init__(self, conn, uid):
        self.conn = conn
        self.active_user_id = uid

    def show_menu(self):
        pass


def _content_labels(page) -> list[str]:
    return [l.text() for l in page._content.findChildren(QLabel)]


def test_no_notenverlauf_eyebrow_when_no_grades(app, conn):
    from school_test_engine.ui.pages.grades import GradesPage
    uid = users_repo.create_user(conn, "Clemens", "👤")
    page = GradesPage(_Win(conn, uid), conn)
    page.reload()
    labels = _content_labels(page)
    assert "NOTENVERLAUF" not in labels, (
        f"Notenverlauf eyebrow should not appear without grades; got {labels}"
    )


def test_single_empty_message_when_no_grades(app, conn):
    from school_test_engine.ui.pages.grades import GradesPage
    uid = users_repo.create_user(conn, "Clemens", "👤")
    page = GradesPage(_Win(conn, uid), conn)
    page.reload()
    labels = _content_labels(page)
    matches = [l for l in labels if "Noch keine Noten" in l]
    assert len(matches) == 1, f"Expected exactly one empty message, got {matches}"


def test_no_zeugnis_hero_when_no_grades(app, conn):
    from school_test_engine.ui.pages.grades import GradesPage
    uid = users_repo.create_user(conn, "Clemens", "👤")
    page = GradesPage(_Win(conn, uid), conn)
    page.reload()
    labels = _content_labels(page)
    # Hero shows "ZEUGNIS-SCHÄTZUNG · 50/50" eyebrow when present; absence
    # means the placeholder "—" card isn't rendered either.
    assert not any("ZEUGNIS-SCHÄTZUNG" in l for l in labels), (
        f"Zeugnis hero should be hidden until first grade; got {labels}"
    )

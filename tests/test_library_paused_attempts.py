"""Library shows all paused attempts of the active user (#10)."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from school_test_engine.storage import attempts_repo, run_migrations, tests_repo, users_repo
from school_test_engine.models.test import Test


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


def _test(title):
    return Test.model_validate({
        "schema_version": 1, "title": title, "subject": "Mathe", "grade": 8, "school_type": "Realschule",
        "questions": [{
            "id": "q1", "type": "short_answer", "topic": "t", "difficulty": "leicht",
            "points": 1, "prompt": "1+1?", "accepted_answers": ["2"],
        }],
    })


class _Win:
    def __init__(self, uid):
        self.active_user_id = uid
        self.resumed = []

    def resume_attempt(self, aid):
        self.resumed.append(aid)

    def start_test(self, tid):
        pass


def _make(conn, uid, title):
    tid = tests_repo.insert_test(conn, _test(title), "{}", uid)
    return attempts_repo.start_attempt(conn, tid, 1, uid)


def test_list_incomplete_attempts_newest_first_and_user_scoped(conn):
    u1 = users_repo.create_user(conn, "A", "x")
    u2 = users_repo.create_user(conn, "B", "x")
    a = _make(conn, u1, "Test A")
    b = _make(conn, u1, "Test B")
    _make(conn, u2, "Fremd")
    rows = attempts_repo.list_incomplete_attempts(conn, u1)
    assert [r["id"] for r in rows] == [b, a]
    assert [r["test_title"] for r in rows] == ["Test B", "Test A"]


def test_library_shows_all_paused_attempts(app, conn):
    from school_test_engine.ui.pages.library import LibraryPage
    uid = users_repo.create_user(conn, "A", "x")
    a = _make(conn, uid, "Test A")
    b = _make(conn, uid, "Test B")
    win = _Win(uid)
    page = LibraryPage(win, conn)
    page.reload()
    assert page.resume_frame.isHidden() is False
    assert len(page._resume_rows) == 2
    text = " ".join(r.label.text() for r in page._resume_rows)
    assert "Test A" in text and "Test B" in text
    assert "Test B" in page._resume_rows[0].label.text()  # newest first
    page._resume_rows[1].resume_btn.click()
    assert win.resumed == [a]


def test_library_hides_banner_without_paused_attempts(app, conn):
    from school_test_engine.ui.pages.library import LibraryPage
    uid = users_repo.create_user(conn, "A", "x")
    page = LibraryPage(_Win(uid), conn)
    page.reload()
    assert page.resume_frame.isHidden()
    assert page._resume_rows == []

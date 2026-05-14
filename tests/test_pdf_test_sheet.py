"""Phase 14 Track D: Test-Sheet PDF export."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from school_test_engine.storage import run_migrations, users_repo
from school_test_engine.storage import tests_repo
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


def _make_test(conn, uid, subject="Mathe"):
    test_data = {
        "schema_version": 1,
        "title": "Übungs-Test",
        "subject": subject,
        "grade": 8,
        "questions": [
            {
                "id": "q1",
                "type": "single_choice",
                "topic": "Arithmetik",
                "difficulty": "leicht",
                "points": 1,
                "prompt": "Was ist 1+1?",
                "choices": [
                    {"id": "a", "text": "1"},
                    {"id": "b", "text": "2"},
                    {"id": "c", "text": "3"},
                ],
                "correct": ["b"],
            },
            {
                "id": "q2",
                "type": "short_answer",
                "topic": "Arithmetik",
                "difficulty": "leicht",
                "points": 1,
                "prompt": "Was ist 3+4?",
                "accepted_answers": ["7"],
            },
        ],
    }
    t = Test.model_validate(test_data)
    return tests_repo.insert_test(conn, t, "{}", uid)


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
    uid = users_repo.create_user(conn, "Test2", "👤")
    test_id = _make_test(conn, uid)
    html = export_test_sheet(conn, test_id)
    pdf = render_to_bytes(html)
    assert pdf[:5] == b"%PDF-"

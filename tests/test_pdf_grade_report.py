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


def test_export_grade_report_no_assessments(app, conn):
    from school_test_engine.pdf_export.grade_report import export_grade_report
    uid = users_repo.create_user(conn, "Clemens", "👤")
    html = export_grade_report(conn, uid)
    assert "Clemens" in html
    assert "Noch keine Noten" in html

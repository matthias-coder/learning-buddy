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

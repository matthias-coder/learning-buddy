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

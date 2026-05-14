"""Phase 14 Migration 010: adds users.show_keyboard_hints (BOOLEAN DEFAULT 1)."""
from __future__ import annotations

import sqlite3

import pytest

from school_test_engine.storage import run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "test.db")
    c.row_factory = sqlite3.Row
    run_migrations(c)
    yield c
    c.close()


def test_users_show_keyboard_hints_column_exists(conn):
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    assert "show_keyboard_hints" in cols


def test_new_user_has_keyboard_hints_default_on(conn):
    uid = users_repo.create_user(conn, "Test", "👤")
    row = users_repo.get_user(conn, uid)
    assert row["show_keyboard_hints"] == 1


def test_update_user_can_toggle_keyboard_hints(conn):
    uid = users_repo.create_user(conn, "Test", "👤")
    users_repo.update_user(conn, uid, show_keyboard_hints=0)
    row = users_repo.get_user(conn, uid)
    assert row["show_keyboard_hints"] == 0

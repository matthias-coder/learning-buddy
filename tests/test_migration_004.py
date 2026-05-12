"""Verifiziert dass Migration 004 (Phase 6 Profile) auf einer Pre-Phase-6-DB sauber läuft:
Tests bleiben, kriegen user_id=1, Standard-User existiert, Versuche werden gelöscht.
"""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from school_test_engine.storage.db import MIGRATIONS_DIR, connect, run_migrations


@pytest.fixture
def pre_phase6_db(tmp_path):
    """DB mit Migrationen 001-003 plus testweise eingefügte Daten."""
    db = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    for v in (1, 2, 3):
        sql_file = list(MIGRATIONS_DIR.glob(f"{v:03d}_*.sql"))[0]
        conn.executescript(sql_file.read_text(encoding="utf-8"))
        conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (v,))
    conn.commit()

    # Test einfügen
    conn.execute(
        """INSERT INTO tests (title, subject, grade, school_type, notenschluessel,
           source_json, imported_at) VALUES ('Alt', 'Mathe', 8, 'Realschule', '{}', '{}', '2026-01-01')"""
    )
    conn.execute(
        """INSERT INTO questions (test_id, ext_id, position, type, topic, difficulty, points,
           prompt, payload) VALUES (1, 'q1', 0, 'single_choice', 'x', 'leicht', 1, '?', '{}')"""
    )
    # Versuch einfügen
    conn.execute(
        """INSERT INTO attempts (test_id, started_at, points_possible, completed)
           VALUES (1, '2026-01-01', 1, 1)"""
    )
    conn.execute(
        """INSERT INTO answers (attempt_id, question_id, response, points_earned, is_correct)
           VALUES (1, 1, '[]', 1.0, 1)"""
    )
    conn.commit()
    conn.close()
    yield db


def test_migration_004_creates_standard_user(pre_phase6_db):
    conn = connect(pre_phase6_db)
    run_migrations(conn)
    users = conn.execute("SELECT * FROM users").fetchall()
    assert len(users) == 1
    assert users[0]["id"] == 1
    assert users[0]["name"] == "Standard"


def test_migration_004_keeps_tests_assigned_to_standard(pre_phase6_db):
    conn = connect(pre_phase6_db)
    run_migrations(conn)
    tests = conn.execute("SELECT * FROM tests").fetchall()
    assert len(tests) == 1
    assert tests[0]["user_id"] == 1
    questions = conn.execute("SELECT * FROM questions").fetchall()
    assert len(questions) == 1


def test_migration_004_deletes_attempts_and_answers(pre_phase6_db):
    conn = connect(pre_phase6_db)
    run_migrations(conn)
    assert conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == 0


def test_migration_004_schema_version_advanced(pre_phase6_db):
    conn = connect(pre_phase6_db)
    run_migrations(conn)
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version >= 4


def test_migration_004_indexes_exist(pre_phase6_db):
    conn = connect(pre_phase6_db)
    run_migrations(conn)
    indexes = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    assert "idx_tests_user" in indexes
    assert "idx_attempts_user" in indexes


def test_users_repo_delete_cleans_up(pre_phase6_db):
    """users_repo.delete_user erledigt das manuelle Cascade."""
    from school_test_engine.storage import users_repo
    conn = connect(pre_phase6_db)
    run_migrations(conn)
    users_repo.delete_user(conn, 1)
    assert conn.execute("SELECT COUNT(*) FROM tests").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0

import pytest

from school_test_engine.storage import connect, run_migrations


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_users_has_grade_column(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "grade" in cols
    assert cols["grade"]["notnull"] == 0  # nullable


def test_users_has_school_type_column(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "school_type" in cols
    assert cols["school_type"]["notnull"] == 0


def test_users_has_bundesland_column(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "bundesland" in cols
    assert cols["bundesland"]["notnull"] == 0


def test_users_has_school_name_column(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "school_name" in cols


def test_users_has_school_year_column(conn):
    cols = {row["name"]: row for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "school_year" in cols


def test_existing_users_remain_intact(conn):
    """Migration must not delete/break the default 'Standard' user from migration 004."""
    row = conn.execute("SELECT name, grade, school_type FROM users WHERE id = 1").fetchone()
    assert row is not None
    assert row["name"] == "Standard"
    assert row["grade"] is None
    assert row["school_type"] is None

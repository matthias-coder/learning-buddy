import pytest

from school_test_engine.storage import connect, run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_migration_creates_standard_user(conn):
    users = users_repo.list_users(conn)
    assert len(users) == 1
    assert users[0]["name"] == "Standard"
    assert users[0]["id"] == 1


def test_create_user_assigns_increasing_sort_order(conn):
    a = users_repo.create_user(conn, "Clemens", "🧒")
    b = users_repo.create_user(conn, "Mira", "🦊")
    rows = users_repo.list_users(conn)
    assert [r["name"] for r in rows] == ["Standard", "Clemens", "Mira"]
    assert rows[1]["sort_order"] < rows[2]["sort_order"]


def test_two_users_same_name_allowed(conn):
    a = users_repo.create_user(conn, "Clemens")
    b = users_repo.create_user(conn, "Clemens")
    assert a != b
    assert users_repo.count_users(conn) == 3  # Standard + 2 Clemens


def test_update_user(conn):
    uid = users_repo.create_user(conn, "alt", "👤")
    users_repo.update_user(conn, uid, name="neu", avatar="🧑")
    row = users_repo.get_user(conn, uid)
    assert row["name"] == "neu"
    assert row["avatar"] == "🧑"


def test_delete_user_cascades_tests_attempts(conn):
    from school_test_engine.importer.json_import import import_from_string
    from pathlib import Path

    uid = users_repo.create_user(conn, "Wegmacher")
    src = (Path(__file__).parent.parent / "examples" / "mathe-lineare-gleichungen.json").read_text(encoding="utf-8")
    test_id = import_from_string(conn, src, user_id=uid)

    # Verify
    assert conn.execute("SELECT COUNT(*) FROM tests WHERE user_id = ?", (uid,)).fetchone()[0] == 1

    users_repo.delete_user(conn, uid)
    assert users_repo.get_user(conn, uid) is None
    assert conn.execute("SELECT COUNT(*) FROM tests WHERE user_id = ?", (uid,)).fetchone()[0] == 0


def test_count_users(conn):
    assert users_repo.count_users(conn) == 1
    users_repo.create_user(conn, "x")
    users_repo.create_user(conn, "y")
    assert users_repo.count_users(conn) == 3


def test_get_unknown_user(conn):
    assert users_repo.get_user(conn, 99999) is None

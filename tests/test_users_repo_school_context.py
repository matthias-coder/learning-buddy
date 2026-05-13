import pytest

from school_test_engine.storage import connect, run_migrations, users_repo


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, "Tester")


def test_update_user_sets_grade(conn, uid):
    users_repo.update_user(conn, uid, grade=8)
    assert users_repo.get_user(conn, uid)["grade"] == 8


def test_update_user_clears_grade_with_none(conn, uid):
    users_repo.update_user(conn, uid, grade=8)
    users_repo.update_user(conn, uid, grade=None)
    assert users_repo.get_user(conn, uid)["grade"] is None


def test_update_user_omit_grade_leaves_value(conn, uid):
    users_repo.update_user(conn, uid, grade=8)
    users_repo.update_user(conn, uid, name="neu")
    assert users_repo.get_user(conn, uid)["grade"] == 8


def test_update_user_sets_school_type(conn, uid):
    users_repo.update_user(conn, uid, school_type="Realschule")
    assert users_repo.get_user(conn, uid)["school_type"] == "Realschule"


def test_update_user_sets_bundesland(conn, uid):
    users_repo.update_user(conn, uid, bundesland="Hessen")
    assert users_repo.get_user(conn, uid)["bundesland"] == "Hessen"


def test_update_user_sets_school_name(conn, uid):
    users_repo.update_user(conn, uid, school_name="Heinrich-Heine-RS")
    assert users_repo.get_user(conn, uid)["school_name"] == "Heinrich-Heine-RS"


def test_update_user_sets_school_year(conn, uid):
    users_repo.update_user(conn, uid, school_year="2025/26")
    assert users_repo.get_user(conn, uid)["school_year"] == "2025/26"


def test_update_user_sets_all_five_at_once(conn, uid):
    users_repo.update_user(
        conn, uid,
        grade=10, school_type="Gymnasium", bundesland="Bayern",
        school_name="Max-Plank", school_year="2025/26",
    )
    row = users_repo.get_user(conn, uid)
    assert row["grade"] == 10
    assert row["school_type"] == "Gymnasium"
    assert row["bundesland"] == "Bayern"
    assert row["school_name"] == "Max-Plank"
    assert row["school_year"] == "2025/26"

import pytest

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import prompt_drafts_repo


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_two_users_have_independent_drafts(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    prompt_drafts_repo.upsert(conn, a, "Mathe", last_topic="A-T", last_count=5, last_dist="auto")
    prompt_drafts_repo.upsert(conn, b, "Mathe", last_topic="B-T", last_count=8, last_dist="auto")
    assert prompt_drafts_repo.get(conn, a, "Mathe")["last_topic"] == "A-T"
    assert prompt_drafts_repo.get(conn, b, "Mathe")["last_topic"] == "B-T"


def test_delete_user_cascade_removes_drafts(conn):
    uid = users_repo.create_user(conn, "Wegmacher")
    prompt_drafts_repo.upsert(conn, uid, "Mathe", last_topic="X", last_count=10, last_dist="auto")
    users_repo.delete_user(conn, uid)
    assert conn.execute(
        "SELECT COUNT(*) FROM prompt_drafts WHERE user_id = ?", (uid,)
    ).fetchone()[0] == 0

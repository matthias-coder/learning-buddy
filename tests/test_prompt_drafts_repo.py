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


@pytest.fixture
def uid(conn):
    return users_repo.create_user(conn, "Clemens", "🧒")


def test_upsert_creates_row(conn, uid):
    prompt_drafts_repo.upsert(
        conn, uid, "Mathe",
        last_topic="Funktionen", last_count=10, last_dist="auto",
    )
    row = prompt_drafts_repo.get(conn, uid, "Mathe")
    assert row is not None
    assert row["last_topic"] == "Funktionen"
    assert row["last_count"] == 10
    assert row["last_dist"] == "auto"


def test_upsert_updates_existing_row(conn, uid):
    prompt_drafts_repo.upsert(
        conn, uid, "Mathe",
        last_topic="A", last_count=5, last_dist="auto",
    )
    prompt_drafts_repo.upsert(
        conn, uid, "Mathe",
        last_topic="B", last_count=8, last_dist="manuell:3-3-2",
    )
    rows = conn.execute("SELECT * FROM prompt_drafts WHERE user_id = ? AND subject = ?", (uid, "Mathe")).fetchall()
    assert len(rows) == 1
    assert rows[0]["last_topic"] == "B"
    assert rows[0]["last_count"] == 8
    assert rows[0]["last_dist"] == "manuell:3-3-2"


def test_get_returns_none_when_missing(conn, uid):
    assert prompt_drafts_repo.get(conn, uid, "Mathe") is None


def test_list_for_user_returns_all_subjects(conn, uid):
    prompt_drafts_repo.upsert(conn, uid, "Mathe", last_topic="A", last_count=10, last_dist="auto")
    prompt_drafts_repo.upsert(conn, uid, "Bio", last_topic="B", last_count=8, last_dist="auto")
    rows = prompt_drafts_repo.list_for_user(conn, uid)
    assert len(rows) == 2
    assert {r["subject"] for r in rows} == {"Mathe", "Bio"}


def test_user_isolation(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    prompt_drafts_repo.upsert(conn, a, "Mathe", last_topic="A-Mathe", last_count=10, last_dist="auto")
    assert prompt_drafts_repo.get(conn, a, "Mathe")["last_topic"] == "A-Mathe"
    assert prompt_drafts_repo.get(conn, b, "Mathe") is None

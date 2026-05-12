"""Verifiziert dass Datenisolation zwischen Profilen funktioniert."""
import json
from pathlib import Path

import pytest

from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import attempts_repo, connect, run_migrations, tests_repo, users_repo
from school_test_engine.study.builder import build_study_test

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


@pytest.fixture
def two_users(conn):
    a = 1  # Standard
    b = users_repo.create_user(conn, "User-B", "🦊")
    return a, b


def test_list_tests_filtered_by_user(conn, two_users):
    a, b = two_users
    src = (EXAMPLES / "mathe-lineare-gleichungen.json").read_text(encoding="utf-8")
    import_from_string(conn, src, user_id=a)
    import_from_string(conn, src, user_id=b)

    a_tests = tests_repo.list_tests(conn, user_id=a)
    b_tests = tests_repo.list_tests(conn, user_id=b)
    assert len(a_tests) == 1
    assert len(b_tests) == 1
    assert a_tests[0]["id"] != b_tests[0]["id"]


def test_attempt_scoped_to_user(conn, two_users):
    a, b = two_users
    src = (EXAMPLES / "mathe-lineare-gleichungen.json").read_text(encoding="utf-8")
    test_a = import_from_string(conn, src, user_id=a)
    attempts_repo.start_attempt(conn, test_a, 10, user_id=a)
    attempts_repo.start_attempt(conn, test_a, 10, user_id=a)
    # User B sieht keine
    assert attempts_repo.find_incomplete_attempt(conn, b) is None
    # User A sieht seinen
    assert attempts_repo.find_incomplete_attempt(conn, a) is not None


def test_study_builder_scoped_to_user(conn, two_users):
    a, b = two_users
    src = (EXAMPLES / "mathe-lineare-gleichungen.json").read_text(encoding="utf-8")
    import_from_string(conn, src, user_id=a)

    # User A kann üben
    sid = build_study_test(
        conn, topic="Lineare Gleichungen — Umformen", subject="Mathe", user_id=a
    )
    assert sid is not None

    # User B nicht (keine Fragen importiert)
    from school_test_engine.study.builder import StudyBuildError
    with pytest.raises(StudyBuildError):
        build_study_test(
            conn, topic="Lineare Gleichungen — Umformen", subject="Mathe", user_id=b
        )


def test_topic_stats_scoped_to_user(conn, two_users):
    a, b = two_users
    src = (EXAMPLES / "mathe-lineare-gleichungen.json").read_text(encoding="utf-8")
    test_a = import_from_string(conn, src, user_id=a)
    aid = attempts_repo.start_attempt(conn, test_a, 13, user_id=a)
    # Eine Antwort und abschließen
    qid = conn.execute("SELECT id FROM questions WHERE test_id = ?", (test_a,)).fetchone()[0]
    attempts_repo.upsert_answer(conn, aid, qid, [], 2.0, True, False)
    attempts_repo.finish_attempt(conn, aid, 2.0, 50.0, 4)

    a_stats = attempts_repo.topic_stats(conn, user_id=a)
    b_stats = attempts_repo.topic_stats(conn, user_id=b)
    assert len(a_stats) > 0
    assert len(b_stats) == 0

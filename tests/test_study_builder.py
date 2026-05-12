import pytest
from pathlib import Path

from school_test_engine.importer.json_import import import_from_string
from school_test_engine.storage import connect, run_migrations
from school_test_engine.study.builder import StudyBuildError, build_study_test

EXAMPLES = Path(__file__).parent.parent / "examples"
_SOURCE = (EXAMPLES / "mathe-lineare-gleichungen.json").read_text(encoding="utf-8")


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_build_study_test_with_matching_questions(conn):
    import_from_string(conn, _SOURCE, user_id=1)

    test_id = build_study_test(
        conn, topic="Lineare Gleichungen — Umformen", subject="Mathe", user_id=1
    )
    row = conn.execute("SELECT * FROM tests WHERE id = ?", (test_id,)).fetchone()
    assert row["is_study"] == 1
    assert "Übung:" in row["title"]

    questions = conn.execute(
        "SELECT * FROM questions WHERE test_id = ? ORDER BY position", (test_id,)
    ).fetchall()
    assert len(questions) == 2
    assert all(q["topic"] == "Lineare Gleichungen — Umformen" for q in questions)


def test_build_study_test_raises_when_no_match(conn):
    import_from_string(conn, _SOURCE, user_id=1)

    with pytest.raises(StudyBuildError):
        build_study_test(conn, topic="Unbekanntes Thema", subject="Mathe", user_id=1)


def test_build_study_test_respects_max_questions(conn):
    import_from_string(conn, _SOURCE, user_id=1)

    test_id = build_study_test(
        conn, topic="Lineare Gleichungen — Anwendung", subject="Mathe", user_id=1, max_questions=1
    )
    questions = conn.execute(
        "SELECT * FROM questions WHERE test_id = ?", (test_id,)
    ).fetchall()
    assert len(questions) == 1


def test_list_tests_excludes_study_by_default(conn):
    import_from_string(conn, _SOURCE, user_id=1)
    build_study_test(conn, topic="Lineare Gleichungen — Umformen", subject="Mathe", user_id=1)

    from school_test_engine.storage import tests_repo
    visible = tests_repo.list_tests(conn, user_id=1)
    assert len(visible) == 1
    assert visible[0]["is_study"] == 0

    all_tests = tests_repo.list_tests(conn, user_id=1, include_study=True)
    assert len(all_tests) == 2

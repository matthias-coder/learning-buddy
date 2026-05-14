import json
import pytest
from datetime import date

from school_test_engine.storage import (
    connect, run_migrations, users_repo, attempts_repo,
)
from school_test_engine.importer.json_import import import_from_string
from school_test_engine.daily.builder import (
    has_enough_questions,
    build_daily_test,
)


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


def _import_test_with_topics(conn, uid, subject: str, topics: list[str]):
    """Import a test where each topic gets one question."""
    questions = []
    for i, topic in enumerate(topics):
        questions.append({
            "id": f"q{i+1}",
            "type": "single_choice",
            "topic": topic,
            "difficulty": "mittel",
            "points": 2,
            "prompt": f"Frage {i+1}",
            "choices": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "correct": ["a"],
            "explanation": "...",
        })
    payload = json.dumps({
        "schema_version": 1,
        "title": f"Test {subject}",
        "subject": subject,
        "grade": 8,
        "school_type": "Realschule",
        "questions": questions,
    })
    return import_from_string(conn, payload, user_id=uid)


def _record_answer(conn, uid, test_id, question_ext_id, correct: bool):
    """Create a finished attempt with one answer."""
    aid = attempts_repo.start_attempt(conn, test_id, 10, uid)
    qrow = conn.execute(
        "SELECT id, points FROM questions WHERE test_id = ? AND ext_id = ?",
        (test_id, question_ext_id),
    ).fetchone()
    attempts_repo.upsert_answer(
        conn, aid, qrow["id"],
        response=["a"] if correct else ["b"],
        points_earned=qrow["points"] if correct else 0,
        is_correct=correct,
    )
    attempts_repo.finish_attempt(conn, aid, points_earned=qrow["points"] if correct else 0,
                                 percent=100 if correct else 0,
                                 note=1 if correct else 5)
    return aid


def test_has_enough_questions_false_when_no_library(conn, uid):
    assert has_enough_questions(conn, uid) is False


def test_has_enough_questions_false_with_fewer_than_5(conn, uid):
    _import_test_with_topics(conn, uid, "Mathe", ["A", "B", "C"])  # 3 questions
    assert has_enough_questions(conn, uid) is False


def test_has_enough_questions_true_with_5_or_more(conn, uid):
    _import_test_with_topics(conn, uid, "Mathe", ["A", "B", "C", "D", "E"])
    assert has_enough_questions(conn, uid) is True


def test_has_enough_questions_excludes_synthetic_tests(conn, uid):
    """is_study=1 tests don't count toward the pool size."""
    _import_test_with_topics(conn, uid, "Mathe", ["A", "B"])  # 2 real
    # Create synthetic test manually (study-style)
    conn.execute(
        """
        INSERT INTO tests (title, subject, grade, school_type, description,
                           time_limit_min, notenschluessel, source_json,
                           imported_at, is_study, user_id)
        VALUES ('Synth', 'Mathe', 8, 'Realschule', '', NULL, '{}', '{}', '2026-01-01', 1, ?)
        """,
        (uid,),
    )
    synth_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    for i in range(5):
        conn.execute(
            """INSERT INTO questions (test_id, ext_id, position, type, topic,
                                       difficulty, points, prompt, prompt_math,
                                       payload, explanation)
               VALUES (?, ?, ?, 'single_choice', 'X', 'mittel', 2, 'p', NULL, '{}', NULL)""",
            (synth_id, f"sq{i}", i),
        )
    conn.commit()
    # Still false — synthetic doesn't count
    assert has_enough_questions(conn, uid) is False


def test_build_returns_none_when_insufficient(conn, uid):
    _import_test_with_topics(conn, uid, "Mathe", ["A", "B"])  # only 2
    assert build_daily_test(conn, uid, date(2026, 5, 14)) is None


def test_build_creates_synthetic_test_with_subject_daily_five(conn, uid):
    test_id = _import_test_with_topics(conn, uid, "Mathe", ["T1", "T2", "T3", "T4", "T5"])
    # Practice some questions wrongly so they're "weak"
    _record_answer(conn, uid, test_id, "q1", correct=False)
    _record_answer(conn, uid, test_id, "q2", correct=False)
    _record_answer(conn, uid, test_id, "q3", correct=True)

    new_test_id = build_daily_test(conn, uid, date(2026, 5, 14))
    assert new_test_id is not None

    row = conn.execute("SELECT * FROM tests WHERE id = ?", (new_test_id,)).fetchone()
    assert row["subject"] == "Daily-5"
    assert row["is_study"] == 1
    assert row["title"].startswith("Daily-5")

    questions = conn.execute(
        "SELECT * FROM questions WHERE test_id = ? ORDER BY position",
        (new_test_id,),
    ).fetchall()
    assert len(questions) == 5


def test_build_picks_2_2_1_from_weakest_topics(conn, uid):
    # Provide enough questions per topic for the 2-2-1 quota to fit fully into weak set:
    # WeakA needs 2 questions, WeakB needs 2, WeakC needs 1 → 5 total weak.
    test_id = _import_test_with_topics(conn, uid, "Mathe", [
        "WeakA", "WeakA",      # q1, q2
        "WeakB", "WeakB",      # q3, q4
        "WeakC",                # q5
        "Strong1", "Strong2",  # q6, q7 (won't be picked)
    ])
    # Make WeakA/WeakB/WeakC weak (all wrong)
    for ext_id in ["q1", "q2", "q3", "q4", "q5"]:
        _record_answer(conn, uid, test_id, ext_id, correct=False)
    # Make Strong1/Strong2 strong (correct)
    _record_answer(conn, uid, test_id, "q6", correct=True)
    _record_answer(conn, uid, test_id, "q7", correct=True)

    new_test_id = build_daily_test(conn, uid, date(2026, 5, 14))
    assert new_test_id is not None
    rows = conn.execute(
        "SELECT topic FROM questions WHERE test_id = ?", (new_test_id,)
    ).fetchall()
    topics = [r["topic"] for r in rows]
    weak_set = {"WeakA", "WeakB", "WeakC"}
    # All 5 must be from the weak set since the pool covers the 2-2-1 quota exactly
    assert all(t in weak_set for t in topics), f"unexpected topics: {topics}"
    assert len(topics) == 5
    # Specifically 2x WeakA, 2x WeakB, 1x WeakC
    assert topics.count("WeakA") == 2
    assert topics.count("WeakB") == 2
    assert topics.count("WeakC") == 1


def test_build_falls_back_to_random_when_no_weak_topics(conn, uid):
    # Import 5 questions, all answered correctly → no weak topics
    test_id = _import_test_with_topics(conn, uid, "Mathe", ["A", "B", "C", "D", "E"])
    for ext_id in ["q1", "q2", "q3", "q4", "q5"]:
        _record_answer(conn, uid, test_id, ext_id, correct=True)
    new_test_id = build_daily_test(conn, uid, date(2026, 5, 14))
    assert new_test_id is not None
    questions = conn.execute(
        "SELECT COUNT(*) AS n FROM questions WHERE test_id = ?", (new_test_id,)
    ).fetchone()
    assert questions["n"] == 5

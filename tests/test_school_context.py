import pytest
import sqlite3

from school_test_engine.prompt_builder.school_context import (
    BUNDESLAENDER,
    SCHOOL_TYPES,
    SchoolContext,
)


def test_constants_present():
    assert SCHOOL_TYPES == ["Hauptschule", "Realschule", "Gymnasium"]
    assert "Hessen" in BUNDESLAENDER
    assert len(BUNDESLAENDER) == 16


def test_from_user_row_none():
    ctx = SchoolContext.from_user_row(None)
    assert ctx.grade is None
    assert ctx.school_type is None
    assert ctx.bundesland is None
    assert ctx.school_name is None
    assert ctx.school_year is None


def test_from_user_row_full():
    row = {
        "grade": 8,
        "school_type": "Realschule",
        "bundesland": "Hessen",
        "school_name": "Heine-RS",
        "school_year": "2025/26",
    }
    ctx = SchoolContext.from_user_row(row)
    assert ctx.grade == 8
    assert ctx.school_type == "Realschule"
    assert ctx.bundesland == "Hessen"
    assert ctx.school_name == "Heine-RS"
    assert ctx.school_year == "2025/26"


def test_from_user_row_partial():
    row = {
        "grade": 9,
        "school_type": "Gymnasium",
        "bundesland": None,
        "school_name": None,
        "school_year": None,
    }
    ctx = SchoolContext.from_user_row(row)
    assert ctx.grade == 9
    assert ctx.school_type == "Gymnasium"
    assert ctx.bundesland is None


def test_grade_coerced_from_string():
    row = {"grade": "8", "school_type": "Realschule",
           "bundesland": None, "school_name": None, "school_year": None}
    ctx = SchoolContext.from_user_row(row)
    assert ctx.grade == 8


def test_grade_coerced_invalid_string_to_none():
    row = {"grade": "abc", "school_type": "Realschule",
           "bundesland": None, "school_name": None, "school_year": None}
    ctx = SchoolContext.from_user_row(row)
    assert ctx.grade is None


def test_is_minimally_complete_when_both_required():
    ctx = SchoolContext(grade=8, school_type="Realschule",
                       bundesland=None, school_name=None, school_year=None)
    assert ctx.is_minimally_complete() is True


def test_is_minimally_complete_false_when_grade_none():
    ctx = SchoolContext(grade=None, school_type="Realschule",
                       bundesland="Hessen", school_name=None, school_year=None)
    assert ctx.is_minimally_complete() is False


def test_is_minimally_complete_false_when_school_type_none():
    ctx = SchoolContext(grade=8, school_type=None,
                       bundesland="Hessen", school_name=None, school_year=None)
    assert ctx.is_minimally_complete() is False


def test_is_minimally_complete_false_when_school_type_empty():
    ctx = SchoolContext(grade=8, school_type="",
                       bundesland="Hessen", school_name=None, school_year=None)
    assert ctx.is_minimally_complete() is False


def test_works_with_sqlite_row(tmp_path):
    """Real sqlite3.Row must work, not just dicts. NOTE: This test depends on
    users_repo.update_user supporting the new school-context kwargs (added in
    Task 3). It will fail until Task 3 lands."""
    from school_test_engine.storage import connect, run_migrations, users_repo
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    uid = users_repo.create_user(c, "Test", "🧒")
    users_repo.update_user(c, uid, grade=10, school_type="Gymnasium",
                           bundesland="Bayern", school_name="X-Gymi", school_year="2025/26")
    row = users_repo.get_user(c, uid)
    ctx = SchoolContext.from_user_row(row)
    assert ctx.grade == 10
    assert ctx.school_type == "Gymnasium"
    c.close()

import pytest
from datetime import date

from school_test_engine.storage import connect, run_migrations, users_repo
from school_test_engine.storage import daily_sessions_repo
from school_test_engine.daily.streak import current_streak


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


def _record_complete_day(conn, uid, d: str) -> None:
    daily_sessions_repo.start_session(
        conn, uid, d, test_id=None, attempt_id=None, started_at=d + "T08:00:00",
    )
    daily_sessions_repo.complete_session(conn, uid, d, completed_at=d + "T08:05:00")


def test_empty_returns_zero(conn, uid):
    assert current_streak(conn, uid, date(2026, 5, 14)) == 0


def test_today_completed_returns_one(conn, uid):
    _record_complete_day(conn, uid, "2026-05-14")
    assert current_streak(conn, uid, date(2026, 5, 14)) == 1


def test_yesterday_only_returns_one(conn, uid):
    _record_complete_day(conn, uid, "2026-05-13")
    # Today not done yet — streak counts backwards from yesterday
    assert current_streak(conn, uid, date(2026, 5, 14)) == 1


def test_three_consecutive_days_with_today_returns_three(conn, uid):
    for d in ["2026-05-12", "2026-05-13", "2026-05-14"]:
        _record_complete_day(conn, uid, d)
    assert current_streak(conn, uid, date(2026, 5, 14)) == 3


def test_three_consecutive_ending_yesterday_returns_three(conn, uid):
    for d in ["2026-05-11", "2026-05-12", "2026-05-13"]:
        _record_complete_day(conn, uid, d)
    # Today not done — streak still 3
    assert current_streak(conn, uid, date(2026, 5, 14)) == 3


def test_gap_resets_streak(conn, uid):
    # Pattern: 12, 14 (skip 13). Today=14. Streak counts only 14.
    _record_complete_day(conn, uid, "2026-05-12")
    _record_complete_day(conn, uid, "2026-05-14")
    assert current_streak(conn, uid, date(2026, 5, 14)) == 1


def test_in_progress_day_does_not_count(conn, uid):
    # Today started but NOT completed → streak counts only completed days before
    _record_complete_day(conn, uid, "2026-05-13")
    daily_sessions_repo.start_session(
        conn, uid, "2026-05-14", test_id=None, attempt_id=None,
        started_at="2026-05-14T08:00:00",
    )
    # No complete_session call → completed_at IS NULL
    assert current_streak(conn, uid, date(2026, 5, 14)) == 1  # only yesterday


def test_user_isolation(conn):
    a = users_repo.create_user(conn, "A")
    b = users_repo.create_user(conn, "B")
    _record_complete_day(conn, a, "2026-05-14")
    assert current_streak(conn, a, date(2026, 5, 14)) == 1
    assert current_streak(conn, b, date(2026, 5, 14)) == 0

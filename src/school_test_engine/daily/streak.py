from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from ..storage import daily_sessions_repo


def current_streak(
    conn: sqlite3.Connection,
    user_id: int,
    today: date,
) -> int:
    """Count consecutive completed days ending today (or yesterday, if today
    is not yet completed). Returns 0 if no completed sessions.
    """
    since = (today - timedelta(days=400)).isoformat()
    until = today.isoformat()
    completed = set(daily_sessions_repo.list_recent_completed_dates(
        conn, user_id, since=since, until=until,
    ))

    if not completed:
        return 0

    streak = 0
    cursor = today
    # If today not completed, streak counts backwards starting from yesterday
    if cursor.isoformat() not in completed:
        cursor -= timedelta(days=1)
    while cursor.isoformat() in completed:
        streak += 1
        cursor -= timedelta(days=1)
    return streak

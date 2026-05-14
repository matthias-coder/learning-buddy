from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..storage import daily_sessions_repo


def finalize_if_daily(conn: sqlite3.Connection, attempt_id: int) -> bool:
    """If `attempt_id` belongs to an open daily_sessions row, mark it complete.

    Returns True if a session was finalized, False otherwise (non-daily attempt
    OR session already completed).
    """
    row = conn.execute(
        "SELECT user_id, session_date FROM daily_sessions "
        "WHERE attempt_id = ? AND completed_at IS NULL",
        (attempt_id,),
    ).fetchone()
    if row is None:
        return False
    daily_sessions_repo.complete_session(
        conn,
        row["user_id"],
        row["session_date"],
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    return True

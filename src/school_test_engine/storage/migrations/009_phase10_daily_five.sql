-- Phase 10: Daily-5 Session-Tracking

CREATE TABLE IF NOT EXISTS daily_sessions (
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_date TEXT    NOT NULL,
    test_id      INTEGER REFERENCES tests(id) ON DELETE SET NULL,
    attempt_id   INTEGER REFERENCES attempts(id) ON DELETE SET NULL,
    started_at   TEXT    NOT NULL,
    completed_at TEXT,
    PRIMARY KEY (user_id, session_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_user_date
    ON daily_sessions(user_id, session_date);

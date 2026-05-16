-- Phase 17: Schulkalender — calendar_events + per-user filter state

CREATE TABLE IF NOT EXISTS calendar_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            TEXT    NOT NULL
                    CHECK (kind IN ('ferien', 'frei', 'event')),
    title           TEXT    NOT NULL,
    start_date      TEXT    NOT NULL,
    end_date        TEXT    NOT NULL,
    external_uid    TEXT,
    external_source TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_user_date
    ON calendar_events(user_id, start_date);

CREATE UNIQUE INDEX IF NOT EXISTS idx_calendar_events_external_uid
    ON calendar_events(user_id, external_uid)
    WHERE external_uid IS NOT NULL;

ALTER TABLE users ADD COLUMN calendar_show_klausuren INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_show_ferien    INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_show_frei      INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_show_events    INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN calendar_timeframe      TEXT    NOT NULL DEFAULT 'future'
                                                       CHECK (calendar_timeframe IN ('future', 'all', 'past'));

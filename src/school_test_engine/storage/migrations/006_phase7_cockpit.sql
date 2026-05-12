-- Phase 7: Schul-Cockpit — Termine + echte Noten

CREATE TABLE IF NOT EXISTS scheduled_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject     TEXT    NOT NULL,
    kind        TEXT    NOT NULL CHECK (kind IN ('klassenarbeit','klausur','test','sonstiges')),
    event_date  TEXT    NOT NULL,
    topics      TEXT    NOT NULL DEFAULT '[]',
    note        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scheduled_user_date
    ON scheduled_events(user_id, event_date);

CREATE TABLE IF NOT EXISTS assessments (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject            TEXT    NOT NULL,
    category           TEXT    NOT NULL CHECK (category IN ('schriftlich','muendlich','sonstige')),
    assessment_date    TEXT    NOT NULL,
    grade              REAL    NOT NULL,
    points             REAL,
    max_points         REAL,
    note               TEXT,
    scheduled_event_id INTEGER REFERENCES scheduled_events(id) ON DELETE SET NULL,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_assessments_user_subject
    ON assessments(user_id, subject);
CREATE INDEX IF NOT EXISTS idx_assessments_event
    ON assessments(scheduled_event_id);

-- Phase 8: Test bauen — KI-Stil-Briefing pro User + Prompt-Drafts pro (User, Fach)

ALTER TABLE users ADD COLUMN ai_style_briefing TEXT;

CREATE TABLE IF NOT EXISTS prompt_drafts (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject     TEXT    NOT NULL,
    last_topic  TEXT,
    last_count  INTEGER NOT NULL DEFAULT 10,
    last_dist   TEXT    NOT NULL DEFAULT 'auto',
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, subject)
);

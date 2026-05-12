-- Phase 6: Multi-User-Profile

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    avatar      TEXT    NOT NULL DEFAULT '👤',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_sort ON users(sort_order, created_at);

-- Platzhalter-User. Existierende Tests werden ihm zugeordnet.
INSERT INTO users (id, name, avatar, sort_order, created_at)
VALUES (1, 'Standard', '👤', 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));

-- Versuche werden gelöscht (Matthias' Entscheidung)
DELETE FROM answers;
DELETE FROM attempts;

-- Spalten anhängen mit DEFAULT 1 → existierende Tests werden Platzhalter zugeordnet.
-- ACHTUNG: SQLite verbietet ALTER TABLE ADD COLUMN mit FK + non-NULL-DEFAULT.
-- Daher legen wir die Spalte ohne REFERENCES an; das Cascade-Löschen erledigt
-- users_repo.delete_user() explizit (DELETE FROM tests WHERE user_id = ? usw.).
ALTER TABLE tests
    ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1;

ALTER TABLE attempts
    ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_tests_user ON tests(user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user_completed ON attempts(user_id, completed);

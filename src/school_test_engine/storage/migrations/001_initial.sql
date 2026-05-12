CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS tests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    subject         TEXT    NOT NULL,
    grade           INTEGER NOT NULL,
    school_type     TEXT    NOT NULL,
    description     TEXT,
    time_limit_min  INTEGER,
    notenschluessel TEXT    NOT NULL,
    source_json     TEXT    NOT NULL,
    imported_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id         INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    ext_id          TEXT    NOT NULL,
    position        INTEGER NOT NULL,
    type            TEXT    NOT NULL,
    topic           TEXT    NOT NULL,
    difficulty      TEXT    NOT NULL,
    points          INTEGER NOT NULL,
    prompt          TEXT    NOT NULL,
    prompt_math     TEXT,
    payload         TEXT    NOT NULL,
    explanation     TEXT
);

CREATE INDEX IF NOT EXISTS idx_questions_test  ON questions(test_id);
CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic);

CREATE TABLE IF NOT EXISTS attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id         INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    started_at      TEXT    NOT NULL,
    finished_at     TEXT,
    points_earned   REAL,
    points_possible INTEGER NOT NULL,
    percent         REAL,
    note            INTEGER,
    shuffle_seed    INTEGER,
    completed       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_attempts_test     ON attempts(test_id);
CREATE INDEX IF NOT EXISTS idx_attempts_finished ON attempts(finished_at);

CREATE TABLE IF NOT EXISTS answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id      INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    question_id     INTEGER NOT NULL REFERENCES questions(id),
    response        TEXT    NOT NULL,
    points_earned   REAL    NOT NULL,
    is_correct      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_answers_attempt  ON answers(attempt_id);
CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(question_id);

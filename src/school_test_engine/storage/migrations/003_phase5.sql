-- Phase 5: Study-Mode

ALTER TABLE tests ADD COLUMN is_study INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_tests_is_study ON tests(is_study);

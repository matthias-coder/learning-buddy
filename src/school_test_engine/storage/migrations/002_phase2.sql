-- Phase 2: Skip / Mark / Save-and-Resume

ALTER TABLE attempts ADD COLUMN current_index INTEGER NOT NULL DEFAULT 0;

ALTER TABLE answers ADD COLUMN marked INTEGER NOT NULL DEFAULT 0;

-- De-dupe (sollte aus MVP nicht vorkommen, aber sicher ist sicher):
-- Behalte nur die jeweils höchste id pro (attempt_id, question_id).
DELETE FROM answers
WHERE id NOT IN (
    SELECT MAX(id) FROM answers GROUP BY attempt_id, question_id
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_answers_unique
    ON answers(attempt_id, question_id);

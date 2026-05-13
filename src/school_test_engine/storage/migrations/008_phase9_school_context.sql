-- Phase 9: Schul-Kontext pro User-Profil

ALTER TABLE users ADD COLUMN grade INTEGER;
ALTER TABLE users ADD COLUMN school_type TEXT;
ALTER TABLE users ADD COLUMN bundesland TEXT;
ALTER TABLE users ADD COLUMN school_name TEXT;
ALTER TABLE users ADD COLUMN school_year TEXT;

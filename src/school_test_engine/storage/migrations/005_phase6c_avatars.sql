-- Phase 6C-Erweiterung: Foto-Avatar + Geburtsdatum

ALTER TABLE users ADD COLUMN avatar_image BLOB;
ALTER TABLE users ADD COLUMN birthday TEXT;

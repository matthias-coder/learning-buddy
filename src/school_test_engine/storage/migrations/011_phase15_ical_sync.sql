-- Phase 15: iCal-sync columns + unique index on (user_id, external_uid)

ALTER TABLE users ADD COLUMN ical_feed_url TEXT;
ALTER TABLE users ADD COLUMN ical_last_sync_at TEXT;
ALTER TABLE users ADD COLUMN ical_last_sync_summary TEXT;

ALTER TABLE scheduled_events ADD COLUMN external_uid TEXT;
ALTER TABLE scheduled_events ADD COLUMN external_source TEXT;

CREATE UNIQUE INDEX idx_events_external_uid
  ON scheduled_events(user_id, external_uid)
  WHERE external_uid IS NOT NULL;

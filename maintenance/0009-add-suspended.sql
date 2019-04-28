--- Add a background_suspended_until_utc_timestamp column to the background table,
--- to track when a background run has been suspended for a while due to a command failure.

ALTER TABLE background
ADD COLUMN background_suspended_until_utc_timestamp int unsigned AFTER background_stopped_localuser_id;

-- Replace the background_stopped_batch index
-- on just the background_stopped_utc_timestamp and background_batch columns of the background table
-- with a background_stopped_suspended_batch index
-- including the new background_suspended_until_utc_timestamp column.

CREATE INDEX background_stopped_suspended_batch ON background (background_stopped_utc_timestamp, background_suspended_until_utc_timestamp, background_batch);

DROP INDEX background_stopped_batch ON background;

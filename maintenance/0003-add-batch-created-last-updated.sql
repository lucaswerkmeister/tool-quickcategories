--- Add batch_created_utc_timestamp and batch_last_updated_utc_timestamp columns to the batch table.

ALTER TABLE batch
ADD COLUMN batch_created_utc_timestamp double unsigned DEFAULT NULL AFTER batch_domain_id,
ADD COLUMN batch_last_updated_utc_timestamp double unsigned DEFAULT NULL AFTER batch_created_utc_timestamp;

--- If you can get the timestamps from some other source,
--- e. g. server access logs,
--- then set them manually.
--- Otherwise, we fall back to the Unix epoch
--- so that we at least don’t have to deal with NULL values in the future
--- (this is only acceptable for test/development installations):
UPDATE batch
SET batch_created_utc_timestamp = 0.0;
UPDATE batch
SET batch_last_updated_utc_timestamp = 0.0;

ALTER TABLE batch
MODIFY batch_created_utc_timestamp double unsigned NOT NULL,
MODIFY batch_last_updated_utc_timestamp double unsigned NOT NULL;

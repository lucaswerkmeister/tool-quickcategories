--- Change the batch_created_utc_timestamp and batch_last_updated_utc_timestamp columns of the batch table
--- from double to int, since we don’t need sub-second precision.

ALTER TABLE batch
MODIFY batch_created_utc_timestamp int unsigned NOT NULL,
MODIFY batch_last_updated_utc_timestamp int unsigned NOT NULL;

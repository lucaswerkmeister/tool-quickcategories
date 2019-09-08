--- Rename columns that point to other tables
--- to drop the _id suffix (where it exists).

ALTER TABLE batch
CHANGE batch_localuser_id batch_localuser int unsigned NOT NULL,
CHANGE batch_domain_id batch_domain int unsigned NOT NULL;

ALTER TABLE command
CHANGE command_actions_id command_actions int unsigned NOT NULL;

ALTER TABLE background
CHANGE background_started_localuser_id background_started_localuser int unsigned NOT NULL,
CHANGE background_stopped_localuser_id background_stopped_localuser int unsigned;

ALTER TABLE localuser
CHANGE localuser_domain_id localuser_domain int unsigned NOT NULL;

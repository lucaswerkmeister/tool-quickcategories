-- Add the background table, which records when a batch can be run in the background.

CREATE TABLE background (
  background_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  background_batch int unsigned NOT NULL,
  background_auth text,
  background_started_utc_timestamp int unsigned NOT NULL,
  background_started_user_name varchar(255) binary NOT NULL,
  background_started_local_user_id int unsigned NOT NULL,
  background_started_global_user_id int unsigned NOT NULL,
  background_stopped_utc_timestamp int unsigned,
  background_stopped_user_name varchar(255) binary,
  background_stopped_local_user_id int unsigned,
  background_stopped_global_user_id int unsigned
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- index for finding the backgrounds of a batch, optionally limited to just the ones not yet stopped
CREATE INDEX background_batch_stopped ON background (background_batch, background_stopped_utc_timestamp);

-- index for finding backgrounds not yet stopped, for any batch
CREATE INDEX background_stopped_batch ON background (background_stopped_utc_timestamp, background_batch);

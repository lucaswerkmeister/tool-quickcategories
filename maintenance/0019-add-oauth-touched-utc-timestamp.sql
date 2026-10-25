--- Add an oauth_touched_utc_timestamp column to the oauth table.

ALTER TABLE oauth
ADD COLUMN oauth_touched_utc_timestamp int unsigned DEFAULT NULL AFTER oauth_access_token;

UPDATE oauth
SET oauth_touched_utc_timestamp = 1792929600;

ALTER TABLE command
MODIFY oauth_touched_utc_timestamp int unsigned NOT NULL;

CREATE INDEX oauth_touched_utc_timestamp ON oauth (oauth_touched_utc_timestamp);

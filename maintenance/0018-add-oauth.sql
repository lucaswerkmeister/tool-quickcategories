--- Move the background_auth field to the new oauth table,
--- in preparation for migration to OAuth 2.

CREATE TABLE oauth (
  oauth_global_user_id int unsigned NOT NULL PRIMARY KEY,
  oauth_access_token text NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

INSERT INTO oauth (oauth_global_user_id, oauth_access_token)
SELECT DISTINCT localuser_global_user_id, background_auth
FROM background
JOIN batch ON background_batch = batch_id
JOIN localuser ON batch_localuser = localuser_id
WHERE background_auth IS NOT NULL;

ALTER TABLE background
DROP COLUMN background_auth;

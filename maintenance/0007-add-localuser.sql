-- Add the localuser table, replacing several columns in the batch and background tables.

CREATE TABLE localuser (
  localuser_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  localuser_user_name varchar(255) binary NOT NULL,
  localuser_domain_id int unsigned NOT NULL, -- referencing domain.domain_id
  localuser_local_user_id int unsigned NOT NULL,
  localuser_global_user_id int unsigned NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- unique index for ensuring that when a user was renamed and starts a new batch,
-- we use the same localuser record, effectively updating all past batches to use the new name too
-- (with the local user ID first because it has much higher selectivity, being virtually unique on its own)
CREATE UNIQUE INDEX localuser_local_user_id_domain_id ON localuser (localuser_local_user_id, localuser_domain_id);


-- update the batch table

ALTER TABLE batch
ADD COLUMN batch_localuser_id int unsigned DEFAULT NULL AFTER batch_global_user_id;

INSERT INTO localuser (localuser_user_name, localuser_domain_id, localuser_local_user_id, localuser_global_user_id)
SELECT batch_user_name, batch_domain_id, batch_local_user_id, batch_global_user_id
FROM batch
ON DUPLICATE KEY UPDATE localuser_user_name=batch_user_name;

UPDATE batch
SET batch_localuser_id = (
  SELECT localuser_id
  FROM localuser
  WHERE localuser_local_user_id = batch_local_user_id
  AND localuser_domain_id = batch_domain_id
);

ALTER TABLE batch
MODIFY COLUMN batch_localuser_id int unsigned NOT NULL,
DROP COLUMN batch_user_name,
DROP COLUMN batch_local_user_id,
DROP COLUMN batch_global_user_id;


-- update the background table

ALTER TABLE background
ADD COLUMN background_started_localuser_id int unsigned DEFAULT NULL AFTER background_started_global_user_id,
ADD COLUMN background_stopped_localuser_id int unsigned DEFAULT NULL AFTER background_stopped_global_user_id;

INSERT INTO localuser (localuser_user_name, localuser_domain_id, localuser_local_user_id, localuser_global_user_id)
SELECT background_started_user_name, batch_domain_id, background_started_local_user_id, background_started_global_user_id
FROM background
JOIN batch ON background_batch = batch_id
ON DUPLICATE KEY UPDATE localuser_user_name=background_started_user_name;

INSERT INTO localuser (localuser_user_name, localuser_domain_id, localuser_local_user_id, localuser_global_user_id)
SELECT background_stopped_user_name, batch_domain_id, background_stopped_local_user_id, background_stopped_global_user_id
FROM background
JOIN batch ON background_batch = batch_id
WHERE background_stopped_user_name IS NOT NULL
ON DUPLICATE KEY UPDATE localuser_user_name=background_stopped_user_name;

UPDATE background
SET background_started_localuser_id = (
  SELECT localuser_id
  FROM localuser
  WHERE localuser_local_user_id = background_started_local_user_id
  AND localuser_domain_id = (
    SELECT batch_domain_id
    FROM batch
    WHERE batch_id = background_batch
  )
);

UPDATE background
SET background_stopped_localuser_id = (
  SELECT localuser_id
  FROM localuser
  WHERE localuser_local_user_id = background_stopped_local_user_id
  AND localuser_domain_id = (
    SELECT batch_domain_id
    FROM batch
    WHERE batch_id = background_batch
  )
)
WHERE background_stopped_utc_timestamp IS NOT NULL
AND background_stopped_local_user_id IS NOT NULL;

ALTER TABLE background
MODIFY COLUMN background_started_localuser_id int unsigned NOT NULL,
MODIFY COLUMN background_stopped_localuser_id int unsigned,
DROP COLUMN background_started_user_name,
DROP COLUMN background_started_local_user_id,
DROP COLUMN background_started_global_user_id,
DROP COLUMN background_stopped_user_name,
DROP COLUMN background_stopped_local_user_id,
DROP COLUMN background_stopped_global_user_id;

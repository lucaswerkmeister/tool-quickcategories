-- stored batches
CREATE TABLE batch (
  batch_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, -- public, also used to identify batches in URLs and on the page
  batch_localuser_id int unsigned NOT NULL, -- referencing localuser.localuser_id
  batch_domain_id int unsigned NOT NULL, -- referencing domain.domain_id
  batch_created_utc_timestamp int unsigned NOT NULL,
  batch_last_updated_utc_timestamp int unsigned NOT NULL,
  batch_status int unsigned NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';


-- commands to be performed for each batch
CREATE TABLE command (
  command_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  command_batch int unsigned NOT NULL, -- referencing batch.batch_id
  command_page text NOT NULL,
  command_actions_id int unsigned NOT NULL, -- referencing actions.actions_id
  command_status int unsigned NOT NULL,
  command_outcome text
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- index for finding commands of a certain batch, optionally filtering by status
-- (e. g. background runner wants the first planned command of a certain batch)
CREATE INDEX command_batch_status ON command (command_batch, command_status);


-- wiki domains (normalized)
CREATE TABLE domain (
  domain_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  domain_hash int unsigned NOT NULL, -- first four bytes of the SHA2-256 hash of the domain_name
  domain_name varchar(255) binary NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- index for finding a domain ID by its hash
CREATE INDEX domain_hash ON domain (domain_hash);


-- actions of commands (normalized)
-- table name is plural because an individual row lists multiple actions (they are not split up)
CREATE TABLE actions (
  actions_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  actions_hash int unsigned NOT NULL, -- first four bytes of the SHA2-256 hash of the actions_tpsv
  actions_tpsv text NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- index for finding an actions ID by its hash
CREATE INDEX actions_hash ON actions (actions_hash);


-- background runs of batches
CREATE TABLE background (
  background_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  background_batch int unsigned NOT NULL, -- referencing batch.batch_id
  background_auth text, -- NULL after the background run was stopped
  background_started_utc_timestamp int unsigned NOT NULL,
  background_started_localuser_id int unsigned NOT NULL, -- referencing localuser.localuser_id
  background_stopped_utc_timestamp int unsigned,
  background_stopped_localuser_id int unsigned -- referencing localuser.localuser_id
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- index for finding the backgrounds of a batch, optionally limited to just the ones not yet stopped
CREATE INDEX background_batch_stopped ON background (background_batch, background_stopped_utc_timestamp);

-- index for finding backgrounds not yet stopped, for any batch
CREATE INDEX background_stopped_batch ON background (background_stopped_utc_timestamp, background_batch);


-- user accounts local to wikis
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


-- retries of certain failed commands, linking the original to the retried command row
CREATE TABLE retry (
  retry_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  retry_failure int unsigned NOT NULL, -- referencing command.command_id
  retry_new int unsigned NOT NULL -- referencing command.command_id
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

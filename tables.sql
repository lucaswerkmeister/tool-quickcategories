CREATE TABLE batch (
  batch_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  batch_user_name varchar(255) binary NOT NULL,
  batch_local_user_id int unsigned NOT NULL,
  batch_global_user_id int unsigned NOT NULL,
  batch_domain_id int unsigned NOT NULL,
  batch_created_utc_timestamp int unsigned NOT NULL,
  batch_last_updated_utc_timestamp int unsigned NOT NULL,
  batch_status int unsigned NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';


CREATE TABLE command (
  command_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  command_batch int unsigned NOT NULL,
  command_page text NOT NULL,
  command_actions_id int unsigned NOT NULL,
  command_status int unsigned NOT NULL,
  command_outcome text
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

CREATE INDEX command_batch_status ON command (command_batch, command_status);


CREATE TABLE domain (
  domain_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  domain_hash int unsigned NOT NULL, -- first four bytes of the SHA2-256 hash of the domain_name
  domain_name varchar(255) binary NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

CREATE INDEX domain_hash ON domain (domain_hash);


CREATE TABLE actions (
  actions_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  actions_hash int unsigned NOT NULL, -- first four bytes of the SHA2-256 hash of the actions_tpsv
  actions_tpsv text NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

CREATE INDEX actions_hash ON actions (actions_hash);


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

-- stored batches
CREATE TABLE batch (
  batch_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT, -- public, also used to identify batches in URLs and on the page
  batch_localuser int unsigned NOT NULL, -- referencing localuser.localuser_id
  batch_domain int unsigned NOT NULL, -- referencing domain.domain_id
  batch_title int unsigned, -- referencing title.title_id
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
  command_page_title text NOT NULL,
  command_page_resolve_redirects bool,
  command_actions int unsigned NOT NULL, -- referencing actions.actions_id
  command_status int unsigned NOT NULL,
  command_outcome text
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- index for finding commands of a certain batch in command ID order,
-- used when listing (slices of) batches or export-streaming them
CREATE INDEX command_batch ON command (command_batch);

-- index for finding commands of a certain batch with a certain status,
-- used by the batch summary and by the background runner (first planned command of a certain batch)
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


-- batch titles (normalized)
CREATE TABLE title (
  title_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  title_hash int unsigned NOT NULL, -- first four bytes of the SHA2-256 hash of the title_text
  title_text varchar(255) binary NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- index for finding a title ID by its hash
CREATE INDEX title_hash ON title (title_hash);


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
  background_started_localuser int unsigned NOT NULL, -- referencing localuser.localuser_id
  background_stopped_utc_timestamp int unsigned,
  background_stopped_localuser int unsigned, -- referencing localuser.localuser_id
  background_suspended_until_utc_timestamp int unsigned
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- index for finding the backgrounds of a batch, optionally limited to just the ones not yet stopped
CREATE INDEX background_batch_stopped ON background (background_batch, background_stopped_utc_timestamp);

-- index for finding backgrounds not yet stopped nor suspended, for any batch
CREATE INDEX background_stopped_suspended_batch ON background (background_stopped_utc_timestamp, background_suspended_until_utc_timestamp, background_batch);


-- user accounts local to wikis
CREATE TABLE localuser (
  localuser_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  localuser_user_name varchar(255) binary NOT NULL,
  localuser_domain int unsigned NOT NULL, -- referencing domain.domain_id
  localuser_local_user_id int unsigned NOT NULL,
  localuser_global_user_id int unsigned NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- unique index for ensuring that when a user was renamed and starts a new batch,
-- we use the same localuser record, effectively updating all past batches to use the new name too
-- (with the local user ID first because it has much higher selectivity, being virtually unique on its own)
CREATE UNIQUE INDEX localuser_local_user_id_domain_id ON localuser (localuser_local_user_id, localuser_domain);


-- retries of certain failed commands, linking the original to the retried command row
CREATE TABLE retry (
  retry_failure int unsigned NOT NULL PRIMARY KEY, -- referencing command.command_id
  retry_new int unsigned NOT NULL -- referencing command.command_id
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';
-- we could enforce the bijection with a unique index on retry_new but it hardly seems necessary


-- persistent user preferences
CREATE TABLE preference (
  preference_global_user_id int unsigned NOT NULL,
  preference_key int unsigned NOT NULL,
  preference_value int unsigned NOT NULL,
  PRIMARY KEY(preference_global_user_id, preference_key)
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';


-- runtime of SQL queries, to investigate what needs to be optimized
CREATE TABLE querytime (
  querytime_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  querytime_utc_timestamp int unsigned NOT NULL, -- time when the query was run
  querytime_querytext int unsigned NOT NULL, -- referencing querytext.querytext_id
  querytime_duration double unsigned NOT NULL -- duration in seconds
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- index for finding long queries in a certain timespan, with the querytext added to make the index covering
CREATE INDEX querytime_utc_timestamp_duration_querytext ON querytime (querytime_utc_timestamp, querytime_duration, querytime_querytext);


-- text of SQL queries (normalized)
CREATE TABLE querytext (
  querytext_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  querytext_hash int unsigned NOT NULL, -- first four bytes of the SHA2-256 hash of the querytext_sql
  querytext_sql text NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

-- index for finding a querytext ID by its hash
CREATE INDEX querytext_hash ON querytext (querytext_hash);

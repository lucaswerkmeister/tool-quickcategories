CREATE TABLE batch (
  batch_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  batch_user_name varchar(255) binary NOT NULL,
  batch_local_user_id int unsigned NOT NULL,
  batch_global_user_id int unsigned NOT NULL,
  batch_domain varchar(255) binary NOT NULL,
  batch_status int unsigned NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

CREATE TABLE command (
  command_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  command_batch int unsigned NOT NULL,
  command_tpsv text NOT NULL,
  command_status int unsigned NOT NULL,
  command_outcome text
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

CREATE INDEX command_batch ON command (command_batch);

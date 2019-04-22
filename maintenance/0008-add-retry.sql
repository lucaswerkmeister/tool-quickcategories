-- Add the retry table, tracking retries of certain failed commands, linking the original to the retried command row.

CREATE TABLE retry (
  retry_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  retry_failure int unsigned NOT NULL, -- referencing command.command_id
  retry_new int unsigned NOT NULL -- referencing command.command_id
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

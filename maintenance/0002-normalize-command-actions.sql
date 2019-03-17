--- Split the command_tpsv column of the command table
--- into a command_page column and a command_actions_id column pointing to a separate actions table

CREATE TABLE actions (
  actions_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  actions_hash int unsigned NOT NULL, -- first four bytes of the SHA2-256 hash of the actions_tpsv
  actions_tpsv text NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin'
SELECT DISTINCT SUBSTRING(command_tpsv FROM LOCATE("|", command_tpsv) + 1) AS actions_tpsv,
  CAST(CONV(SUBSTRING(SHA2(SUBSTRING(command_tpsv FROM LOCATE("|", command_tpsv) + 1), 256), 1, 8), 16, 10) AS unsigned int) AS actions_hash
FROM command;

CREATE INDEX actions_hash ON actions (actions_hash);

ALTER TABLE command
ADD COLUMN command_page text DEFAULT NULL AFTER command_tpsv,
ADD COLUMN command_actions_id int unsigned DEFAULT NULL AFTER command_page;

UPDATE command
SET command_page = SUBSTRING(command_tpsv FROM 1 FOR LOCATE("|", command_tpsv) - 1);

UPDATE command
SET command_actions_id = (
  SELECT actions_id
  FROM actions
  WHERE actions_hash = CAST(CONV(SUBSTRING(SHA2(SUBSTRING(command_tpsv FROM LOCATE("|", command_tpsv) + 1), 256), 1, 8), 16, 10) AS unsigned int)
);

ALTER TABLE command
MODIFY command_page text NOT NULL,
MODIFY command_actions_id int unsigned NOT NULL,
DROP COLUMN command_tpsv;

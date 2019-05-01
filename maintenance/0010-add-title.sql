--- Add a batch_title column to the batch table,
--- normalized via a title table.

CREATE TABLE title (
  title_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  title_hash int unsigned NOT NULL, -- first four bytes of the SHA2-256 hash of the title_text
  title_text varchar(255) binary NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

CREATE INDEX title_hash ON title (title_hash);


ALTER TABLE batch
ADD COLUMN batch_title int unsigned DEFAULT NULL AFTER batch_domain_id;

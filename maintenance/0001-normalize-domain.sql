-- Replace the batch_domain column of the batch table
-- with a batch_domain_id column pointing to a separate domain table.

CREATE TABLE domain (
  domain_id int unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  domain_hash int unsigned NOT NULL, -- first four bytes of the SHA2-256 hash of the domain_name
  domain_name varchar(255) binary NOT NULL
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin'
SELECT DISTINCT batch_domain AS domain_name, CAST(CONV(SUBSTRING(SHA2(batch_domain, 256), 1, 8), 16, 10) AS unsigned int) AS domain_hash
FROM batch;

CREATE INDEX domain_hash ON domain (domain_hash);


ALTER TABLE batch
ADD COLUMN batch_domain_id int unsigned DEFAULT NULL AFTER batch_domain;

UPDATE batch
SET batch_domain_id = (
  SELECT domain_id
  FROM domain
  WHERE domain_hash = CAST(CONV(SUBSTRING(SHA2(batch_domain, 256), 1, 8), 16, 10) AS unsigned int)
);

ALTER TABLE batch
MODIFY batch_domain_id int unsigned NOT NULL,
DROP COLUMN batch_domain;

-- Add a querytime table tracking the duration of SQL queries,
-- to optimize which ones should be optimized,
-- with the query texts normalized via a querytext table.

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

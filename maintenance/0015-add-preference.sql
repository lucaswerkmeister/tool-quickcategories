--- Add the preference table, storing persistent user preferences
--- where the background runner can access them.
CREATE TABLE preference (
  preference_global_user_id int unsigned NOT NULL,
  preference_key int unsigned NOT NULL,
  preference_value int unsigned NOT NULL,
  PRIMARY KEY(preference_global_user_id, preference_key)
)
CHARACTER SET = 'utf8mb4'
COLLATE = 'utf8mb4_bin';

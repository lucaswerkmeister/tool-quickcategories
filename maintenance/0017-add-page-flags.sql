--- Replace the command_page_resolve_redirects column of the command table
--- with the command_page_flags column, where true in the old column means 1 in the new column
--- and NULL in the old column means 2 in the new column.

ALTER TABLE command
ADD COLUMN command_page_flags tinyint unsigned DEFAULT NULL AFTER command_page_title;

UPDATE command
SET command_page_flags = IF(command_page_resolve_redirects IS NULL, 2, IF(command_page_resolve_redirects, 1, 0)) | 8;

ALTER TABLE command
MODIFY command_page_flags tinyint unsigned NOT NULL,
DROP COLUMN command_page_resolve_redirects;

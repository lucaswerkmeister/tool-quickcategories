--- Add a command_page_resolve_redirects column to the command table
--- and rename command_page to command_page_title.

ALTER TABLE command
CHANGE command_page command_page_title text NOT NULL,
ADD COLUMN command_page_resolve_redirects bool DEFAULT NULL AFTER command_page_title;

UPDATE command
SET command_page_resolve_redirects = NULL;

ALTER TABLE command
MODIFY command_page_resolve_redirects bool;

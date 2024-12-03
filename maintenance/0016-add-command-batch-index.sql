--- Add another index on the command table
--- which can be used when sorting commands of a batch by command_id
--- without a filesort (or a full table scan).
CREATE INDEX command_batch ON command (command_batch);

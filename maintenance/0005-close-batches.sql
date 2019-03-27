--- After the introduction of a closed status for batches,
--- convert all batches with no open commands to this status.

UPDATE batch
SET batch_status = 128 -- DatabaseStore._BATCH_STATUS_CLOSED
WHERE batch_id NOT IN (
  SELECT DISTINCT command_batch
  FROM command
  WHERE command_status IN (
    0, -- DatabaseStore._COMMAND_STATUS_PLAN
    16 -- DatabaseStore._COMMAND_STATUS_PENDING
  )
);

--- Replace the command_batch index on just the command_batch column of the command table
--- with a command_batch_status index on the command_batch and command_status columns.

CREATE INDEX command_batch_status ON command (command_batch, command_status);

DROP INDEX command_batch ON command;

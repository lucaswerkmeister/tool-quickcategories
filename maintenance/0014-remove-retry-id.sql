--- Remove the retry_id column from the retry table
--- and instead use the retry_failure as the primary key.

ALTER TABLE retry
DROP retry_id,
ADD PRIMARY KEY(retry_failure);

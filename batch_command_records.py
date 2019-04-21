from typing import List

from command import CommandRecord, CommandPending, CommandFinish


class BatchCommandRecords:
    """Accessor for the CommandRecords of a StoredBatch."""

    def get_slice(self, offset: int, limit: int) -> List[CommandRecord]: ...

    def make_plans_pending(self, offset: int, limit: int) -> List[CommandPending]: ...

    def store_finish(self, command_finish: CommandFinish) -> None: ...

    def __len__(self) -> int: ...

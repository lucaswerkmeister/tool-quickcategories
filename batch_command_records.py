from typing import Dict, Iterator, List, Type

from command import Command, CommandRecord, CommandPending, CommandFinish
from page import Page


class BatchCommandRecords:
    """Accessor for the CommandRecords of a StoredBatch."""

    def get_slice(self, offset: int, limit: int) -> List[CommandRecord]:
        ...

    def get_summary(self) -> Dict[Type[CommandRecord], int]:
        ...

    def stream_pages(self) -> Iterator[Page]:
        ...

    def stream_commands(self) -> Iterator[Command]:
        ...

    def make_plans_pending(self, offset: int, limit: int) -> List[CommandPending]:
        ...

    def make_pendings_planned(self, command_record_ids: List[int]) -> None:
        ...

    def store_finish(self, command_finish: CommandFinish) -> None:
        ...

    def __len__(self) -> int:
        ...

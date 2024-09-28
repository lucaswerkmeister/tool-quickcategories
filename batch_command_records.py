from abc import ABC, abstractmethod
from collections.abc import Iterator

from command import Command, CommandRecord, CommandPending, CommandFinish
from page import Page


class BatchCommandRecords(ABC):
    """Accessor for the CommandRecords of a StoredBatch."""

    @abstractmethod
    def get_slice(self, offset: int, limit: int) -> list[CommandRecord]:
        """Get up to limit command records from the given offset."""

    @abstractmethod
    def get_summary(self) -> dict[type[CommandRecord], int]:
        """Get the number of command records for each concrete type."""

    @abstractmethod
    def stream_pages(self) -> Iterator[Page]:
        """Get a stream of all the pages touched by a batch."""

    @abstractmethod
    def stream_commands(self) -> Iterator[Command]:
        """Get a stream of all the commands in a batch."""

    @abstractmethod
    def make_plans_pending(self, offset: int, limit: int) -> list[CommandPending]:
        """Mark up to limit command records from the given offset as pending and return them."""

    @abstractmethod
    def make_pendings_planned(self, command_record_ids: list[int]) -> None:
        """Mark the pending command records with the given IDs as planned."""

    @abstractmethod
    def store_finish(self, command_finish: CommandFinish) -> None:
        """Save the given finished command."""

    @abstractmethod
    def __len__(self) -> int:
        """Get the number of command records in the batch."""

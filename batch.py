from abc import ABC, abstractmethod
from dataclasses import dataclass
import datetime
from typing import List, Optional

from batch_background_runs import BatchBackgroundRuns
from batch_command_records import BatchCommandRecords
from command import Command
from localuser import LocalUser


@dataclass
class NewBatch:
    """A list of commands to be performed."""

    commands: List[Command]
    title: Optional[str]

    def cleanup(self) -> None:
        """Partially normalize the batch, as a convenience for users.

        This should not be used as a replacement for full
        normalization via the MediaWiki API.
        """
        for command in self.commands:
            command.cleanup()
        if self.title is not None:
            self.title = self.title.strip()

    def __str__(self) -> str:
        command_strs = '\n'.join([str(command) for command in self.commands])
        if self.title:
            return '# ' + self.title + '\n' + command_strs
        else:
            return command_strs


@dataclass  # type: ignore
class StoredBatch(ABC):
    """A list of commands to be performed for one user that has been registered."""

    id: int
    local_user: LocalUser
    domain: str
    title: Optional[str]
    created: datetime.datetime
    last_updated: datetime.datetime
    command_records: BatchCommandRecords
    background_runs: BatchBackgroundRuns

    @abstractmethod
    def __str__(self) -> str:
        pass


class OpenBatch(StoredBatch):
    """A list of commands to be performed for one user that has been registered but not completed yet."""

    def __str__(self) -> str:
        return 'batch #%d on %s by %s' % (self.id, self.domain, self.local_user.user_name)


class ClosedBatch(StoredBatch):
    """A list of commands that were performed for one user."""

    def __str__(self) -> str:
        return 'batch #%d on %s by %s' % (self.id, self.domain, self.local_user.user_name)

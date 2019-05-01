import datetime
from typing import Any, List, Optional

from batch_background_runs import BatchBackgroundRuns
from batch_command_records import BatchCommandRecords
from command import Command
from localuser import LocalUser


class NewBatch:
    """A list of commands to be performed."""

    def __init__(self, commands: List[Command], title: Optional[str]):
        self.commands = commands
        self.title = title

    def cleanup(self) -> None:
        """Partially normalize the batch, as a convenience for users.

        This should not be used as a replacement for full
        normalization via the MediaWiki API.
        """
        for command in self.commands:
            command.cleanup()
        if self.title is not None:
            self.title = self.title.strip()

    def __eq__(self, value: Any) -> bool:
        return type(value) is NewBatch and \
            self.commands == value.commands and \
            self.title == value.title

    def __str__(self) -> str:
        command_strs = '\n'.join([str(command) for command in self.commands])
        if self.title:
            return '# ' + self.title + '\n' + command_strs
        else:
            return command_strs

    def __repr__(self) -> str:
        return 'NewBatch(' + \
            repr(self.commands) + ', ' + \
            repr(self.title) + ')'


class StoredBatch:
    """A list of commands to be performed for one user that has been registered."""

    def __init__(self,
                 id: int,
                 local_user: LocalUser,
                 domain: str,
                 title: Optional[str],
                 created: datetime.datetime,
                 last_updated: datetime.datetime,
                 command_records: BatchCommandRecords,
                 background_runs: BatchBackgroundRuns):
        self.id = id
        self.local_user = local_user
        self.domain = domain
        self.title = title
        self.created = created
        self.last_updated = last_updated
        self.command_records = command_records
        self.background_runs = background_runs


class OpenBatch(StoredBatch):
    """A list of commands to be performed for one user that has been registered but not completed yet."""

    def __eq__(self, value: Any) -> bool:
        return type(value) is OpenBatch and \
            self.id == value.id and \
            self.local_user == value.local_user and \
            self.domain == value.domain and \
            self.title == value.title and \
            self.created == value.created and \
            self.last_updated == value.last_updated and \
            self.command_records == value.command_records and \
            self.background_runs == value.background_runs

    def __str__(self) -> str:
        return 'batch #%d on %s by %s' % (self.id, self.domain, self.local_user.user_name)

    def __repr__(self) -> str:
        return 'OpenBatch(' + \
            repr(self.id) + ', ' + \
            repr(self.local_user) + ', ' + \
            repr(self.domain) + ', ' + \
            repr(self.title) + ', ' + \
            repr(self.created) + ', ' + \
            repr(self.last_updated) + ', ' + \
            repr(self.command_records) + ', ' + \
            repr(self.background_runs) + ')'


class ClosedBatch(StoredBatch):
    """A list of commands that were performed for one user."""

    def __eq__(self, value: Any) -> bool:
        return type(value) is ClosedBatch and \
            self.id == value.id and \
            self.local_user == value.local_user and \
            self.domain == value.domain and \
            self.title == value.title and \
            self.created == value.created and \
            self.last_updated == value.last_updated and \
            self.command_records == value.command_records and \
            self.background_runs == value.background_runs

    def __str__(self) -> str:
        return 'batch #%d on %s by %s' % (self.id, self.domain, self.local_user.user_name)

    def __repr__(self) -> str:
        return 'ClosedBatch(' + \
            repr(self.id) + ', ' + \
            repr(self.local_user) + ', ' + \
            repr(self.domain) + ', ' + \
            repr(self.title) + ', ' + \
            repr(self.created) + ', ' + \
            repr(self.last_updated) + ', ' + \
            repr(self.command_records) + ', ' + \
            repr(self.background_runs) + ')'

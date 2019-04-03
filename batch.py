import datetime
from typing import Any, List

from command import Command, CommandRecord, CommandPlan, CommandPending, CommandFinish


class NewBatch:
    """A list of commands to be performed."""

    def __init__(self, commands: List[Command]):
        self.commands = commands

    def cleanup(self) -> None:
        """Partially normalize the batch, as a convenience for users.

        This should not be used as a replacement for full
        normalization via the MediaWiki API.
        """
        for command in self.commands:
            command.cleanup()

    def __eq__(self, value: Any) -> bool:
        return type(value) is NewBatch and \
            self.commands == value.commands

    def __str__(self) -> str:
        return '\n'.join([str(command) for command in self.commands])

    def __repr__(self) -> str:
        return 'NewBatch(' + repr(self.commands) + ')'


class StoredBatch:
    """A list of commands to be performed for one user that has been registered."""

    def __init__(self,
                 id: int,
                 user_name: str,
                 local_user_id: int,
                 global_user_id: int,
                 domain: str,
                 created: datetime.datetime,
                 last_updated: datetime.datetime,
                 command_records: 'BatchCommandRecords'):
        self.id = id
        self.user_name = user_name
        self.local_user_id = local_user_id
        self.global_user_id = global_user_id
        self.domain = domain
        self.created = created
        self.last_updated = last_updated
        self.command_records = command_records


class OpenBatch(StoredBatch):
    """A list of commands to be performed for one user that has been registered but not completed yet."""

    def __eq__(self, value: Any) -> bool:
        return type(value) is OpenBatch and \
            self.id == value.id and \
            self.user_name == value.user_name and \
            self.local_user_id == value.local_user_id and \
            self.global_user_id == value.global_user_id and \
            self.domain == value.domain and \
            self.created == value.created and \
            self.last_updated == value.last_updated and \
            self.command_records == value.command_records

    def __str__(self) -> str:
        return 'batch #%d on %s by %s' % (self.id, self.domain, self.user_name)

    def __repr__(self) -> str:
        return 'OpenBatch(' + \
            repr(self.id) + ', ' + \
            repr(self.user_name) + ', ' + \
            repr(self.local_user_id) + ', ' + \
            repr(self.global_user_id) + ', ' + \
            repr(self.domain) + ', ' + \
            repr(self.created) + ', ' + \
            repr(self.last_updated) + ', ' + \
            repr(self.command_records) + ')'


class ClosedBatch(StoredBatch):
    """A list of commands that were performed for one user."""

    def __eq__(self, value: Any) -> bool:
        return type(value) is ClosedBatch and \
            self.id == value.id and \
            self.user_name == value.user_name and \
            self.local_user_id == value.local_user_id and \
            self.global_user_id == value.global_user_id and \
            self.domain == value.domain and \
            self.created == value.created and \
            self.last_updated == value.last_updated and \
            self.command_records == value.command_records

    def __str__(self) -> str:
        return 'batch #%d on %s by %s' % (self.id, self.domain, self.user_name)

    def __repr__(self) -> str:
        return 'ClosedBatch(' + \
            repr(self.id) + ', ' + \
            repr(self.user_name) + ', ' + \
            repr(self.local_user_id) + ', ' + \
            repr(self.global_user_id) + ', ' + \
            repr(self.domain) + ', ' + \
            repr(self.created) + ', ' + \
            repr(self.last_updated) + ', ' + \
            repr(self.command_records) + ')'


class BatchCommandRecords:
    """Accessor for the CommandRecords of a StoredBatch."""

    def get_slice(self, offset: int, limit: int) -> List[CommandRecord]: ...

    def make_plans_pending(self, offset: int, limit: int) -> List[CommandPending]: ...

    def store_finish(self, command_finish: CommandFinish) -> None: ...

    def __len__(self) -> int: ...


class BatchCommandRecordsList(BatchCommandRecords):
    """List-based implementation of BatchCommandRecords."""

    def __init__(self, command_records: List[CommandRecord]):
        self.command_records = command_records

    def get_slice(self, offset: int, limit: int) -> List[CommandRecord]:
        return self.command_records[offset:offset+limit]

    def make_plans_pending(self, offset: int, limit: int) -> List[CommandPending]:
        command_pendings = []
        for index, command_plan in enumerate(self.command_records[offset:offset+limit]):
            if not isinstance(command_plan, CommandPlan):
                continue
            command_pending = CommandPending(command_plan.id, command_plan.command)
            self.command_records[index] = command_pending
            command_pendings.append(command_pending)
        return command_pendings

    def store_finish(self, command_finish: CommandFinish) -> None:
        for index, command_record in enumerate(self.command_records):
            if command_record.id == command_finish.id:
                self.command_records[index] = command_finish
                break
        else:
            raise KeyError('command not found')

    def __len__(self) -> int:
        return len(self.command_records)

    def __eq__(self, value: Any) -> bool:
        return type(value) is BatchCommandRecordsList and \
            self.command_records == value.command_records

    def __repr__(self) -> str:
        return 'BatchCommandRecordsList(' + repr(self.command_records) + ')'

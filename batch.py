from typing import Any, List

from command import Command, CommandRecord, CommandPlan, CommandFinish


class NewBatch:
    """A list of commands to be performed."""

    def __init__(self, commands: List[Command]):
        self.commands = commands

    def __eq__(self, value: Any) -> bool:
        return type(value) is NewBatch and \
            self.commands == value.commands

    def __str__(self) -> str:
        return '\n'.join([str(command) for command in self.commands])

    def __repr__(self) -> str:
        return 'NewBatch(' + repr(self.commands) + ')'


class OpenBatch:
    """A list of commands to be performed that has been registered but not completed yet."""

    def __init__(self,
                 id: int,
                 command_records: List[CommandRecord]):
        assert command_records
        assert any(map(lambda command_record: isinstance(command_record, CommandPlan), command_records))
        self.id = id
        self.command_records = command_records

    def __eq__(self, value: Any) -> bool:
        return type(value) is OpenBatch and \
            self.id == value.id and \
            self.command_records == value.command_records

    def __str__(self) -> str:
        return '\n'.join([str(command_record) for command_record in self.command_records])

    def __repr__(self) -> str:
        return 'OpenBatch(' + \
            repr(self.id) + ', ' + \
            repr(self.command_records) + ')'

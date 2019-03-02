from typing import Any, List, Mapping

from command import Command, CommandPlan, CommandFinish


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
                 command_plans: Mapping[int, CommandPlan],
                 command_finishes: Mapping[int, CommandFinish]):
        assert command_plans
        self.id = id
        self.command_plans = command_plans
        self.command_finishes = command_finishes

    def __eq__(self, value: Any) -> bool:
        return type(value) is OpenBatch and \
            self.id == value.id and \
            self.command_plans == value.command_plans and \
            self.command_finishes == value.command_finishes

    def __str__(self) -> str:
        return '\n'.join([str(command) for command in self.command_plans.values()] +
                         ['# ' + str(command) for command in self.command_finishes.values()])

    def __repr__(self) -> str:
        return 'OpenBatch(' + \
            repr(self.id) + ', ' + \
            repr(self.command_plans) + ', ' + \
            repr(self.command_finishes) + ')'

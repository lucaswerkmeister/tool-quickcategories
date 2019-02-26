from typing import Any, List

from command import Command
import siteinfo


class Batch:
    """A list of commands to be performed for one user."""

    def __init__(self, authentication: dict, commands: List[Command]):
        self.authentication = authentication
        self.commands = commands

    def __eq__(self, value: Any) -> bool:
        return type(value) is Batch and \
            self.authentication == value.authentication and \
            self.commands == value.commands

    def __str__(self) -> str:
        return '\n'.join([str(command) for command in self.commands])

    def __repr__(self) -> str:
        return 'Batch(' + repr(self.authentication) + ', ' + repr(self.commands) + ')'

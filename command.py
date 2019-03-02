from typing import Any, List, Tuple

from action import Action

class Command:
    """A list of actions to perform on a page."""

    def __init__(self, page: str, actions: List['Action']):
        self.page = page
        self.actions = actions

    def apply(self, wikitext: str, category_info: Tuple[str, List[str]]) -> Tuple[str, List[Tuple[Action, bool]]]:
        """Apply the actions of this command to the given wikitext and return
        the result as well as the actions together with the
        information whether they were a no-op or not.
        """
        actions = []

        for action in self.actions:
            new_wikitext = action.apply(wikitext, category_info)
            actions.append((action, wikitext == new_wikitext))
            wikitext = new_wikitext

        return wikitext, actions

    def __eq__(self, value: Any) -> bool:
        return type(value) is Command and \
            self.page == value.page and \
            self.actions == value.actions

    def __str__(self) -> str:
        return self.page + '|' + '|'.join([str(action) for action in self.actions])

    def __repr__(self) -> str:
        return 'Command(' + repr(self.page) + ', ' + repr(self.actions) + ')'


class CommandPlan:
    """A command that should be run in the future."""

    def __init__(self, id: int, command: Command):
        self.id = id
        self.command = command

    def __eq__(self, value: Any) -> bool:
        return type(value) is CommandPlan and \
            self.id == value.id and \
            self.command == value.command

    def __str__(self) -> str:
        return str(self.command)

    def __repr__(self) -> str:
        return 'CommandPlan(' + repr(self.id) + ', ' + repr(self.command) + ')'


class CommandFinish:
    """A command that was intended to be run at some point
    and should now no longer be run."""

    def __init__(self, id: int, command: Command):
        self.id = id
        self.command = command


class CommandSuccess(CommandFinish):
    """A command that was successfully run."""


class CommandEdit(CommandSuccess):
    """A command that resulted in an edit on a page."""

    def __init__(self, id: int, command: Command, base_revision: int, revision: int):
        assert base_revision < revision
        super().__init__(id, command)
        self.base_revision = base_revision
        self.revision = revision


    def __eq__(self, value: Any) -> bool:
        return type(value) is CommandEdit and \
            self.id == value.id and \
            self.command == value.command and \
            self.base_revision == value.base_revision and \
            self.revision == value.revision

    def __str__(self) -> str:
        return str(self.command)

    def __repr__(self) -> str:
        return 'CommandEdit(' + \
            repr(self.id) + ', ' + \
            repr(self.command) + ', ' + \
            repr(self.base_revision) + ', ' + \
            repr(self.revision) + ')'


class CommandNoop(CommandSuccess):
    """A command that resulted in no change to a page."""

    def __init__(self, id: int, command: Command, revision: int):
        super().__init__(id, command)
        self.revision = revision

    def __eq__(self, value: Any) -> bool:
        return type(value) is CommandNoop and \
            self.id == value.id and \
            self.command == value.command and \
            self.revision == value.revision

    def __str__(self) -> str:
        return str(self.command)

    def __repr__(self) -> str:
        return 'CommandNoop(' + \
            repr(self.id) + ', ' + \
            repr(self.command) + ', ' + \
            repr(self.revision) + ')'

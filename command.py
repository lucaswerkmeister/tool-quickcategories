import datetime
from typing import Any, List, Optional, Tuple

from action import Action
from siteinfo import CategoryInfo


class Command:
    """A list of actions to perform on a page."""

    def __init__(self, page: str, actions: List['Action']):
        self.page = page
        self.actions = actions

    def apply(self, wikitext: str, category_info: CategoryInfo) -> Tuple[str, List[Tuple[Action, bool]]]:
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

    def cleanup(self) -> None:
        """Partially normalize the command, as a convenience for users.

        This should not be used as a replacement for full
        normalization via the MediaWiki API.
        """
        self.page = self.page.replace('_', ' ')
        for action in self.actions:
            action.cleanup()

    def __eq__(self, value: Any) -> bool:
        return type(value) is Command and \
            self.page == value.page and \
            self.actions == value.actions

    def __str__(self) -> str:
        return self.page + '|' + '|'.join([str(action) for action in self.actions])

    def __repr__(self) -> str:
        return 'Command(' + repr(self.page) + ', ' + repr(self.actions) + ')'


class CommandRecord:
    """A command that was recorded in some store."""

    def __init__(self, id: int, command: Command):
        self.id = id
        self.command = command


class CommandPlan(CommandRecord):
    """A command that should be run in the future."""

    def __eq__(self, value: Any) -> bool:
        return type(value) is CommandPlan and \
            self.id == value.id and \
            self.command == value.command

    def __str__(self) -> str:
        return str(self.command)

    def __repr__(self) -> str:
        return 'CommandPlan(' + repr(self.id) + ', ' + repr(self.command) + ')'


class CommandFinish(CommandRecord):
    """A command that was intended to be run at some point
    and should now no longer be run."""

    def __str__(self) -> str:
        return '# ' + str(self.command)


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

    def __repr__(self) -> str:
        return 'CommandNoop(' + \
            repr(self.id) + ', ' + \
            repr(self.command) + ', ' + \
            repr(self.revision) + ')'


class CommandFailure(CommandFinish):
    """A command that was not successfully run."""

    def can_retry_immediately(self) -> bool:
        """Whether it is okay to retry running this command immediately.

        In case of an immediate retry, no permanent record of the failure is kept,
        so this should not be used if the failure resulted in any actions on the wiki."""
        ...

    def can_continue_batch(self) -> bool:
        """Whether it is okay to continue with other commands in this batch.

        If the failure only affects this command, we can proceed with the batch as usual;
        if other commands are likely to fail for the same reason,
        or we should back off for some other reason,
        the batch should be suspended for a time."""
        ...


class CommandPageMissing(CommandFailure):
    """A command that failed because the specified page was found to be missing at the time."""

    def __init__(self, id: int, command: Command, curtimestamp: str):
        super().__init__(id, command)
        self.curtimestamp = curtimestamp

    def can_retry_immediately(self) -> bool:
        return False

    def can_continue_batch(self) -> bool:
        return True

    def __eq__(self, value: Any) -> bool:
        return type(value) is CommandPageMissing and \
            self.id == value.id and \
            self.command == value.command and \
            self.curtimestamp == value.curtimestamp

    def __repr__(self) -> str:
        return 'CommandPageMissing(' + \
            repr(self.id) + ', ' + \
            repr(self.command) + ', ' + \
            repr(self.curtimestamp) + ')'


class CommandEditConflict(CommandFailure):
    """A command that failed due to an edit conflict."""

    def can_retry_immediately(self) -> bool:
        return True

    def can_continue_batch(self) -> bool:
        return True

    def __eq__(self, value: Any) -> bool:
        return type(value) is CommandEditConflict and \
            self.id == value.id and \
            self.command == value.command

    def __repr__(self) -> str:
        return 'CommandEditConflict(' + \
            repr(self.id) + ', ' + \
            repr(self.command) + ')'


class CommandMaxlagExceeded(CommandFailure):
    """A command that failed replication lag in the database cluster was too high."""

    def __init__(self, id: int, command: Command, retry_after: datetime.datetime):
        super().__init__(id, command)
        self.retry_after = retry_after

    def can_retry_immediately(self) -> bool:
        return False

    def can_continue_batch(self) -> bool:
        return False

    def __eq__(self, value: Any) -> bool:
        return type(value) is CommandMaxlagExceeded and \
            self.id == value.id and \
            self.command == value.command and \
            self.retry_after == value.retry_after

    def __repr__(self) -> str:
        return 'CommandMaxlagExceeded(' + \
            repr(self.id) + ', ' + \
            repr(self.command) + ', ' + \
            repr(self.retry_after) + ')'


class CommandBlocked(CommandFailure):
    """A command that failed because the user or IP address was blocked."""

    def __init__(self, id: int, command: Command, auto: bool, blockinfo: Optional[dict]):
        super().__init__(id, command)
        self.auto = auto
        self.blockinfo = blockinfo

    def can_retry_immediately(self) -> bool:
        return False

    def can_continue_batch(self) -> bool:
        # we could perhaps continue the batch if the block is partial
        # (that is, if self.blockinfo['blockpartial'] is True),
        # but for now I’d rather not
        return False

    def __eq__(self, value: Any) -> bool:
        return type(value) is CommandBlocked and \
            self.id == value.id and \
            self.command == value.command and \
            self.auto == value.auto and \
            self.blockinfo == value.blockinfo

    def __repr__(self) -> str:
        return 'CommandBlocked(' + \
            repr(self.id) + ', ' + \
            repr(self.command) + ', ' + \
            'auto=' + repr(self.auto) + ', ' + \
            'blockinfo=' + repr(self.blockinfo) + ')'

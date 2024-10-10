from abc import ABC, abstractmethod
from dataclasses import dataclass
import datetime
from typing import Optional

from action import Action
from page import Page
from siteinfo import CategoryInfo


@dataclass(frozen=True)
class Command:
    """A list of actions to perform on a page."""

    page: Page
    actions: list['Action']

    def apply(self, wikitext: str, category_info: CategoryInfo) -> tuple[str, list[tuple[Action, bool]]]:
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
        self.page.cleanup()
        for action in self.actions:
            action.cleanup()

    def actions_tpsv(self) -> str:
        return '|'.join([str(action) for action in self.actions])

    def __str__(self) -> str:
        return str(self.page) + '|' + self.actions_tpsv()


@dataclass(frozen=True)
class CommandRecord(ABC):
    """A command that was recorded in some store."""

    id: int
    command: Command


class CommandPlan(CommandRecord):
    """A command that should be run in the future."""

    def __str__(self) -> str:
        return str(self.command)


class CommandPending(CommandRecord):
    """A command that is about to be run or currently running."""

    def __str__(self) -> str:
        return str(self.command)


class CommandFinish(CommandRecord):
    """A command that was intended to be run at some point
    and should now no longer be run."""

    def __str__(self) -> str:
        return '# ' + str(self.command)


class CommandSuccess(CommandFinish):
    """A command that was successfully run."""


@dataclass(frozen=True)
class CommandEdit(CommandSuccess):
    """A command that resulted in an edit on a page."""

    base_revision: int
    revision: int

    def __post_init__(self) -> None:
        assert self.base_revision < self.revision


@dataclass(frozen=True)
class CommandNoop(CommandSuccess):
    """A command that resulted in no change to a page."""

    revision: int


class CommandFailure(CommandFinish):
    """A command that was not successfully run."""

    @abstractmethod
    def can_retry_immediately(self) -> bool:
        """Whether it is okay to retry running this command immediately.

        In case of an immediate retry, no permanent record of the failure is kept,
        so this should not be used if the failure resulted in any actions on the wiki."""

    @abstractmethod
    def can_retry_later(self) -> bool:
        """Whether it is okay to retry running this command at a later time.

        If True, a new command plan for the same command with a fresh ID
        will be appended to the end of the batch."""

    @abstractmethod
    def can_continue_batch(self) -> bool | datetime.datetime:
        """Whether it is okay to continue with other commands in this batch.

        If the failure only affects this command, we can proceed with the batch as usual;
        if other commands are likely to fail for the same reason,
        or we should back off for some other reason,
        the batch should be suspended for a time.

        True means that we can continue immediately;
        False means that we should suspend the batch for an unspecified time
        (i. e., stop background runs and only proceed on manual input by the user);
        a datetime means that we should suspend the batch until that time
        (i. e., suspend background runs but resume them automatically)."""


@dataclass(frozen=True)
class CommandPageMissing(CommandFailure):
    """A command that failed because the specified page was found to be missing at the time."""

    curtimestamp: str

    def can_retry_immediately(self) -> bool:
        return False

    def can_retry_later(self) -> bool:
        return False

    def can_continue_batch(self) -> bool:
        return True


@dataclass(frozen=True)
class CommandTitleInvalid(CommandFailure):
    """A command that failed because the specified title was invalid.

    This also includes empty titles (which in the API output are absent,
    rather than reported as invalid)."""

    curtimestamp: str

    def can_retry_immediately(self) -> bool:
        return False

    def can_retry_later(self) -> bool:
        return False

    def can_continue_batch(self) -> bool:
        return True


@dataclass(frozen=True)
class CommandTitleInterwiki(CommandFailure):
    """A command that failed because the specified title was an interwiki link."""

    curtimestamp: str

    def can_retry_immediately(self) -> bool:
        return False

    def can_retry_later(self) -> bool:
        return False

    def can_continue_batch(self) -> bool:
        return True


@dataclass(frozen=True)
class CommandPageProtected(CommandFailure):
    """A command that failed because the specified page was protected at the time."""

    curtimestamp: str

    def can_retry_immediately(self) -> bool:
        return False

    def can_retry_later(self) -> bool:
        return False

    def can_continue_batch(self) -> bool:
        return True


@dataclass(frozen=True)
class CommandPageBadContentFormat(CommandFailure):
    """A command that failed because the page has a bad content format.

    The content format is the lower level beneath a content model.
    Multiple content models can share the same content format.
    QuickCategories only supports the text/x-wiki content format,
    and this is unlikely to ever change."""

    content_format: str
    content_model: str
    revision: int

    def can_retry_immediately(self) -> bool:
        return False

    def can_retry_later(self) -> bool:
        return False

    def can_continue_batch(self) -> bool:
        return True


@dataclass(frozen=True)
class CommandPageBadContentModel(CommandFailure):
    """A command that failed because the page has a bad content model.

    The content format is the lower level beneath a content model.
    Multiple content models can share the same content format.
    QuickCategories supports a small number of known content models
    as long as they use the text/x-wiki content format;
    an error of this kind can potentially be made supported later."""

    content_format: str
    content_model: str
    revision: int

    def can_retry_immediately(self) -> bool:
        return False

    def can_retry_later(self) -> bool:
        return False

    def can_continue_batch(self) -> bool:
        return True


class CommandEditConflict(CommandFailure):
    """A command that failed due to an edit conflict."""

    def can_retry_immediately(self) -> bool:
        return True

    def can_retry_later(self) -> bool:
        return True

    def can_continue_batch(self) -> bool:
        return True


@dataclass(frozen=True)
class CommandMaxlagExceeded(CommandFailure):
    """A command that failed because replication lag in the database cluster was too high."""

    retry_after: datetime.datetime

    def can_retry_immediately(self) -> bool:
        return False

    def can_retry_later(self) -> bool:
        return True

    def can_continue_batch(self) -> datetime.datetime:
        return self.retry_after


@dataclass(frozen=True)
class CommandBlocked(CommandFailure):
    """A command that failed because the user or IP address was blocked."""

    auto: bool
    blockinfo: Optional[dict]

    def can_retry_immediately(self) -> bool:
        return False

    def can_retry_later(self) -> bool:
        return True

    def can_continue_batch(self) -> bool:
        # we could perhaps continue the batch if the block is partial
        # (that is, if self.blockinfo['blockpartial'] is True),
        # but for now I’d rather not
        return False


@dataclass(frozen=True)
class CommandWikiReadOnly(CommandFailure):
    """A command that failed because the wiki was in read-only mode."""

    reason: Optional[str]
    retry_after: Optional[datetime.datetime]

    def can_retry_immediately(self) -> bool:
        return False

    def can_retry_later(self) -> bool:
        return True

    def can_continue_batch(self) -> bool | datetime.datetime:
        return self.retry_after or False

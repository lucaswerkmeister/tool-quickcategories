from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
import datetime
from typing import Optional

from localuser import LocalUser


@dataclass(frozen=True)
class BatchBackgroundStart:
    """The time and user starting the background run."""

    time: datetime.datetime
    user: LocalUser


@dataclass(frozen=True)
class BatchBackgroundStop:
    """The time and user stopping the background run.

    If user is None, the run was stopped by the system,
    usually because the batch finished."""

    time: datetime.datetime
    user: Optional[LocalUser]


@dataclass(frozen=True)
class BatchBackgroundRun:
    """A background run.

    If stop is None, the batch is currently running."""

    start: BatchBackgroundStart
    stop: Optional[BatchBackgroundStop]


class BatchBackgroundRuns(ABC):
    """Accessor for the background runs of a StoredBatch."""

    def currently_running(self) -> bool:
        last = self.get_last()
        return last is not None and last.stop is None

    @abstractmethod
    def get_last(self) -> Optional[BatchBackgroundRun]:
        """Get the last background run, if any."""

    @abstractmethod
    def get_all(self) -> Sequence[BatchBackgroundRun]:
        """Get all the background runs."""

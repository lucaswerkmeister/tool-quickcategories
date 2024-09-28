from abc import ABC, abstractmethod
from collections.abc import Sequence
import datetime
from typing import Optional

from localuser import LocalUser


class BatchBackgroundRuns(ABC):
    """Accessor for the background runs of a StoredBatch."""

    def currently_running(self) -> bool:
        last = self.get_last()
        return last is not None and last[1] is None

    @abstractmethod
    def get_last(self) -> Optional[tuple[tuple[datetime.datetime, LocalUser], Optional[tuple[datetime.datetime, Optional[LocalUser]]]]]:
        """Get the last background run, if any.

           A background run is a tuple of the time and user starting the background run,
           and (if it’s finished) the time and (if it didn’t stop on its own) user stopping it."""

    @abstractmethod
    def get_all(self) -> Sequence[tuple[tuple[datetime.datetime, LocalUser], Optional[tuple[datetime.datetime, Optional[LocalUser]]]]]:
        """Get all the background runs."""

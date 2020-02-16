import datetime
from typing import Optional, Sequence, Tuple

from localuser import LocalUser


class BatchBackgroundRuns:
    """Accessor for the background runs of a StoredBatch."""

    def currently_running(self) -> bool:
        last = self.get_last()
        return last is not None and last[1] is None

    def get_last(self) -> Optional[Tuple[Tuple[datetime.datetime, LocalUser], Optional[Tuple[datetime.datetime, Optional[LocalUser]]]]]:
        ...

    def get_all(self) -> Sequence[Tuple[Tuple[datetime.datetime, LocalUser], Optional[Tuple[datetime.datetime, Optional[LocalUser]]]]]:
        ...

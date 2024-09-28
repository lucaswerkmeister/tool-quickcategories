from abc import ABC, abstractmethod
from collections.abc import Sequence
import datetime
import mwapi  # type: ignore
import mwoauth  # type: ignore
from typing import Optional

from batch import NewBatch, StoredBatch, OpenBatch
from command import CommandPending
from localuser import LocalUser


class BatchStore(ABC):

    @abstractmethod
    def store_batch(self, new_batch: NewBatch, session: mwapi.Session) -> OpenBatch:
        """Store the given batch and return it as a batch with ID."""

    @abstractmethod
    def get_batch(self, id: int) -> Optional[StoredBatch]:
        """Get the batch with the given ID."""

    @abstractmethod
    def get_batches_slice(self, offset: int, limit: int) -> Sequence[StoredBatch]:
        """Get up to limit batches from the given offset."""

    @abstractmethod
    def get_batches_count(self) -> int:
        """Get the total number of stored batches."""

    @abstractmethod
    def start_background(self, batch: OpenBatch, session: mwapi.Session) -> None:
        """Mark the given batch to be run in the background using the session’s credentials."""

    @abstractmethod
    def stop_background(self, batch: StoredBatch, session: Optional[mwapi.Session] = None) -> None:
        """Mark the given batch to no longer be run in the background."""

    @abstractmethod
    def suspend_background(self, batch: StoredBatch, until: datetime.datetime) -> None:
        """Mark the given batch to stop background runs until the given datetime."""

    @abstractmethod
    def make_plan_pending_background(self, consumer_token: mwoauth.ConsumerToken, user_agent: str) -> Optional[tuple[OpenBatch, CommandPending, mwapi.Session]]:
        """Pick one planned command from a batch that’s marked to be run in the background,
           mark that command as pending and return it with credentials."""


def _local_user_from_session(session: mwapi.Session) -> LocalUser:
    domain = session.host[len('https://'):]
    response = session.get(**{'action': 'query',
                              'meta': 'userinfo',
                              'uiprop': 'centralids',
                              'assert': 'user'})  # assert is a keyword, can’t use kwargs syntax :(
    user_name = response['query']['userinfo']['name']
    local_user_id = response['query']['userinfo']['id']
    global_user_id = response['query']['userinfo']['centralids']['CentralAuth']
    assert user_name
    assert local_user_id > 0
    assert global_user_id > 0
    return LocalUser(user_name, domain, local_user_id, global_user_id)

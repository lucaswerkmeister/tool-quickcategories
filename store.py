from abc import ABC, abstractmethod
import cachetools
from collections.abc import Sequence
import datetime
from enum import Enum, unique
import mwapi  # type: ignore
import mwoauth  # type: ignore
import requests_oauthlib  # type: ignore
import threading
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


@unique
class WatchlistParam(Enum):
    """The watchlist parameter to the action=edit API.

    The name is the parameter as sent to the API
    (and hence lowercase, unlike Python’s strong recommendation for UPPER_CASE enum members),
    the value is internal (used by the database store).
    """
    preferences = 0
    nochange = 1
    watch = 2
    unwatch = 3  # only used in tests


class PreferenceStore(ABC):
    """A persistent store for user preferences.

    Unlike flask.session, this is also available in the background runner.

    For convenience, the session is optional in the getters
    (which return None in that case),
    so they can be called directly with authenticated_session().
    """

    # once we have more than one preference in this store,
    # we might want multi-get+set methods

    @abstractmethod
    def get_watchlist_param(self, session: Optional[mwapi.Session]) -> Optional[WatchlistParam]:
        """Get the watchlist parameter preference for the given session, if set."""

    @abstractmethod
    def set_watchlist_param(self, session: mwapi.Session, value: WatchlistParam) -> None:
        """Set the watchlist parameter preference for the given session."""


_local_user_cache: cachetools.LRUCache[tuple[str, str], LocalUser] = cachetools.LRUCache(maxsize=1024)
_local_user_cache_lock = threading.RLock()
def _local_user_cache_key(session: mwapi.Session) -> tuple[str, str]:
    assert isinstance(session.session.auth, requests_oauthlib.OAuth1)
    return session.host, session.session.auth.client.resource_owner_key

@cachetools.cached(cache=_local_user_cache,
                   key=_local_user_cache_key,
                   lock=_local_user_cache_lock)
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

import datetime
import mwapi # type: ignore
import mwoauth # type: ignore
from typing import Optional, Sequence, Tuple

from batch import NewBatch, StoredBatch, OpenBatch
from command import CommandPending
from localuser import LocalUser


class BatchStore:

    def store_batch(self, new_batch: NewBatch, session: mwapi.Session) -> OpenBatch: ...

    def get_batch(self, id: int) -> Optional[StoredBatch]: ...

    def get_batches_slice(self, offset: int, limit: int) -> Sequence[StoredBatch]: ...

    def get_batches_count(self) -> int: ...

    def start_background(self, batch: OpenBatch, session: mwapi.Session) -> None: ...

    def stop_background(self, batch: StoredBatch, session: Optional[mwapi.Session] = None) -> None: ...

    def suspend_background(self, batch: StoredBatch, until: datetime.datetime) -> None: ...

    def make_plan_pending_background(self, consumer_token: mwoauth.ConsumerToken, user_agent: str) -> Optional[Tuple[OpenBatch, CommandPending, mwapi.Session]]: ...


def _local_user_from_session(session: mwapi.Session) -> LocalUser:
    domain = session.host[len('https://'):]
    response = session.get(**{'action': 'query',
                              'meta': 'userinfo',
                              'uiprop': 'centralids',
                              'assert': 'user'}) # assert is a keyword, can’t use kwargs syntax :(
    user_name = response['query']['userinfo']['name']
    local_user_id = response['query']['userinfo']['id']
    global_user_id = response['query']['userinfo']['centralids']['CentralAuth']
    assert user_name
    assert local_user_id > 0
    assert global_user_id > 0
    return LocalUser(user_name, domain, local_user_id, global_user_id)

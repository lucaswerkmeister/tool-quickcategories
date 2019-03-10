import contextlib
import mwapi # type: ignore
import pymysql
from typing import Generator, List, Optional, Tuple

from batch import NewBatch, OpenBatch
from command import CommandPlan, CommandRecord


def _metadata_from_session(session: mwapi.Session) -> Tuple[str, int, int, str]:
    domain = session.host[len('https://'):]
    response = session.get(action='query',
                           meta='userinfo',
                           uiprop='centralids')
    user_name = response['query']['userinfo']['name']
    local_user_id = response['query']['userinfo']['id']
    global_user_id = response['query']['userinfo']['centralids']['CentralAuth']
    return user_name, local_user_id, global_user_id, domain


class InMemoryStore:

    def __init__(self):
        self.next_batch_id = 1
        self.next_command_id = 1
        self.batches = {}

    def store_batch(self, new_batch: NewBatch, session: mwapi.Session) -> OpenBatch:
        command_plans = [] # type: List[CommandRecord]
        for command in new_batch.commands:
            command_plans.append(CommandPlan(self.next_command_id, command))
            self.next_command_id += 1

        user_name, local_user_id, global_user_id, domain = _metadata_from_session(session)

        open_batch = OpenBatch(self.next_batch_id,
                               user_name,
                               local_user_id,
                               global_user_id,
                               domain,
                               command_plans)
        self.next_batch_id += 1
        self.batches[open_batch.id] = open_batch
        return open_batch

    def get_batch(self, id: int) -> Optional[OpenBatch]:
        return self.batches.get(id)


class DatabaseStore:

    _BATCH_STATUS_OPEN = 0

    _COMMAND_STATUS_PLAN = 0

    def __init__(self, connection_params: dict):
        connection_params.setdefault('charset', 'utf8mb4')
        self.connection_params = connection_params

    @contextlib.contextmanager
    def _connect(self) -> Generator[pymysql.connections.Connection, None, None]:
        connection = pymysql.connect(**self.connection_params)
        try:
            yield connection
        finally:
            connection.close()

    def store_batch(self, new_batch: NewBatch, session: mwapi.Session) -> OpenBatch:
        user_name, local_user_id, global_user_id, domain = _metadata_from_session(session)

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('INSERT INTO `batch` (`batch_user_name`, `batch_local_user_id`, `batch_global_user_id`, `batch_domain`, `batch_status`) VALUES (%s, %s, %s, %s, %s)',
                               (user_name, local_user_id, global_user_id, domain, DatabaseStore._BATCH_STATUS_OPEN))
                batch_id = cursor.lastrowid

            with connection.cursor() as cursor:
                cursor.executemany('INSERT INTO `command` (`command_batch`, `command_tpsv`, `command_status`, `command_outcome`) VALUES (%s, %s, %s, NULL)',
                                   [(batch_id, str(command), DatabaseStore._COMMAND_STATUS_PLAN) for command in new_batch.commands])

            connection.commit()

            with connection.cursor() as cursor:
                cursor.execute('SELECT `command_id` FROM `command` WHERE `command_batch` = %s ORDER BY `command_id` ASC', (batch_id,))
                command_ids = cursor.fetchall()

        command_plans = [] # type: List[CommandRecord]
        for (command_id, ), command in zip(command_ids, new_batch.commands):
            command_plans.append(CommandPlan(command_id, command))

        return OpenBatch(batch_id,
                         user_name,
                         local_user_id,
                         global_user_id,
                         domain,
                         command_plans)

import contextlib
import json
import mwapi # type: ignore
import pymysql
from typing import Generator, Iterable, List, MutableSequence, Optional, Tuple, Union, overload

from batch import NewBatch, OpenBatch
from command import CommandPlan, CommandRecord, CommandFinish, CommandEdit, CommandNoop, CommandPageMissing, CommandEditConflict
import parse_tpsv


def _metadata_from_session(session: mwapi.Session) -> Tuple[str, int, int, str]:
    domain = session.host[len('https://'):]
    response = session.get(action='query',
                           meta='userinfo',
                           uiprop='centralids')
    user_name = response['query']['userinfo']['name']
    local_user_id = response['query']['userinfo']['id']
    global_user_id = response['query']['userinfo']['centralids']['CentralAuth']
    return user_name, local_user_id, global_user_id, domain


class BatchStore:

    def store_batch(self, new_batch: NewBatch, session: mwapi.Session) -> OpenBatch: ...

    def get_batch(self, id: int) -> Optional[OpenBatch]: ...


class InMemoryStore(BatchStore):

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


class DatabaseStore(BatchStore):

    _BATCH_STATUS_OPEN = 0

    _COMMAND_STATUS_PLAN = 0
    _COMMAND_STATUS_EDIT = 1
    _COMMAND_STATUS_NOOP = 2
    _COMMAND_STATUS_PAGE_MISSING = 129
    _COMMAND_STATUS_EDIT_CONFLICT = 130

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

        return OpenBatch(batch_id,
                         user_name,
                         local_user_id,
                         global_user_id,
                         domain,
                         _DatabaseCommandRecords(batch_id, self))

    def get_batch(self, id: int) -> Optional[OpenBatch]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `batch_user_name`, `batch_local_user_id`, `batch_global_user_id`, `batch_domain`, `batch_status`
                                  FROM `batch`
                                  WHERE `batch_id` = %s''', (id,))
                result = cursor.fetchone()
        if not result:
            return None
        user_name, local_user_id, global_user_id, domain, status = result
        assert status == DatabaseStore._BATCH_STATUS_OPEN
        return OpenBatch(id,
                         user_name,
                         local_user_id,
                         global_user_id,
                         domain,
                         _DatabaseCommandRecords(id, self))


class _DatabaseCommandRecords(MutableSequence[CommandRecord]):

    def __init__(self, batch_id: int, store: DatabaseStore):
        self.batch_id = batch_id
        self.store = store

    def _command_record_to_row(self, command_record: CommandRecord) -> Tuple[int, dict]:
        if isinstance(command_record, CommandEdit):
            status = DatabaseStore._COMMAND_STATUS_EDIT
            outcome = {'base_revision': command_record.base_revision, 'revision': command_record.revision} # type: dict
        elif isinstance(command_record, CommandNoop):
            status = DatabaseStore._COMMAND_STATUS_NOOP
            outcome = {'revision': command_record.revision}
        elif isinstance(command_record, CommandPageMissing):
            status = DatabaseStore._COMMAND_STATUS_PAGE_MISSING
            outcome = {'curtimestamp': command_record.curtimestamp}
        elif isinstance(command_record, CommandEditConflict):
            status = DatabaseStore._COMMAND_STATUS_EDIT_CONFLICT
            outcome = {}
        else:
            raise ValueError('Unknown command type')

        return status, outcome

    def _row_to_command_record(self, id: int, tpsv: str, status: int, outcome: Optional[str]) -> CommandRecord:
        if outcome:
            outcome_dict = json.loads(outcome)

        command = parse_tpsv.parse_command(tpsv)

        if status == DatabaseStore._COMMAND_STATUS_PLAN:
            assert outcome is None
            return CommandPlan(id, command)
        elif status == DatabaseStore._COMMAND_STATUS_EDIT:
            return CommandEdit(id,
                               command,
                               base_revision=outcome_dict['base_revision'],
                               revision=outcome_dict['revision'])
        elif status == DatabaseStore._COMMAND_STATUS_NOOP:
            return CommandNoop(id,
                               command,
                               revision=outcome_dict['revision'])
        elif status == DatabaseStore._COMMAND_STATUS_PAGE_MISSING:
            return CommandPageMissing(id,
                                      command,
                                      curtimestamp=outcome_dict['curtimestamp'])
        elif status == DatabaseStore._COMMAND_STATUS_EDIT_CONFLICT:
            return CommandEditConflict(id,
                                       command)
        else:
            raise ValueError('Unknown command status %d' % status)

    @overload
    def __getitem__(self, index: int) -> CommandRecord: ...
    @overload
    def __getitem__(self, index: slice) -> List[CommandRecord]: ...
    def __getitem__(self, index):
        if isinstance(index, int):
            index = slice(index, index + 1)
            return_first = True
        else:
            return_first = False
        assert isinstance(index, slice)
        assert isinstance(index.start, int)
        assert isinstance(index.stop, int)
        assert index.step in [None, 1]

        command_records = []
        with self.store._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''SELECT `command_id`, `command_tpsv`, `command_status`, `command_outcome`
                              FROM `command`
                              WHERE `command_batch` = %s
                              ORDER BY `command_id` ASC
                              LIMIT %s OFFSET %s''', (self.batch_id, index.stop - index.start, index.start))
            for id, tpsv, status, outcome in cursor.fetchall():
                command_records.append(self._row_to_command_record(id, tpsv, status, outcome))

        if return_first:
            return command_records[0]
        else:
            return command_records

    def __len__(self) -> int:
        with self.store._connect() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM `command` WHERE `command_batch` = %s', (self.batch_id,))
            (count,) = cursor.fetchone()
        return count

    @overload
    def __setitem__(self, index: int, value: CommandRecord) -> None: ...
    @overload
    def __setitem__(self, index: slice, value: Iterable[CommandRecord]) -> None: ...
    def __setitem__(self, index, value):
        if isinstance(index, slice):
            raise NotImplementedError('Can only set a single command record')
        if isinstance(value, CommandPlan):
            raise NotImplementedError('Can only store finished commands')
        assert isinstance(index, int)
        assert isinstance(value, CommandFinish)

        status, outcome = self._command_record_to_row(value)

        with self.store._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''UPDATE `command`
                              SET `command_status` = %s, `command_outcome` = %s
                              WHERE `command_id` = %s AND `command_batch` = %s''',
                           (status, json.dumps(outcome), value.id, self.batch_id))
            connection.commit()

    def __delitem__(self, *args, **kwargs):
        raise NotImplementedError('Cannot delete commands from a batch')

    def insert(self, *args, **kwargs):
        raise NotImplementedError('Cannot insert commands into a batch')

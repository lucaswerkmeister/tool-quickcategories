import cachetools
import contextlib
import datetime
import hashlib
import json
import mwapi # type: ignore
import operator
import pymysql
import threading
from typing import Generator, Iterable, List, MutableSequence, Optional, Tuple, Union, overload

from batch import NewBatch, OpenBatch
from command import CommandPlan, CommandRecord, CommandFinish, CommandEdit, CommandNoop, CommandPageMissing, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
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
    _COMMAND_STATUS_MAXLAG_EXCEEDED = 131
    _COMMAND_STATUS_BLOCKED = 132
    _COMMAND_STATUS_WIKI_READ_ONLY = 133

    def __init__(self, connection_params: dict):
        connection_params.setdefault('charset', 'utf8mb4')
        self.connection_params = connection_params
        self.domain_store = _StringTableStore('domain', 'domain_id', 'domain_hash', 'domain_name')

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
            domain_id = self.domain_store.acquire_id(connection, domain)
            with connection.cursor() as cursor:
                cursor.execute('INSERT INTO `batch` (`batch_user_name`, `batch_local_user_id`, `batch_global_user_id`, `batch_domain_id`, `batch_status`) VALUES (%s, %s, %s, %s, %s)',
                               (user_name, local_user_id, global_user_id, domain_id, DatabaseStore._BATCH_STATUS_OPEN))
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
                cursor.execute('''SELECT `batch_user_name`, `batch_local_user_id`, `batch_global_user_id`, `domain_name`, `batch_status`
                                  FROM `batch`
                                  JOIN `domain` ON `batch_domain_id` = `domain_id`
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
        elif isinstance(command_record, CommandMaxlagExceeded):
            status = DatabaseStore._COMMAND_STATUS_MAXLAG_EXCEEDED
            outcome = {'retry_after_utc_timestamp': command_record.retry_after.timestamp()}
        elif isinstance(command_record, CommandBlocked):
            status = DatabaseStore._COMMAND_STATUS_BLOCKED
            outcome = {'auto': command_record.auto, 'blockinfo': command_record.blockinfo}
        elif isinstance(command_record, CommandWikiReadOnly):
            status = DatabaseStore._COMMAND_STATUS_WIKI_READ_ONLY
            outcome = {'reason': command_record.reason}
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
        elif status == DatabaseStore._COMMAND_STATUS_MAXLAG_EXCEEDED:
            return CommandMaxlagExceeded(id,
                                         command,
                                         datetime.datetime.fromtimestamp(outcome_dict['retry_after_utc_timestamp'],
                                                                         tz=datetime.timezone.utc))
        elif status == DatabaseStore._COMMAND_STATUS_BLOCKED:
            return CommandBlocked(id,
                                  command,
                                  auto=outcome_dict['auto'],
                                  blockinfo=outcome_dict['blockinfo'])
        elif status == DatabaseStore._COMMAND_STATUS_WIKI_READ_ONLY:
            return CommandWikiReadOnly(id,
                                       command,
                                       outcome_dict['reason'])
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


class _StringTableStore:
    """Encapsulates access to a string that has been extracted into a separate table.

    The separate table is expected to have three columns:
    an automatically incrementing ID,
    an unsigned integer hash (the first four bytes of the SHA2-256 hash of the string),
    and the string itself.

    IDs for the least recently used strings are cached,
    but to look up the string for an ID,
    callers should use a plain SQL JOIN for now."""

    def __init__(self,
                 table_name: str,
                 id_column_name: str,
                 hash_column_name: str,
                 string_column_name: str):
        self.table_name = table_name
        self.id_column_name = id_column_name
        self.hash_column_name = hash_column_name
        self.string_column_name = string_column_name
        self._cache = cachetools.LRUCache(maxsize=1024) # type: cachetools.LRUCache[str, int]
        self._cache_lock = threading.RLock()

    def _hash(self, string: str) -> int:
        hex = hashlib.sha256(string.encode('utf8')).hexdigest()
        return int(hex[:8], base=16)

    @cachetools.cachedmethod(operator.attrgetter('_cache'), key=lambda connection, string: string, lock=operator.attrgetter('_cache_lock'))
    def acquire_id(self, connection: pymysql.connections.Connection, string: str) -> int:
        hash = self._hash(string)

        with connection.cursor() as cursor:
            cursor.execute('''SELECT `%s`
                              FROM `%s`
                              WHERE `%s` = %%s
                              FOR UPDATE''' % (self.id_column_name, self.table_name, self.hash_column_name),
                           (hash,))
            result = cursor.fetchone()
        if result:
            connection.commit() # finish the FOR UPDATE
            return result[0]

        with connection.cursor() as cursor:
            cursor.execute('''INSERT INTO `%s` (`%s`, `%s`)
                              VALUES (%%s, %%s)''' % (self.table_name, self.string_column_name, self.hash_column_name),
                           (string, hash))
            string_id = cursor.lastrowid
        connection.commit()
        return string_id

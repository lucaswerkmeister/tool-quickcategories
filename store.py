import cachetools
import contextlib
import datetime
import hashlib
import json
import mwapi # type: ignore
import operator
import pymysql
import threading
from typing import Any, Generator, List, Optional, Sequence, Tuple

from batch import NewBatch, OpenBatch, BatchCommandRecords, BatchCommandRecordsList
from command import Command, CommandPlan, CommandRecord, CommandFinish, CommandEdit, CommandNoop, CommandPageMissing, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
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


def _now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0)


class BatchStore:

    def store_batch(self, new_batch: NewBatch, session: mwapi.Session) -> OpenBatch: ...

    def get_batch(self, id: int) -> Optional[OpenBatch]: ...

    def get_latest_batches(self) -> Sequence[OpenBatch]: ...


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
        created = _now()

        open_batch = OpenBatch(self.next_batch_id,
                               user_name,
                               local_user_id,
                               global_user_id,
                               domain,
                               created,
                               created,
                               BatchCommandRecordsList(command_plans))
        self.next_batch_id += 1
        self.batches[open_batch.id] = open_batch
        return open_batch

    def get_batch(self, id: int) -> Optional[OpenBatch]:
        return self.batches.get(id)

    def get_latest_batches(self) -> Sequence[OpenBatch]:
        return [self.batches[id] for id in sorted(self.batches.keys(), reverse=True)[:10]]


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
        self.actions_store = _StringTableStore('actions', 'actions_id', 'actions_hash', 'actions_tpsv')

    @contextlib.contextmanager
    def _connect(self) -> Generator[pymysql.connections.Connection, None, None]:
        connection = pymysql.connect(**self.connection_params)
        try:
            yield connection
        finally:
            connection.close()

    def _datetime_to_utc_timestamp(self, dt: datetime.datetime) -> int:
        assert dt.tzinfo == datetime.timezone.utc
        assert dt.microsecond == 0
        return int(dt.timestamp())

    def _utc_timestamp_to_datetime(self, timestamp: int) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(timestamp,
                                               tz=datetime.timezone.utc)

    def store_batch(self, new_batch: NewBatch, session: mwapi.Session) -> OpenBatch:
        user_name, local_user_id, global_user_id, domain = _metadata_from_session(session)
        created = _now()
        created_utc_timestamp = self._datetime_to_utc_timestamp(created)

        with self._connect() as connection:
            domain_id = self.domain_store.acquire_id(connection, domain)
            with connection.cursor() as cursor:
                cursor.execute('INSERT INTO `batch` (`batch_user_name`, `batch_local_user_id`, `batch_global_user_id`, `batch_domain_id`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                               (user_name, local_user_id, global_user_id, domain_id, created_utc_timestamp, created_utc_timestamp, DatabaseStore._BATCH_STATUS_OPEN))
                batch_id = cursor.lastrowid

            with connection.cursor() as cursor:
                cursor.executemany('INSERT INTO `command` (`command_batch`, `command_page`, `command_actions_id`, `command_status`, `command_outcome`) VALUES (%s, %s, %s, %s, NULL)',
                                   [(batch_id, command.page, self.actions_store.acquire_id(connection, command.actions_tpsv()), DatabaseStore._COMMAND_STATUS_PLAN) for command in new_batch.commands])

            connection.commit()

        return OpenBatch(batch_id,
                         user_name,
                         local_user_id,
                         global_user_id,
                         domain,
                         created,
                         created,
                         _BatchCommandRecordsDatabase(batch_id, self))

    def get_batch(self, id: int) -> Optional[OpenBatch]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `batch_id`, `batch_user_name`, `batch_local_user_id`, `batch_global_user_id`, `domain_name`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`
                                  FROM `batch`
                                  JOIN `domain` ON `batch_domain_id` = `domain_id`
                                  WHERE `batch_id` = %s''', (id,))
                result = cursor.fetchone()
        if not result:
            return None
        return self._result_to_batch(result)

    def _result_to_batch(self, result: tuple) -> OpenBatch:
        id, user_name, local_user_id, global_user_id, domain, created_utc_timestamp, last_updated_utc_timestamp, status = result
        assert status == DatabaseStore._BATCH_STATUS_OPEN
        created = self._utc_timestamp_to_datetime(created_utc_timestamp)
        last_updated = self._utc_timestamp_to_datetime(last_updated_utc_timestamp)
        return OpenBatch(id,
                         user_name,
                         local_user_id,
                         global_user_id,
                         domain,
                         created,
                         last_updated,
                         _BatchCommandRecordsDatabase(id, self))

    def get_latest_batches(self) -> Sequence[OpenBatch]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `batch_id`, `batch_user_name`, `batch_local_user_id`, `batch_global_user_id`, `domain_name`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`
                                  FROM `batch`
                                  JOIN `domain` ON `batch_domain_id` = `domain_id`
                                  ORDER BY `batch_id` DESC
                                  LIMIT 10''')
                return [self._result_to_batch(result) for result in cursor.fetchall()]


class _BatchCommandRecordsDatabase(BatchCommandRecords):

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
            outcome = {'retry_after_utc_timestamp': self.store._datetime_to_utc_timestamp(command_record.retry_after)}
        elif isinstance(command_record, CommandBlocked):
            status = DatabaseStore._COMMAND_STATUS_BLOCKED
            outcome = {'auto': command_record.auto, 'blockinfo': command_record.blockinfo}
        elif isinstance(command_record, CommandWikiReadOnly):
            status = DatabaseStore._COMMAND_STATUS_WIKI_READ_ONLY
            outcome = {'reason': command_record.reason}
        else:
            raise ValueError('Unknown command type')

        return status, outcome

    def _row_to_command_record(self, id: int, page: str, actions_tpsv: str, status: int, outcome: Optional[str]) -> CommandRecord:
        if outcome:
            outcome_dict = json.loads(outcome)

        command = Command(page,
                          [parse_tpsv.parse_action(field) for field in actions_tpsv.split('|')])

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
                                         self.store._utc_timestamp_to_datetime(outcome_dict['retry_after_utc_timestamp']))
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

    def get_slice(self, offset: int, limit: int) -> List[CommandRecord]:
        command_records = []
        with self.store._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''SELECT `command_id`, `command_page`, `actions_tpsv`, `command_status`, `command_outcome`
                              FROM `command`
                              JOIN `actions` ON `command_actions_id` = `actions_id`
                              WHERE `command_batch` = %s
                              ORDER BY `command_id` ASC
                              LIMIT %s OFFSET %s''', (self.batch_id, limit, offset))
            for id, page, actions_tpsv, status, outcome in cursor.fetchall():
                command_records.append(self._row_to_command_record(id, page, actions_tpsv, status, outcome))
        return command_records

    def __len__(self) -> int:
        with self.store._connect() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM `command` WHERE `command_batch` = %s', (self.batch_id,))
            (count,) = cursor.fetchone()
        return count

    def store_finish(self, command_finish: CommandFinish) -> None:
        status, outcome = self._command_record_to_row(command_finish)
        last_updated = _now()
        last_updated_utc_timestamp = self.store._datetime_to_utc_timestamp(last_updated)

        with self.store._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''UPDATE `command`
                              SET `command_status` = %s, `command_outcome` = %s
                              WHERE `command_id` = %s AND `command_batch` = %s''',
                           (status, json.dumps(outcome), command_finish.id, self.batch_id))
            cursor.execute('''UPDATE `batch`
                              SET `batch_last_updated_utc_timestamp` = %s
                              WHERE `batch_id` = %s''', (last_updated_utc_timestamp, self.batch_id))
            connection.commit()

    def __eq__(self, value: Any) -> bool:
        # limited test to avoid overly expensive full comparison
        return type(value) is _BatchCommandRecordsDatabase and \
            self.batch_id == value.batch_id


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

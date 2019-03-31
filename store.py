import cachetools
import contextlib
import datetime
import hashlib
import itertools
import json
import mwapi # type: ignore
import mwoauth # type: ignore
import operator
import pymysql
import requests_oauthlib # type: ignore
import threading
from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple, cast

from batch import NewBatch, StoredBatch, OpenBatch, ClosedBatch, BatchCommandRecords, BatchCommandRecordsList
from command import Command, CommandPlan, CommandPending, CommandRecord, CommandFinish, CommandEdit, CommandNoop, CommandPageMissing, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
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

    def get_batch(self, id: int) -> Optional[StoredBatch]: ...

    def get_latest_batches(self) -> Sequence[StoredBatch]: ...

    def start_background(self, batch: OpenBatch, session: mwapi.Session) -> None: ...

    def stop_background(self, batch: StoredBatch, session: Optional[mwapi.Session] = None) -> None: ...

    def make_plan_pending_background(self, consumer_token: mwoauth.ConsumerToken, user_agent: str) -> Optional[Tuple[OpenBatch, CommandPending, mwapi.Session]]: ...


class InMemoryStore(BatchStore):

    def __init__(self):
        self.next_batch_id = 1
        self.next_command_id = 1
        self.batches = {} # type: Dict[int, StoredBatch]
        self.started_backgrounds = {} # type: Dict[int, Tuple[datetime.datetime, mwapi.Session]]
        self.stopped_backgrounds = {} # type: Dict[int, List[Tuple[datetime.datetime, mwapi.Session, datetime.datetime, Optional[mwapi.Session]]]]

    def store_batch(self, new_batch: NewBatch, session: mwapi.Session) -> OpenBatch:
        created = _now()
        user_name, local_user_id, global_user_id, domain = _metadata_from_session(session)

        command_plans = [] # type: List[CommandRecord]
        for command in new_batch.commands:
            command_plans.append(CommandPlan(self.next_command_id, command))
            self.next_command_id += 1

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

    def get_batch(self, id: int) -> Optional[StoredBatch]:
        stored_batch = self.batches.get(id)
        if stored_batch is None:
            return None

        command_records = cast(BatchCommandRecordsList, stored_batch.command_records).command_records
        if isinstance(stored_batch, OpenBatch) and \
           all(map(lambda command_record: isinstance(command_record, CommandFinish), command_records)):
            stored_batch = ClosedBatch(stored_batch.id,
                                       stored_batch.user_name,
                                       stored_batch.local_user_id,
                                       stored_batch.global_user_id,
                                       stored_batch.domain,
                                       stored_batch.created,
                                       stored_batch.last_updated,
                                       stored_batch.command_records)
            self.batches[id] = stored_batch
        return stored_batch

    def get_latest_batches(self) -> Sequence[StoredBatch]:
        return [cast(StoredBatch, self.get_batch(id)) for id in sorted(self.batches.keys(), reverse=True)[:10]]

    def start_background(self, batch: OpenBatch, session: mwapi.Session) -> None:
        started = _now()
        if batch.id not in self.started_backgrounds:
            self.started_backgrounds[batch.id] = (started, session)

    def stop_background(self, batch: StoredBatch, session: Optional[mwapi.Session] = None) -> None:
        stopped = _now()
        if batch.id in self.started_backgrounds:
            started, started_session = self.started_backgrounds[batch.id]
            stopped_backgrounds = self.stopped_backgrounds.get(batch.id, [])
            stopped_backgrounds.append((started, started_session, stopped, session))
            self.stopped_backgrounds[batch.id] = stopped_backgrounds
            del self.started_backgrounds[batch.id]

    def make_plan_pending_background(self, consumer_token: mwoauth.ConsumerToken, user_agent: str) -> Optional[Tuple[OpenBatch, CommandPending, mwapi.Session]]:
        batch_ids_by_last_updated = sorted(self.started_backgrounds, key=lambda id: self.batches[id].last_updated)
        if not batch_ids_by_last_updated:
            return None
        batch = self.batches[batch_ids_by_last_updated[0]]
        assert isinstance(batch, OpenBatch)
        assert isinstance(batch.command_records, BatchCommandRecordsList)
        for index, command_plan in enumerate(batch.command_records.command_records):
            if not isinstance(command_plan, CommandPlan):
                continue
            command_pending = CommandPending(command_plan.id, command_plan.command)
            batch.command_records.command_records[index] = command_pending
        return batch, command_pending, self.started_backgrounds[batch.id][1]


class DatabaseStore(BatchStore):

    _BATCH_STATUS_OPEN = 0
    _BATCH_STATUS_CLOSED = 128

    _COMMAND_STATUS_PLAN = 0
    _COMMAND_STATUS_EDIT = 1
    _COMMAND_STATUS_NOOP = 2
    _COMMAND_STATUS_PENDING = 16
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
        created = _now()
        created_utc_timestamp = self._datetime_to_utc_timestamp(created)
        user_name, local_user_id, global_user_id, domain = _metadata_from_session(session)

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

    def get_batch(self, id: int) -> Optional[StoredBatch]:
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

    def _result_to_batch(self, result: tuple) -> StoredBatch:
        id, user_name, local_user_id, global_user_id, domain, created_utc_timestamp, last_updated_utc_timestamp, status = result
        created = self._utc_timestamp_to_datetime(created_utc_timestamp)
        last_updated = self._utc_timestamp_to_datetime(last_updated_utc_timestamp)
        if status == DatabaseStore._BATCH_STATUS_OPEN:
            return OpenBatch(id,
                             user_name,
                             local_user_id,
                             global_user_id,
                             domain,
                             created,
                             last_updated,
                             _BatchCommandRecordsDatabase(id, self))
        elif status == DatabaseStore._BATCH_STATUS_CLOSED:
            return ClosedBatch(id,
                               user_name,
                               local_user_id,
                               global_user_id,
                               domain,
                               created,
                               last_updated,
                               _BatchCommandRecordsDatabase(id, self))
        else:
            raise ValueError('Unknown batch type')

    def get_latest_batches(self) -> Sequence[StoredBatch]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `batch_id`, `batch_user_name`, `batch_local_user_id`, `batch_global_user_id`, `domain_name`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`
                                  FROM `batch`
                                  JOIN `domain` ON `batch_domain_id` = `domain_id`
                                  ORDER BY `batch_id` DESC
                                  LIMIT 10''')
                return [self._result_to_batch(result) for result in cursor.fetchall()]

    def start_background(self, batch: OpenBatch, session: mwapi.Session) -> None:
        started = _now()
        started_utc_timestamp = self._datetime_to_utc_timestamp(started)
        user_name, local_user_id, global_user_id, domain = _metadata_from_session(session)

        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''SELECT 1
                              FROM `background`
                              WHERE `background_batch` = %s
                              AND `background_stopped_utc_timestamp` IS NULL
                              FOR UPDATE''',
                           (batch.id,))
            if cursor.fetchone():
                connection.commit() # finish the FOR UPDATE
                return

            assert isinstance(session.session.auth, requests_oauthlib.OAuth1)
            auth = {'resource_owner_key': session.session.auth.client.resource_owner_key,
                    'resource_owner_secret': session.session.auth.client.resource_owner_secret}

            cursor.execute('''INSERT INTO `background`
                              (`background_batch`, `background_auth`, `background_started_utc_timestamp`, `background_started_user_name`, `background_started_local_user_id`, `background_started_global_user_id`)
                              VALUES (%s, %s, %s, %s, %s, %s)''',
                           (batch.id, json.dumps(auth), started_utc_timestamp, user_name, local_user_id, global_user_id))
            connection.commit()

    def stop_background(self, batch: StoredBatch, session: Optional[mwapi.Session] = None) -> None:
        self._stop_background_by_id(batch.id, session)

    def _stop_background_by_id(self, batch_id: int, session: Optional[mwapi.Session] = None) -> None:
        stopped = _now()
        stopped_utc_timestamp = self._datetime_to_utc_timestamp(stopped)
        if session:
            user_name, local_user_id, global_user_id, domain = _metadata_from_session(session) # type: Tuple[Optional[str], Optional[int], Optional[int], str]
        else:
            user_name, local_user_id, global_user_id = None, None, None
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''UPDATE `background`
                              SET `background_auth` = NULL, `background_stopped_utc_timestamp` = %s, `background_stopped_user_name` = %s, `background_stopped_local_user_id` = %s, `background_stopped_global_user_id` = %s
                              WHERE `background_batch` = %s
                              AND `background_stopped_utc_timestamp` IS NULL''',
                           (stopped_utc_timestamp, user_name, local_user_id, global_user_id, batch_id))
            connection.commit()
            if cursor.rowcount > 1:
                raise RuntimeError('Should have stopped at most 1 background operation, actually affected %d!' % cursor.rowcount)

    def make_plan_pending_background(self, consumer_token: mwoauth.ConsumerToken, user_agent: str) -> Optional[Tuple[OpenBatch, CommandPending, mwapi.Session]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `batch_id`, `batch_user_name`, `batch_local_user_id`, `batch_global_user_id`, `domain_name`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`, `background_auth`, `command_id`, `command_page`, `actions_tpsv`
                                  FROM `batch`
                                  JOIN `background` ON `background_batch` = `batch_id`
                                  JOIN `command` ON `command_batch` = `batch_id`
                                  JOIN `domain` ON `batch_domain_id` = `domain_id`
                                  JOIN `actions` ON `command_actions_id` = `actions_id`
                                  WHERE `background_stopped_utc_timestamp` IS NULL
                                  AND `command_status` = %s
                                  ORDER BY `batch_last_updated_utc_timestamp` ASC, `command_id` ASC
                                  LIMIT 1
                                  FOR UPDATE''',
                               (DatabaseStore._COMMAND_STATUS_PLAN))
                result = cursor.fetchone()
            if not result:
                connection.commit() # finish the FOR UPDATE
                return None

            with connection.cursor() as cursor:
                cursor.execute('''UPDATE `command`
                                  SET `command_status` = %s
                                  WHERE `command_id` = %s AND `command_batch` = %s''',
                               (DatabaseStore._COMMAND_STATUS_PENDING, result[9], result[0]))
            connection.commit()

        auth_data = json.loads(result[8])
        auth = requests_oauthlib.OAuth1(client_key=consumer_token.key, client_secret=consumer_token.secret,
                                        resource_owner_key=auth_data['resource_owner_key'], resource_owner_secret=auth_data['resource_owner_secret'])
        session = mwapi.Session(host='https://'+result[4], auth=auth, user_agent=user_agent)
        command_pending = _BatchCommandRecordsDatabase(result[0], self)._row_to_command_record(result[9],
                                                                                               result[10],
                                                                                               result[11],
                                                                                               DatabaseStore._COMMAND_STATUS_PENDING,
                                                                                               outcome=None)
        batch = self._result_to_batch(result[0:8])

        assert isinstance(batch, OpenBatch), "must be open since at least one command is still pending"
        assert isinstance(command_pending, CommandPending), "must be pending since we just set that status"
        return batch, command_pending, session


class _BatchCommandRecordsDatabase(BatchCommandRecords):

    def __init__(self, batch_id: int, store: DatabaseStore):
        self.batch_id = batch_id
        self.store = store

    def _command_finish_to_row(self, command_finish: CommandFinish) -> Tuple[int, dict]:
        if isinstance(command_finish, CommandEdit):
            status = DatabaseStore._COMMAND_STATUS_EDIT
            outcome = {'base_revision': command_finish.base_revision, 'revision': command_finish.revision} # type: dict
        elif isinstance(command_finish, CommandNoop):
            status = DatabaseStore._COMMAND_STATUS_NOOP
            outcome = {'revision': command_finish.revision}
        elif isinstance(command_finish, CommandPageMissing):
            status = DatabaseStore._COMMAND_STATUS_PAGE_MISSING
            outcome = {'curtimestamp': command_finish.curtimestamp}
        elif isinstance(command_finish, CommandEditConflict):
            status = DatabaseStore._COMMAND_STATUS_EDIT_CONFLICT
            outcome = {}
        elif isinstance(command_finish, CommandMaxlagExceeded):
            status = DatabaseStore._COMMAND_STATUS_MAXLAG_EXCEEDED
            outcome = {'retry_after_utc_timestamp': self.store._datetime_to_utc_timestamp(command_finish.retry_after)}
        elif isinstance(command_finish, CommandBlocked):
            status = DatabaseStore._COMMAND_STATUS_BLOCKED
            outcome = {'auto': command_finish.auto, 'blockinfo': command_finish.blockinfo}
        elif isinstance(command_finish, CommandWikiReadOnly):
            status = DatabaseStore._COMMAND_STATUS_WIKI_READ_ONLY
            outcome = {'reason': command_finish.reason}
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
        elif status == DatabaseStore._COMMAND_STATUS_PENDING:
            assert outcome is None
            return CommandPending(id, command)
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

    def make_plans_pending(self, offset: int, limit: int) -> List[CommandPending]:
        with self.store._connect() as connection:
            command_ids = [] # List[int]

            with connection.cursor() as cursor:
                # the extra subquery layer below is necessary to work around a MySQL/MariaDB restriction;
                # based on https://stackoverflow.com/a/24777566/1420237
                cursor.execute('''SELECT `command_id`
                                  FROM `command`
                                  WHERE `command_id` IN ( SELECT * FROM (
                                    SELECT `command_id`
                                    FROM `command`
                                    WHERE `command_batch` = %s
                                    ORDER BY `command_id` ASC
                                    LIMIT %s OFFSET %s
                                  ) AS temporary_table)
                                  AND `command_status` = %s
                                  ORDER BY `command_id` ASC
                                  FOR UPDATE''', (self.batch_id, limit, offset, DatabaseStore._COMMAND_STATUS_PLAN))
                for (command_id,) in cursor.fetchall():
                    command_ids.append(command_id)

            if not command_ids:
                connection.commit() # finish the FOR UPDATE
                return []

            with connection.cursor() as cursor:
                cursor.executemany('''UPDATE `command`
                                      SET `command_status` = %s
                                      WHERE `command_id` = %s AND `command_batch` = %s''',
                                   zip(itertools.repeat(DatabaseStore._COMMAND_STATUS_PENDING),
                                       command_ids,
                                       itertools.repeat(self.batch_id)))
            connection.commit()

            command_records = []
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `command_id`, `command_page`, `actions_tpsv`, `command_status`, `command_outcome`
                                  FROM `command`
                                  JOIN `actions` ON `command_actions_id` = `actions_id`
                                  WHERE `command_id` IN (%s)''' % ', '.join(['%s'] * len(command_ids)),
                               command_ids)
            for id, page, actions_tpsv, status, outcome in cursor.fetchall():
                assert status == DatabaseStore._COMMAND_STATUS_PENDING
                assert outcome is None
                command_record = self._row_to_command_record(id, page, actions_tpsv, status, outcome)
                assert isinstance(command_record, CommandPending)
                command_records.append(command_record)
        return command_records

    def store_finish(self, command_finish: CommandFinish) -> None:
        last_updated = _now()
        last_updated_utc_timestamp = self.store._datetime_to_utc_timestamp(last_updated)
        status, outcome = self._command_finish_to_row(command_finish)

        with self.store._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''UPDATE `command`
                              SET `command_status` = %s, `command_outcome` = %s
                              WHERE `command_id` = %s AND `command_batch` = %s''',
                           (status, json.dumps(outcome), command_finish.id, self.batch_id))
            cursor.execute('''UPDATE `batch`
                              SET `batch_last_updated_utc_timestamp` = %s
                              WHERE `batch_id` = %s''', (last_updated_utc_timestamp, self.batch_id))
            connection.commit()
            cursor.execute('''SELECT 1
                              FROM `command`
                              WHERE `command_batch` = %s
                              AND `command_status` IN (%s, %s)
                              LIMIT 1''',
                           (self.batch_id, DatabaseStore._COMMAND_STATUS_PLAN, DatabaseStore._COMMAND_STATUS_PENDING))
            if not cursor.fetchone():
                # close the batch
                cursor.execute('''UPDATE `batch`
                                  SET `batch_status` = %s
                                  WHERE `batch_id` = %s''',
                               (DatabaseStore._BATCH_STATUS_CLOSED, self.batch_id))
                connection.commit()
                self.store._stop_background_by_id(self.batch_id)

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

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
from typing import Any, Generator, List, Optional, Sequence, Tuple

from batch import NewBatch, StoredBatch, OpenBatch, ClosedBatch, BatchCommandRecords, BatchBackgroundRuns
from command import Command, CommandPlan, CommandPending, CommandRecord, CommandFinish, CommandEdit, CommandNoop, CommandFailure, CommandPageMissing, CommandPageProtected, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
from localuser import LocalUser
import parse_tpsv
from store import BatchStore, _local_user_from_session, _now


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
    _COMMAND_STATUS_PAGE_PROTECTED = 134

    def __init__(self, connection_params: dict):
        connection_params.setdefault('charset', 'utf8mb4')
        self.connection_params = connection_params
        self.domain_store = _StringTableStore('domain', 'domain_id', 'domain_hash', 'domain_name')
        self.actions_store = _StringTableStore('actions', 'actions_id', 'actions_hash', 'actions_tpsv')
        self.local_user_store = _LocalUserStore(self.domain_store)

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
        local_user = _local_user_from_session(session)

        with self._connect() as connection:
            domain_id = self.domain_store.acquire_id(connection, local_user.domain)
            localuser_id = self.local_user_store.acquire_localuser_id(connection, local_user)
            with connection.cursor() as cursor:
                cursor.execute('INSERT INTO `batch` (`batch_localuser_id`, `batch_domain_id`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`) VALUES (%s, %s, %s, %s, %s)',
                               (localuser_id, domain_id, created_utc_timestamp, created_utc_timestamp, DatabaseStore._BATCH_STATUS_OPEN))
                batch_id = cursor.lastrowid

            with connection.cursor() as cursor:
                cursor.executemany('INSERT INTO `command` (`command_batch`, `command_page`, `command_actions_id`, `command_status`, `command_outcome`) VALUES (%s, %s, %s, %s, NULL)',
                                   [(batch_id, command.page, self.actions_store.acquire_id(connection, command.actions_tpsv()), DatabaseStore._COMMAND_STATUS_PLAN) for command in new_batch.commands])

            connection.commit()

        return OpenBatch(batch_id,
                         local_user,
                         local_user.domain,
                         created,
                         created,
                         _BatchCommandRecordsDatabase(batch_id, self),
                         _BatchBackgroundRunsDatabase(batch_id, local_user.domain, self))

    def get_batch(self, id: int) -> Optional[StoredBatch]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `batch_id`, `localuser_user_name`, `localuser_local_user_id`, `localuser_global_user_id`, `domain_name`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`
                                  FROM `batch`
                                  JOIN `domain` ON `batch_domain_id` = `domain_id`
                                  JOIN `localuser` ON `batch_localuser_id` = `localuser_id`
                                  WHERE `batch_id` = %s''', (id,))
                result = cursor.fetchone()
        if not result:
            return None
        return self._result_to_batch(result)

    def _result_to_batch(self, result: tuple) -> StoredBatch:
        id, user_name, local_user_id, global_user_id, domain, created_utc_timestamp, last_updated_utc_timestamp, status = result
        created = self._utc_timestamp_to_datetime(created_utc_timestamp)
        last_updated = self._utc_timestamp_to_datetime(last_updated_utc_timestamp)
        local_user = LocalUser(user_name, domain, local_user_id, global_user_id)
        if status == DatabaseStore._BATCH_STATUS_OPEN:
            return OpenBatch(id,
                             local_user,
                             local_user.domain,
                             created,
                             last_updated,
                             _BatchCommandRecordsDatabase(id, self),
                             _BatchBackgroundRunsDatabase(id, local_user.domain, self))
        elif status == DatabaseStore._BATCH_STATUS_CLOSED:
            return ClosedBatch(id,
                               local_user,
                               local_user.domain,
                               created,
                               last_updated,
                               _BatchCommandRecordsDatabase(id, self),
                               _BatchBackgroundRunsDatabase(id, local_user.domain, self))
        else:
            raise ValueError('Unknown batch type')

    def get_latest_batches(self) -> Sequence[StoredBatch]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `batch_id`, `localuser_user_name`, `localuser_local_user_id`, `localuser_global_user_id`, `domain_name`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`
                                  FROM `batch`
                                  JOIN `domain` ON `batch_domain_id` = `domain_id`
                                  JOIN `localuser` ON `batch_localuser_id` = `localuser_id`
                                  ORDER BY `batch_id` DESC
                                  LIMIT 10''')
                return [self._result_to_batch(result) for result in cursor.fetchall()]

    def start_background(self, batch: OpenBatch, session: mwapi.Session) -> None:
        started = _now()
        started_utc_timestamp = self._datetime_to_utc_timestamp(started)
        local_user = _local_user_from_session(session)

        with self._connect() as connection:
            with connection.cursor() as cursor:
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

            localuser_id = self.local_user_store.acquire_localuser_id(connection, local_user)

            with connection.cursor() as cursor:
                cursor.execute('''INSERT INTO `background`
                                  (`background_batch`, `background_auth`, `background_started_utc_timestamp`, `background_started_localuser_id`)
                                  VALUES (%s, %s, %s, %s)''',
                               (batch.id, json.dumps(auth), started_utc_timestamp, localuser_id))
            connection.commit()

    def stop_background(self, batch: StoredBatch, session: Optional[mwapi.Session] = None) -> None:
        self._stop_background_by_id(batch.id, session)

    def _stop_background_by_id(self, batch_id: int, session: Optional[mwapi.Session] = None) -> None:
        stopped = _now()
        stopped_utc_timestamp = self._datetime_to_utc_timestamp(stopped)
        with self._connect() as connection:
            if session:
                local_user = _local_user_from_session(session)
                localuser_id = self.local_user_store.acquire_localuser_id(connection, local_user) # type: Optional[int]
            else:
                localuser_id = None
            with connection.cursor() as cursor:
                cursor.execute('''UPDATE `background`
                                  SET `background_auth` = NULL, `background_stopped_utc_timestamp` = %s, `background_stopped_localuser_id` = %s, `background_suspended_until_utc_timestamp` = NULL
                                  WHERE `background_batch` = %s
                                  AND `background_stopped_utc_timestamp` IS NULL''',
                               (stopped_utc_timestamp, localuser_id, batch_id))
            connection.commit()
            if cursor.rowcount > 1:
                raise RuntimeError('Should have stopped at most 1 background operation, actually affected %d!' % cursor.rowcount)

    def suspend_background(self, batch: StoredBatch, until: datetime.datetime) -> None:
        until_utc_timestamp = self._datetime_to_utc_timestamp(until)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''UPDATE `background`
                              SET `background_suspended_until_utc_timestamp` = %s
                              WHERE `background_batch` = %s
                              AND `background_stopped_utc_timestamp` IS NULL''',
                           (until_utc_timestamp, batch.id))
            connection.commit()
            if cursor.rowcount > 1:
                raise RuntimeError('Should have suspended at most 1 background run, actually affected %d!' % cursor.rowcount)

    def make_plan_pending_background(self, consumer_token: mwoauth.ConsumerToken, user_agent: str) -> Optional[Tuple[OpenBatch, CommandPending, mwapi.Session]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                now = _now()
                now_utc_timestamp = self._datetime_to_utc_timestamp(now)
                cursor.execute('''SELECT `batch_id`, `localuser_user_name`, `localuser_local_user_id`, `localuser_global_user_id`, `domain_name`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`, `background_auth`, `command_id`, `command_page`, `actions_tpsv`
                                  FROM `background`
                                  JOIN `batch` ON `background_batch` = `batch_id`
                                  JOIN `command` ON `command_batch` = `batch_id`
                                  JOIN `domain` ON `batch_domain_id` = `domain_id`
                                  JOIN `actions` ON `command_actions_id` = `actions_id`
                                  JOIN `localuser` ON `batch_localuser_id` = `localuser_id`
                                  WHERE `background_stopped_utc_timestamp` IS NULL
                                  AND COALESCE(`background_suspended_until_utc_timestamp`, 0) < %s
                                  AND `command_status` = %s
                                  ORDER BY `batch_last_updated_utc_timestamp` ASC, `command_id` ASC
                                  LIMIT 1
                                  FOR UPDATE''',
                               (now_utc_timestamp, DatabaseStore._COMMAND_STATUS_PLAN))
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
        command_pending = self._row_to_command_record(result[9],
                                                      result[10],
                                                      result[11],
                                                      DatabaseStore._COMMAND_STATUS_PENDING,
                                                      outcome=None)
        batch = self._result_to_batch(result[0:8])

        assert isinstance(batch, OpenBatch), "must be open since at least one command is still pending"
        assert isinstance(command_pending, CommandPending), "must be pending since we just set that status"
        return batch, command_pending, session

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
        elif isinstance(command_finish, CommandPageProtected):
            status = DatabaseStore._COMMAND_STATUS_PAGE_PROTECTED
            outcome = {'curtimestamp': command_finish.curtimestamp}
        elif isinstance(command_finish, CommandEditConflict):
            status = DatabaseStore._COMMAND_STATUS_EDIT_CONFLICT
            outcome = {}
        elif isinstance(command_finish, CommandMaxlagExceeded):
            status = DatabaseStore._COMMAND_STATUS_MAXLAG_EXCEEDED
            outcome = {'retry_after_utc_timestamp': self._datetime_to_utc_timestamp(command_finish.retry_after)}
        elif isinstance(command_finish, CommandBlocked):
            status = DatabaseStore._COMMAND_STATUS_BLOCKED
            outcome = {'auto': command_finish.auto, 'blockinfo': command_finish.blockinfo}
        elif isinstance(command_finish, CommandWikiReadOnly):
            status = DatabaseStore._COMMAND_STATUS_WIKI_READ_ONLY
            outcome = {'reason': command_finish.reason}
            if command_finish.retry_after:
                outcome['retry_after_utc_timestamp'] = self._datetime_to_utc_timestamp(command_finish.retry_after)
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
        elif status == DatabaseStore._COMMAND_STATUS_PAGE_PROTECTED:
            return CommandPageProtected(id,
                                        command,
                                        curtimestamp=outcome_dict['curtimestamp'])
        elif status == DatabaseStore._COMMAND_STATUS_EDIT_CONFLICT:
            return CommandEditConflict(id,
                                       command)
        elif status == DatabaseStore._COMMAND_STATUS_MAXLAG_EXCEEDED:
            return CommandMaxlagExceeded(id,
                                         command,
                                         self._utc_timestamp_to_datetime(outcome_dict['retry_after_utc_timestamp']))
        elif status == DatabaseStore._COMMAND_STATUS_BLOCKED:
            return CommandBlocked(id,
                                  command,
                                  auto=outcome_dict['auto'],
                                  blockinfo=outcome_dict['blockinfo'])
        elif status == DatabaseStore._COMMAND_STATUS_WIKI_READ_ONLY:
            if 'retry_after_utc_timestamp' in outcome_dict:
                retry_after = self._utc_timestamp_to_datetime(outcome_dict['retry_after_utc_timestamp']) # type: Optional[datetime.datetime]
            else:
                retry_after = None
            return CommandWikiReadOnly(id,
                                       command,
                                       outcome_dict['reason'],
                                       retry_after)
        else:
            raise ValueError('Unknown command status %d' % status)


class _BatchCommandRecordsDatabase(BatchCommandRecords):

    def __init__(self, batch_id: int, store: DatabaseStore):
        self.batch_id = batch_id
        self.store = store

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
                command_records.append(self.store._row_to_command_record(id, page, actions_tpsv, status, outcome))
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
                command_record = self.store._row_to_command_record(id, page, actions_tpsv, status, outcome)
                assert isinstance(command_record, CommandPending)
                command_records.append(command_record)
        return command_records

    def make_pendings_planned(self, command_record_ids: List[int]) -> None:
        with self.store._connect() as connection, connection.cursor() as cursor:
            parameters = [DatabaseStore._COMMAND_STATUS_PLAN] # in Python 3.5+, replace that with [DS._C_S_PLAN, *c_r_ids, DS._C_S_PENDING]
            parameters.extend(command_record_ids)
            parameters.append(DatabaseStore._COMMAND_STATUS_PENDING)
            cursor.execute('''UPDATE `command`
                              SET `command_status` = %%s
                              WHERE `command_id` IN (%s)
                              AND `command_status` = %%s''' % ', '.join(['%s'] * len(command_record_ids)),
                           parameters)
            connection.commit()

    def store_finish(self, command_finish: CommandFinish) -> None:
        last_updated = _now()
        last_updated_utc_timestamp = self.store._datetime_to_utc_timestamp(last_updated)
        status, outcome = self.store._command_finish_to_row(command_finish)

        with self.store._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''UPDATE `command`
                              SET `command_status` = %s, `command_outcome` = %s
                              WHERE `command_id` = %s AND `command_batch` = %s''',
                           (status, json.dumps(outcome), command_finish.id, self.batch_id))
            cursor.execute('''UPDATE `batch`
                              SET `batch_last_updated_utc_timestamp` = %s
                              WHERE `batch_id` = %s''', (last_updated_utc_timestamp, self.batch_id))
            connection.commit()

            if isinstance(command_finish, CommandFailure) and \
               command_finish.can_retry_later():
                # append a fresh plan for the same command
                cursor.execute('''INSERT INTO `command`
                                  (`command_batch`, `command_page`, `command_actions_id`, `command_status`, `command_outcome`)
                                  SELECT `command_batch`, `command_page`, `command_actions_id`, %s, NULL
                                  FROM `command`
                                  WHERE `command_id` = %s''',
                               (DatabaseStore._COMMAND_STATUS_PLAN, command_finish.id))
                command_plan_id = cursor.lastrowid
                cursor.execute('''INSERT INTO `retry`
                                  (`retry_failure`, `retry_new`)
                                  VALUES (%s, %s)''',
                               (command_finish.id, command_plan_id))
                connection.commit()
            else:
                # close the batch if no planned or pending commands are left in it
                cursor.execute('''SELECT 1
                                  FROM `command`
                                  WHERE `command_batch` = %s
                                  AND `command_status` IN (%s, %s)
                                  LIMIT 1''',
                               (self.batch_id, DatabaseStore._COMMAND_STATUS_PLAN, DatabaseStore._COMMAND_STATUS_PENDING))
                if not cursor.fetchone():
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


class _BatchBackgroundRunsDatabase(BatchBackgroundRuns):

    def __init__(self, batch_id: int, domain: str, store: DatabaseStore):
        self.batch_id = batch_id
        self.domain = domain
        self.store = store

    def currently_running(self) -> bool:
        with self.store._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''SELECT 1
                              FROM `background`
                              WHERE `background_batch` = %s
                              AND `background_stopped_utc_timestamp` IS NULL
                              LIMIT 1''',
                           (self.batch_id,))
            return cursor.fetchone() is not None

    def _row_to_background_run(self,
                               started_utc_timestamp: int, started_user_name: str, started_local_user_id: int, started_global_user_id: int,
                               stopped_utc_timestamp: int, stopped_user_name: str, stopped_local_user_id: int, stopped_global_user_id: int) \
                               -> Tuple[Tuple[datetime.datetime, LocalUser], Optional[Tuple[datetime.datetime, Optional[LocalUser]]]]:
        background_start = (self.store._utc_timestamp_to_datetime(started_utc_timestamp), LocalUser(started_user_name, self.domain, started_local_user_id, started_global_user_id))
        if stopped_utc_timestamp:
            if stopped_user_name:
                stopped_local_user = LocalUser(stopped_user_name, self.domain, stopped_local_user_id, stopped_global_user_id) # type: Optional[LocalUser]
            else:
                stopped_local_user = None
            background_stop = (self.store._utc_timestamp_to_datetime(stopped_utc_timestamp), stopped_local_user) # type: Optional[Tuple[datetime.datetime, Optional[LocalUser]]]
        else:
            background_stop = None
        return (background_start, background_stop)

    def get_last(self) -> Optional[Tuple[Tuple[datetime.datetime, LocalUser], Optional[Tuple[datetime.datetime, Optional[LocalUser]]]]]:
        with self.store._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''SELECT `background_started_utc_timestamp`, `started`.`localuser_user_name`, `started`.`localuser_local_user_id`, `started`.`localuser_global_user_id`, `background_stopped_utc_timestamp`, `stopped`.`localuser_user_name`, `stopped`.`localuser_local_user_id`, `stopped`.`localuser_global_user_id`
                              FROM `background`
                              JOIN `localuser` AS `started` ON `background_started_localuser_id` = `started`.`localuser_id`
                              LEFT JOIN `localuser` AS `stopped` ON `background_stopped_localuser_id` = `stopped`.`localuser_id`
                              WHERE `background_batch` = %s
                              ORDER BY `background_id` DESC
                              LIMIT 1''',
                           (self.batch_id,))
            result = cursor.fetchone()
            if result:
                return self._row_to_background_run(*result)
            else:
                return None

    def get_all(self) -> Sequence[Tuple[Tuple[datetime.datetime, LocalUser], Optional[Tuple[datetime.datetime, Optional[LocalUser]]]]]:
        with self.store._connect() as connection, connection.cursor() as cursor:
            cursor.execute('''SELECT `background_started_utc_timestamp`, `started`.`localuser_user_name`, `started`.`localuser_local_user_id`, `started`.`localuser_global_user_id`, `background_stopped_utc_timestamp`, `stopped`.`localuser_user_name`, `stopped`.`localuser_local_user_id`, `stopped`.`localuser_global_user_id`
                              FROM `background`
                              JOIN `localuser` AS `started` ON `background_started_localuser_id` = `started`.`localuser_id`
                              LEFT JOIN `localuser` AS `stopped` ON `background_stopped_localuser_id` = `stopped`.`localuser_id`
                              WHERE `background_batch` = %s
                              ORDER BY `background_id` ASC''',
                           (self.batch_id,))
            return [self._row_to_background_run(*row) for row in cursor.fetchall()]

    def __eq__(self, value: Any) -> bool:
        # limited test to avoid overly expensive full comparison
        return type(value) is _BatchBackgroundRunsDatabase and \
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


class _LocalUserStore:
    """Encapsulates access to a local user account in the localuser table.

       When a user has been renamed, the same ID will still be used
       and the name will be updated once the user is stored the next time."""

    def __init__(self, domain_store: _StringTableStore):
        self.domain_store = domain_store

    def acquire_localuser_id(self, connection: pymysql.connections.Connection, local_user: LocalUser) -> int:
        domain_id = self.domain_store.acquire_id(connection, local_user.domain)

        with connection.cursor() as cursor:
            cursor.execute('''INSERT INTO `localuser`
                              (`localuser_user_name`, `localuser_domain_id`, `localuser_local_user_id`, `localuser_global_user_id`)
                              VALUES (%s, %s, %s, %s)
                              ON DUPLICATE KEY UPDATE `localuser_user_name` = %s''',
                           (local_user.user_name, domain_id, local_user.local_user_id, local_user.global_user_id,
                            local_user.user_name))
            localuser_id = cursor.lastrowid
            if not localuser_id: # not returned in the ON DUPLICATE KEY UPDATE case, apparently
                cursor.execute('''SELECT `localuser_id`
                                  FROM `localuser`
                                  WHERE `localuser_local_user_id` = %s
                                  AND `localuser_domain_id` = %s''',
                               (local_user.local_user_id, domain_id))
                (localuser_id,) = cursor.fetchone()
                assert cursor.fetchone() is None
        connection.commit()
        return localuser_id

from collections.abc import Generator, Iterator, Sequence
import contextlib
from dataclasses import dataclass
import datetime
import flask
import itertools
import json
import mwapi  # type: ignore
import mwoauth  # type: ignore
import pymysql
import requests_oauthlib  # type: ignore
from typing import Any, Optional, cast

from batch import NewBatch, StoredBatch, OpenBatch, ClosedBatch, BatchCommandRecords, BatchBackgroundRuns
from command import Command, CommandPlan, CommandPending, CommandRecord, CommandFinish, CommandEdit, CommandNoop, CommandFailure, CommandPageMissing, CommandTitleInvalid, CommandTitleInterwiki, CommandPageProtected, CommandPageBadContentFormat, CommandPageBadContentModel, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
from localuser import LocalUser
from page import Page
import parse_tpsv
from querytime import QueryTimingCursor, QueryTimingSSCursor
from store import BatchStore, PreferenceStore, WatchlistParam, _local_user_from_session
from stringstore import StringTableStore
from timestamp import now, datetime_to_utc_timestamp, utc_timestamp_to_datetime


class DatabaseBatchStore(BatchStore):

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
    _COMMAND_STATUS_TITLE_INVALID = 135
    _COMMAND_STATUS_TITLE_INTERWIKI = 136
    _COMMAND_STATUS_PAGE_BAD_CONTENT_FORMAT = 137
    _COMMAND_STATUS_PAGE_BAD_CONTENT_MODEL = 138

    def __init__(self, connection_params: dict, app: Optional[flask.Flask] = None) -> None:
        connection_params.setdefault('charset', 'utf8mb4')
        if connection_params.pop('enable_querytime', False):
            self.connection_params = {
                'cursorclass': cast(type[pymysql.cursors.Cursor], QueryTimingCursor),
                **connection_params,
            }
            self.streaming_connection_params = {
                'cursorclass': cast(type[pymysql.cursors.SSCursor], QueryTimingSSCursor),
                **connection_params,
            }
        else:
            self.connection_params = {
                'cursorclass': pymysql.cursors.Cursor,
                **connection_params,
            }
            self.streaming_connection_params = {
                'cursorclass': pymysql.cursors.SSCursor,
                **connection_params,
            }
        self.app = app
        if app is not None:
            @app.teardown_appcontext
            def teardown_connection(exception: Optional[BaseException]) -> None:
                connection = flask.g.pop('database_connection', None)
                if connection is not None:
                    connection.close()
        self.domain_store = StringTableStore('domain', 'domain_id', 'domain_hash', 'domain_name')
        self.title_store = StringTableStore('title', 'title_id', 'title_hash', 'title_text')
        self.actions_store = StringTableStore('actions', 'actions_id', 'actions_hash', 'actions_tpsv')
        self.local_user_store = _LocalUserStore(self.domain_store)

    @contextlib.contextmanager
    def connect(self) -> Generator[pymysql.connections.Connection, None, None]:
        if self.app is not None:
            if 'database_connection' not in flask.g:
                flask.g.database_connection = self._connect()
            yield flask.g.database_connection
        else:
            connection = self._connect()
            try:
                yield connection
            finally:
                connection.close()

    def _connect(self) -> pymysql.connections.Connection:
        return pymysql.connect(**self.connection_params)

    @contextlib.contextmanager
    def connect_streaming(self) -> Generator[pymysql.connections.Connection, None, None]:
        connection = pymysql.connect(**self.streaming_connection_params)
        try:
            yield connection
        finally:
            connection.close()

    def store_batch(self, new_batch: NewBatch, session: mwapi.Session) -> OpenBatch:
        created = now()
        created_utc_timestamp = datetime_to_utc_timestamp(created)
        local_user = _local_user_from_session(session)

        with self.connect() as connection:
            domain_id = self.domain_store.acquire_id(connection, local_user.domain)
            if new_batch.title:
                title_id = self.title_store.acquire_id(connection, new_batch.title)
            else:
                title_id = None
            localuser_id = self.local_user_store.acquire_localuser_id(connection, local_user)
            with connection.cursor() as cursor:
                cursor.execute('INSERT INTO `batch` (`batch_localuser`, `batch_domain`, `batch_title`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`) VALUES (%s, %s, %s, %s, %s, %s)',
                               (localuser_id, domain_id, title_id, created_utc_timestamp, created_utc_timestamp, DatabaseBatchStore._BATCH_STATUS_OPEN))
                batch_id = cursor.lastrowid

            with connection.cursor() as cursor:
                cursor.executemany('INSERT INTO `command` (`command_batch`, `command_page_title`, `command_page_resolve_redirects`, `command_actions`, `command_status`, `command_outcome`) VALUES (%s, %s, %s, %s, %s, NULL)',
                                   [(batch_id, command.page.title, command.page.resolve_redirects, self.actions_store.acquire_id(connection, command.actions_tpsv()), DatabaseBatchStore._COMMAND_STATUS_PLAN) for command in new_batch.commands])

            connection.commit()

        return OpenBatch(batch_id,
                         local_user,
                         local_user.domain,
                         new_batch.title,
                         created,
                         created,
                         _BatchCommandRecordsDatabase(batch_id, self),
                         _BatchBackgroundRunsDatabase(batch_id, local_user.domain, self))

    def get_batch(self, id: int) -> Optional[StoredBatch]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `batch_id`, `localuser_user_name`, `localuser_local_user_id`, `localuser_global_user_id`, `domain_name`, `title_text`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`
                                  FROM `batch`
                                  JOIN `domain` ON `batch_domain` = `domain_id`
                                  JOIN `localuser` ON `batch_localuser` = `localuser_id`
                                  LEFT JOIN `title` ON `batch_title` = `title_id`
                                  WHERE `batch_id` = %s''', (id,))
                result = cursor.fetchone()
        if not result:
            return None
        return self._result_to_batch(result)

    def _result_to_batch(self, result: tuple) -> StoredBatch:
        id, user_name, local_user_id, global_user_id, domain, title, created_utc_timestamp, last_updated_utc_timestamp, status = result
        created = utc_timestamp_to_datetime(created_utc_timestamp)
        last_updated = utc_timestamp_to_datetime(last_updated_utc_timestamp)
        local_user = LocalUser(user_name, domain, local_user_id, global_user_id)
        if status == DatabaseBatchStore._BATCH_STATUS_OPEN:
            return OpenBatch(id,
                             local_user,
                             local_user.domain,
                             title,
                             created,
                             last_updated,
                             _BatchCommandRecordsDatabase(id, self),
                             _BatchBackgroundRunsDatabase(id, local_user.domain, self))
        elif status == DatabaseBatchStore._BATCH_STATUS_CLOSED:
            return ClosedBatch(id,
                               local_user,
                               local_user.domain,
                               title,
                               created,
                               last_updated,
                               _BatchCommandRecordsDatabase(id, self),
                               _BatchBackgroundRunsDatabase(id, local_user.domain, self))
        else:
            raise ValueError('Unknown batch type')

    def get_batches_slice(self, offset: int, limit: int) -> Sequence[StoredBatch]:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `batch_id`, `localuser_user_name`, `localuser_local_user_id`, `localuser_global_user_id`, `domain_name`, `title_text`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`
                                  FROM `batch`
                                  JOIN `domain` ON `batch_domain` = `domain_id`
                                  JOIN `localuser` ON `batch_localuser` = `localuser_id`
                                  LEFT JOIN `title` ON `batch_title` = `title_id`
                                  ORDER BY `batch_id` DESC
                                  LIMIT %s
                                  OFFSET %s''',
                               (limit, offset))
                return [self._result_to_batch(result) for result in cursor.fetchall()]

    def get_batches_count(self) -> int:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT COUNT(*) AS `count`
                                  FROM `batch`''')
                result = cursor.fetchone()
                assert result, "COUNT(*) must return a result"
                (count,) = result
        return count

    def start_background(self, batch: OpenBatch, session: mwapi.Session) -> None:
        started = now()
        started_utc_timestamp = datetime_to_utc_timestamp(started)
        local_user = _local_user_from_session(session)

        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT 1
                                  FROM `background`
                                  WHERE `background_batch` = %s
                                  AND `background_stopped_utc_timestamp` IS NULL
                                  FOR UPDATE''',
                               (batch.id,))
                if cursor.fetchone():
                    connection.commit()  # finish the FOR UPDATE
                    return

            assert isinstance(session.session.auth, requests_oauthlib.OAuth1)
            auth = {'resource_owner_key': session.session.auth.client.resource_owner_key,
                    'resource_owner_secret': session.session.auth.client.resource_owner_secret}

            localuser_id = self.local_user_store.acquire_localuser_id(connection, local_user)

            with connection.cursor() as cursor:
                cursor.execute('''INSERT INTO `background`
                                  (`background_batch`, `background_auth`, `background_started_utc_timestamp`, `background_started_localuser`)
                                  VALUES (%s, %s, %s, %s)''',
                               (batch.id, json.dumps(auth), started_utc_timestamp, localuser_id))
            connection.commit()

    def stop_background(self, batch: StoredBatch, session: Optional[mwapi.Session] = None) -> None:
        self._stop_background_by_id(batch.id, session)

    def _stop_background_by_id(self, batch_id: int, session: Optional[mwapi.Session] = None) -> None:
        stopped = now()
        stopped_utc_timestamp = datetime_to_utc_timestamp(stopped)
        with self.connect() as connection:
            localuser_id: Optional[int]
            if session:
                local_user = _local_user_from_session(session)
                localuser_id = self.local_user_store.acquire_localuser_id(connection, local_user)
            else:
                localuser_id = None
            with connection.cursor() as cursor:
                cursor.execute('''UPDATE `background`
                                  SET `background_auth` = NULL, `background_stopped_utc_timestamp` = %s, `background_stopped_localuser` = %s, `background_suspended_until_utc_timestamp` = NULL
                                  WHERE `background_batch` = %s
                                  AND `background_stopped_utc_timestamp` IS NULL''',
                               (stopped_utc_timestamp, localuser_id, batch_id))
            connection.commit()
            if cursor.rowcount > 1:
                raise RuntimeError('Should have stopped at most 1 background operation, actually affected %d!' % cursor.rowcount)

    def suspend_background(self, batch: StoredBatch, until: datetime.datetime) -> None:
        until_utc_timestamp = datetime_to_utc_timestamp(until)
        with self.connect() as connection, connection.cursor() as cursor:
            cursor.execute('''UPDATE `background`
                              SET `background_suspended_until_utc_timestamp` = %s
                              WHERE `background_batch` = %s
                              AND `background_stopped_utc_timestamp` IS NULL''',
                           (until_utc_timestamp, batch.id))
            connection.commit()
            if cursor.rowcount > 1:
                raise RuntimeError('Should have suspended at most 1 background run, actually affected %d!' % cursor.rowcount)

    def make_plan_pending_background(self, consumer_token: mwoauth.ConsumerToken, user_agent: str) -> Optional[tuple[OpenBatch, CommandPending, mwapi.Session]]:
        with self.connect() as connection:
            # find a planned command and lock it
            with connection.cursor() as cursor:
                now_utc_timestamp = datetime_to_utc_timestamp(now())
                cursor.execute('''SELECT `command_id`, `batch_id`
                                  FROM `background`
                                  JOIN `batch` ON `background_batch` = `batch_id`
                                  JOIN `command` ON `command_batch` = `batch_id`
                                  WHERE `background_stopped_utc_timestamp` IS NULL
                                  AND COALESCE(`background_suspended_until_utc_timestamp`, 0) < %s
                                  AND `command_status` = %s
                                  ORDER BY `batch_last_updated_utc_timestamp` ASC, `command_id` ASC
                                  LIMIT 1
                                  FOR UPDATE''',
                               (now_utc_timestamp, DatabaseBatchStore._COMMAND_STATUS_PLAN))
                result = cursor.fetchone()
            if not result:
                connection.commit()  # finish the FOR UPDATE
                return None

            command_id = result[0]
            batch_id = result[1]

            # make it pending
            with connection.cursor() as cursor:
                cursor.execute('''UPDATE `command`
                                  SET `command_status` = %s
                                  WHERE `command_id` = %s AND `command_batch` = %s''',
                               (DatabaseBatchStore._COMMAND_STATUS_PENDING, command_id, batch_id))
            connection.commit()

            # get the rest of the data now that we know we need it (without locking it)
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `batch_id`, `localuser_user_name`, `localuser_local_user_id`, `localuser_global_user_id`, `domain_name`, `title_text`, `batch_created_utc_timestamp`, `batch_last_updated_utc_timestamp`, `batch_status`, `background_auth`, `command_id`, `command_page_title`, `command_page_resolve_redirects`, `actions_tpsv`
                                  FROM `background`
                                  JOIN `batch` ON `background_batch` = `batch_id`
                                  JOIN `command` ON `command_batch` = `batch_id`
                                  JOIN `domain` ON `batch_domain` = `domain_id`
                                  JOIN `actions` ON `command_actions` = `actions_id`
                                  JOIN `localuser` ON `batch_localuser` = `localuser_id`
                                  LEFT JOIN `title` ON `batch_title` = `title_id`
                                  WHERE `command_id` = %s
                                  AND `background_stopped_utc_timestamp` IS NULL
                                  AND COALESCE(`background_suspended_until_utc_timestamp`, 0) < %s''',
                               (command_id, now_utc_timestamp))
                assert cursor.rowcount == 1
                result = cursor.fetchone()
                assert result is not None

        auth_data = json.loads(result[9])
        auth = requests_oauthlib.OAuth1(client_key=consumer_token.key, client_secret=consumer_token.secret,
                                        resource_owner_key=auth_data['resource_owner_key'], resource_owner_secret=auth_data['resource_owner_secret'])
        session = mwapi.Session(host='https://'+result[4], auth=auth, user_agent=user_agent)
        command_pending = self._row_to_command_record(result[10],
                                                      result[11],
                                                      result[12],
                                                      result[13],
                                                      DatabaseBatchStore._COMMAND_STATUS_PENDING,
                                                      outcome=None)
        batch = self._result_to_batch(result[0:9])

        assert isinstance(batch, OpenBatch), "must be open since at least one command is still pending"
        assert isinstance(command_pending, CommandPending), "must be pending since we just set that status"
        return batch, command_pending, session

    def _command_finish_to_row(self, command_finish: CommandFinish) -> tuple[int, dict]:
        status: int
        outcome: dict
        if isinstance(command_finish, CommandEdit):
            status = DatabaseBatchStore._COMMAND_STATUS_EDIT
            outcome = {'base_revision': command_finish.base_revision, 'revision': command_finish.revision}
        elif isinstance(command_finish, CommandNoop):
            status = DatabaseBatchStore._COMMAND_STATUS_NOOP
            outcome = {'revision': command_finish.revision}
        elif isinstance(command_finish, CommandPageMissing):
            status = DatabaseBatchStore._COMMAND_STATUS_PAGE_MISSING
            outcome = {'curtimestamp': command_finish.curtimestamp}
        elif isinstance(command_finish, CommandTitleInvalid):
            status = DatabaseBatchStore._COMMAND_STATUS_TITLE_INVALID
            outcome = {'curtimestamp': command_finish.curtimestamp}
        elif isinstance(command_finish, CommandTitleInterwiki):
            status = DatabaseBatchStore._COMMAND_STATUS_TITLE_INTERWIKI
            outcome = {'curtimestamp': command_finish.curtimestamp}
        elif isinstance(command_finish, CommandPageProtected):
            status = DatabaseBatchStore._COMMAND_STATUS_PAGE_PROTECTED
            outcome = {'curtimestamp': command_finish.curtimestamp}
        elif isinstance(command_finish, CommandPageBadContentFormat):
            status = DatabaseBatchStore._COMMAND_STATUS_PAGE_BAD_CONTENT_FORMAT
            outcome = {
                'content_format': command_finish.content_format,
                'content_model': command_finish.content_model,
                'revision': command_finish.revision,
            }
        elif isinstance(command_finish, CommandPageBadContentModel):
            status = DatabaseBatchStore._COMMAND_STATUS_PAGE_BAD_CONTENT_MODEL
            outcome = {
                'content_format': command_finish.content_format,
                'content_model': command_finish.content_model,
                'revision': command_finish.revision,
            }
        elif isinstance(command_finish, CommandEditConflict):
            status = DatabaseBatchStore._COMMAND_STATUS_EDIT_CONFLICT
            outcome = {}
        elif isinstance(command_finish, CommandMaxlagExceeded):
            status = DatabaseBatchStore._COMMAND_STATUS_MAXLAG_EXCEEDED
            outcome = {'retry_after_utc_timestamp': datetime_to_utc_timestamp(command_finish.retry_after)}
        elif isinstance(command_finish, CommandBlocked):
            status = DatabaseBatchStore._COMMAND_STATUS_BLOCKED
            outcome = {'auto': command_finish.auto, 'blockinfo': command_finish.blockinfo}
        elif isinstance(command_finish, CommandWikiReadOnly):
            status = DatabaseBatchStore._COMMAND_STATUS_WIKI_READ_ONLY
            outcome = {'reason': command_finish.reason}
            if command_finish.retry_after:
                outcome['retry_after_utc_timestamp'] = datetime_to_utc_timestamp(command_finish.retry_after)
        else:
            raise ValueError('Unknown command type')

        return status, outcome

    def _row_to_page(self, title: str, resolve_redirects: Optional[int]) -> Page:
        return Page(title, self._tinyint_to_bool(resolve_redirects))

    def _row_to_command(self, title: str, resolve_redirects: Optional[int], actions_tpsv: str) -> Command:
        return Command(self._row_to_page(title, self._tinyint_to_bool(resolve_redirects)),
                       [parse_tpsv.parse_action(field) for field in actions_tpsv.split('|')])

    def _row_to_command_record(self, id: int, title: str, resolve_redirects: Optional[int], actions_tpsv: str, status: int, outcome: Optional[str]) -> CommandRecord:
        if outcome:
            outcome_dict = json.loads(outcome)

        command = self._row_to_command(title, resolve_redirects, actions_tpsv)

        if status == DatabaseBatchStore._COMMAND_STATUS_PLAN:
            assert outcome is None
            return CommandPlan(id, command)
        elif status == DatabaseBatchStore._COMMAND_STATUS_EDIT:
            return CommandEdit(id,
                               command,
                               base_revision=outcome_dict['base_revision'],
                               revision=outcome_dict['revision'])
        elif status == DatabaseBatchStore._COMMAND_STATUS_NOOP:
            return CommandNoop(id,
                               command,
                               revision=outcome_dict['revision'])
        elif status == DatabaseBatchStore._COMMAND_STATUS_PENDING:
            assert outcome is None
            return CommandPending(id, command)
        elif status == DatabaseBatchStore._COMMAND_STATUS_PAGE_MISSING:
            return CommandPageMissing(id,
                                      command,
                                      curtimestamp=outcome_dict['curtimestamp'])
        elif status == DatabaseBatchStore._COMMAND_STATUS_TITLE_INVALID:
            return CommandTitleInvalid(id,
                                       command,
                                       curtimestamp=outcome_dict['curtimestamp'])
        elif status == DatabaseBatchStore._COMMAND_STATUS_TITLE_INTERWIKI:
            return CommandTitleInterwiki(id,
                                         command,
                                         curtimestamp=outcome_dict['curtimestamp'])
        elif status == DatabaseBatchStore._COMMAND_STATUS_PAGE_PROTECTED:
            return CommandPageProtected(id,
                                        command,
                                        curtimestamp=outcome_dict['curtimestamp'])
        elif status == DatabaseBatchStore._COMMAND_STATUS_PAGE_BAD_CONTENT_FORMAT:
            return CommandPageBadContentFormat(id,
                                               command,
                                               content_format=outcome_dict['content_format'],
                                               content_model=outcome_dict['content_model'],
                                               revision=outcome_dict['revision'])
        elif status == DatabaseBatchStore._COMMAND_STATUS_PAGE_BAD_CONTENT_MODEL:
            return CommandPageBadContentModel(id,
                                              command,
                                              content_format=outcome_dict['content_format'],
                                              content_model=outcome_dict['content_model'],
                                              revision=outcome_dict['revision'])
        elif status == DatabaseBatchStore._COMMAND_STATUS_EDIT_CONFLICT:
            return CommandEditConflict(id,
                                       command)
        elif status == DatabaseBatchStore._COMMAND_STATUS_MAXLAG_EXCEEDED:
            return CommandMaxlagExceeded(id,
                                         command,
                                         utc_timestamp_to_datetime(outcome_dict['retry_after_utc_timestamp']))
        elif status == DatabaseBatchStore._COMMAND_STATUS_BLOCKED:
            return CommandBlocked(id,
                                  command,
                                  auto=outcome_dict['auto'],
                                  blockinfo=outcome_dict['blockinfo'])
        elif status == DatabaseBatchStore._COMMAND_STATUS_WIKI_READ_ONLY:
            retry_after: Optional[datetime.datetime]
            if 'retry_after_utc_timestamp' in outcome_dict:
                retry_after = utc_timestamp_to_datetime(outcome_dict['retry_after_utc_timestamp'])
            else:
                retry_after = None
            return CommandWikiReadOnly(id,
                                       command,
                                       outcome_dict['reason'],
                                       retry_after)
        else:
            raise ValueError('Unknown command status %d' % status)

    def _status_to_command_record_type(self, status: int) -> type[CommandRecord]:
        if status == DatabaseBatchStore._COMMAND_STATUS_PLAN:
            return CommandPlan
        elif status == DatabaseBatchStore._COMMAND_STATUS_EDIT:
            return CommandEdit
        elif status == DatabaseBatchStore._COMMAND_STATUS_NOOP:
            return CommandNoop
        elif status == DatabaseBatchStore._COMMAND_STATUS_PENDING:
            return CommandPending
        elif status == DatabaseBatchStore._COMMAND_STATUS_PAGE_MISSING:
            return CommandPageMissing
        elif status == DatabaseBatchStore._COMMAND_STATUS_TITLE_INVALID:
            return CommandTitleInvalid
        elif status == DatabaseBatchStore._COMMAND_STATUS_TITLE_INTERWIKI:
            return CommandTitleInterwiki
        elif status == DatabaseBatchStore._COMMAND_STATUS_PAGE_PROTECTED:
            return CommandPageProtected
        elif status == DatabaseBatchStore._COMMAND_STATUS_PAGE_BAD_CONTENT_FORMAT:
            return CommandPageBadContentFormat
        elif status == DatabaseBatchStore._COMMAND_STATUS_PAGE_BAD_CONTENT_MODEL:
            return CommandPageBadContentModel
        elif status == DatabaseBatchStore._COMMAND_STATUS_EDIT_CONFLICT:
            return CommandEditConflict
        elif status == DatabaseBatchStore._COMMAND_STATUS_MAXLAG_EXCEEDED:
            return CommandMaxlagExceeded
        elif status == DatabaseBatchStore._COMMAND_STATUS_BLOCKED:
            return CommandBlocked
        elif status == DatabaseBatchStore._COMMAND_STATUS_WIKI_READ_ONLY:
            return CommandWikiReadOnly
        else:
            raise ValueError('Unknown command status %d' % status)

    def _tinyint_to_bool(self, val: Optional[int]) -> Optional[bool]:
        if val is None:
            return None
        else:
            return bool(val)


@dataclass(frozen=True)
class _BatchCommandRecordsDatabase(BatchCommandRecords):

    batch_id: int
    store: DatabaseBatchStore

    def get_slice(self, offset: int, limit: int) -> list[CommandRecord]:
        command_records = []
        with self.store.connect() as connection, connection.cursor() as cursor:
            cursor.execute('''SELECT `command_id`, `command_page_title`, `command_page_resolve_redirects`, `actions_tpsv`, `command_status`, `command_outcome`
                              FROM `command`
                              JOIN `actions` ON `command_actions` = `actions_id`
                              WHERE `command_batch` = %s
                              ORDER BY `command_id` ASC
                              LIMIT %s OFFSET %s''', (self.batch_id, limit, offset))
            for id, title, resolve_redirects, actions_tpsv, status, outcome in cursor.fetchall():
                command_records.append(self.store._row_to_command_record(id, title, resolve_redirects, actions_tpsv, status, outcome))
        return command_records

    def get_summary(self) -> dict[type[CommandRecord], int]:
        with self.store.connect() as connection, connection.cursor() as cursor:
            cursor.execute('''SELECT `command_status`, COUNT(*) AS `count`
                              FROM `command`
                              WHERE `command_batch` = %s
                              GROUP BY `command_status`''',
                           (self.batch_id,))
            return {self.store._status_to_command_record_type(status): count for status, count in cursor.fetchall()}

    def stream_pages(self) -> Iterator[Page]:
        with self.store.connect_streaming() as connection, cast(pymysql.cursors.SSCursor, connection.cursor()) as cursor:
            cursor.execute('''SELECT `command_page_title`, `command_page_resolve_redirects`
                              FROM `command`
                              WHERE `command_batch` = %s
                              ORDER BY `command_id` ASC''',
                           (self.batch_id,))
            for title, resolve_redirects in cursor.fetchall_unbuffered():
                yield self.store._row_to_page(title, resolve_redirects)

    def stream_commands(self) -> Iterator[Command]:
        with self.store.connect_streaming() as connection, cast(pymysql.cursors.SSCursor, connection.cursor()) as cursor:
            cursor.execute('''SELECT `command_page_title`, `command_page_resolve_redirects`, `actions_tpsv`
                              FROM `command`
                              JOIN `actions` ON `command_actions` = `actions_id`
                              WHERE `command_batch` = %s
                              ORDER BY `command_id` ASC''',
                           (self.batch_id,))
            for title, resolve_redirects, actions_tpsv in cursor.fetchall_unbuffered():
                yield self.store._row_to_command(title, resolve_redirects, actions_tpsv)

    def __len__(self) -> int:
        with self.store.connect() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM `command` WHERE `command_batch` = %s', (self.batch_id,))
            result = cursor.fetchone()
            assert result, "COUNT(*) must return a result"
            (count,) = result
        return count

    def make_plans_pending(self, offset: int, limit: int) -> list[CommandPending]:
        with self.store.connect() as connection:
            command_ids: list[int] = []

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
                                  FOR UPDATE''', (self.batch_id, limit, offset, DatabaseBatchStore._COMMAND_STATUS_PLAN))
                for (command_id,) in cursor.fetchall():
                    command_ids.append(command_id)

            if not command_ids:
                connection.commit()  # finish the FOR UPDATE
                return []

            with connection.cursor() as cursor:
                cursor.executemany('''UPDATE `command`
                                      SET `command_status` = %s
                                      WHERE `command_id` = %s AND `command_batch` = %s''',
                                   zip(itertools.repeat(DatabaseBatchStore._COMMAND_STATUS_PENDING),
                                       command_ids,
                                       itertools.repeat(self.batch_id)))
            connection.commit()

            command_records = []
            with connection.cursor() as cursor:
                cursor.execute('''SELECT `command_id`, `command_page_title`, `command_page_resolve_redirects`, `actions_tpsv`, `command_status`, `command_outcome`
                                  FROM `command`
                                  JOIN `actions` ON `command_actions` = `actions_id`
                                  WHERE `command_id` IN (%s)''' % ', '.join(['%s'] * len(command_ids)),
                               command_ids)
            for id, title, resolve_redirects, actions_tpsv, status, outcome in cursor.fetchall():
                assert status == DatabaseBatchStore._COMMAND_STATUS_PENDING
                assert outcome is None
                command_record = self.store._row_to_command_record(id, title, resolve_redirects, actions_tpsv, status, outcome)
                assert isinstance(command_record, CommandPending)
                command_records.append(command_record)
        return command_records

    def make_pendings_planned(self, command_record_ids: list[int]) -> None:
        if not command_record_ids:
            return

        with self.store.connect() as connection, connection.cursor() as cursor:
            cursor.execute('''UPDATE `command`
                              SET `command_status` = %%s
                              WHERE `command_id` IN (%s)
                              AND `command_status` = %%s''' % ', '.join(['%s'] * len(command_record_ids)),
                           [DatabaseBatchStore._COMMAND_STATUS_PLAN,
                            *command_record_ids,
                            DatabaseBatchStore._COMMAND_STATUS_PENDING])
            connection.commit()

    def store_finish(self, command_finish: CommandFinish) -> None:
        last_updated = now()
        last_updated_utc_timestamp = datetime_to_utc_timestamp(last_updated)
        status, outcome = self.store._command_finish_to_row(command_finish)

        with self.store.connect() as connection, connection.cursor() as cursor:
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
                                  (`command_batch`, `command_page_title`, `command_page_resolve_redirects`, `command_actions`, `command_status`, `command_outcome`)
                                  SELECT `command_batch`, `command_page_title`, `command_page_resolve_redirects`, `command_actions`, %s, NULL
                                  FROM `command`
                                  WHERE `command_id` = %s''',
                               (DatabaseBatchStore._COMMAND_STATUS_PLAN, command_finish.id))
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
                               (self.batch_id, DatabaseBatchStore._COMMAND_STATUS_PLAN, DatabaseBatchStore._COMMAND_STATUS_PENDING))
                if not cursor.fetchone():
                    cursor.execute('''UPDATE `batch`
                                      SET `batch_status` = %s
                                      WHERE `batch_id` = %s''',
                                   (DatabaseBatchStore._BATCH_STATUS_CLOSED, self.batch_id))
                    connection.commit()
                    self.store._stop_background_by_id(self.batch_id)

    def __eq__(self, value: Any) -> bool:
        # limited test to avoid overly expensive full comparison
        return type(value) is _BatchCommandRecordsDatabase and \
            self.batch_id == value.batch_id


@dataclass(frozen=True)
class _BatchBackgroundRunsDatabase(BatchBackgroundRuns):

    batch_id: int
    domain: str
    store: DatabaseBatchStore

    def currently_running(self) -> bool:
        with self.store.connect() as connection, connection.cursor() as cursor:
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
                               -> tuple[tuple[datetime.datetime, LocalUser], Optional[tuple[datetime.datetime, Optional[LocalUser]]]]:  # NOQA: E127 (indentation)
        background_start = (utc_timestamp_to_datetime(started_utc_timestamp), LocalUser(started_user_name, self.domain, started_local_user_id, started_global_user_id))
        background_stop: Optional[tuple[datetime.datetime, Optional[LocalUser]]]
        if stopped_utc_timestamp:
            stopped_local_user: Optional[LocalUser]
            if stopped_user_name:
                stopped_local_user = LocalUser(stopped_user_name, self.domain, stopped_local_user_id, stopped_global_user_id)
            else:
                stopped_local_user = None
            background_stop = (utc_timestamp_to_datetime(stopped_utc_timestamp), stopped_local_user)
        else:
            background_stop = None
        return (background_start, background_stop)

    def get_last(self) -> Optional[tuple[tuple[datetime.datetime, LocalUser], Optional[tuple[datetime.datetime, Optional[LocalUser]]]]]:
        with self.store.connect() as connection, connection.cursor() as cursor:
            cursor.execute('''SELECT `background_started_utc_timestamp`, `started`.`localuser_user_name`, `started`.`localuser_local_user_id`, `started`.`localuser_global_user_id`, `background_stopped_utc_timestamp`, `stopped`.`localuser_user_name`, `stopped`.`localuser_local_user_id`, `stopped`.`localuser_global_user_id`
                              FROM `background`
                              JOIN `localuser` AS `started` ON `background_started_localuser` = `started`.`localuser_id`
                              LEFT JOIN `localuser` AS `stopped` ON `background_stopped_localuser` = `stopped`.`localuser_id`
                              WHERE `background_batch` = %s
                              ORDER BY `background_id` DESC
                              LIMIT 1''',
                           (self.batch_id,))
            result = cursor.fetchone()
            if result:
                return self._row_to_background_run(*result)
            else:
                return None

    def get_all(self) -> Sequence[tuple[tuple[datetime.datetime, LocalUser], Optional[tuple[datetime.datetime, Optional[LocalUser]]]]]:
        with self.store.connect() as connection, connection.cursor() as cursor:
            cursor.execute('''SELECT `background_started_utc_timestamp`, `started`.`localuser_user_name`, `started`.`localuser_local_user_id`, `started`.`localuser_global_user_id`, `background_stopped_utc_timestamp`, `stopped`.`localuser_user_name`, `stopped`.`localuser_local_user_id`, `stopped`.`localuser_global_user_id`
                              FROM `background`
                              JOIN `localuser` AS `started` ON `background_started_localuser` = `started`.`localuser_id`
                              LEFT JOIN `localuser` AS `stopped` ON `background_stopped_localuser` = `stopped`.`localuser_id`
                              WHERE `background_batch` = %s
                              ORDER BY `background_id` ASC''',
                           (self.batch_id,))
            return [self._row_to_background_run(*row) for row in cursor.fetchall()]

    def __eq__(self, value: Any) -> bool:
        # limited test to avoid overly expensive full comparison
        return type(value) is _BatchBackgroundRunsDatabase and \
            self.batch_id == value.batch_id


@dataclass(frozen=True)
class _LocalUserStore:
    """Encapsulates access to a local user account in the localuser table.

       When a user has been renamed, the same ID will still be used
       and the name will be updated once the user is stored the next time."""

    domain_store: StringTableStore

    def acquire_localuser_id(self, connection: pymysql.connections.Connection, local_user: LocalUser) -> int:
        domain_id = self.domain_store.acquire_id(connection, local_user.domain)

        with connection.cursor() as cursor:
            cursor.execute('''INSERT INTO `localuser`
                              (`localuser_user_name`, `localuser_domain`, `localuser_local_user_id`, `localuser_global_user_id`)
                              VALUES (%s, %s, %s, %s)
                              ON DUPLICATE KEY UPDATE `localuser_user_name` = %s''',
                           (local_user.user_name, domain_id, local_user.local_user_id, local_user.global_user_id,
                            local_user.user_name))
            localuser_id = cursor.lastrowid
            if not localuser_id:  # not returned in the ON DUPLICATE KEY UPDATE case, apparently
                cursor.execute('''SELECT `localuser_id`
                                  FROM `localuser`
                                  WHERE `localuser_local_user_id` = %s
                                  AND `localuser_domain` = %s''',
                               (local_user.local_user_id, domain_id))
                result = cursor.fetchone()
                assert result, "COUNT(*) must return a result"
                (localuser_id,) = result
                assert cursor.fetchone() is None
        connection.commit()
        return localuser_id


class DatabasePreferenceStore(PreferenceStore):

    _PREFERENCE_WATCHLIST_PARAM = 0

    def __init__(self, store: DatabaseBatchStore) -> None:
        self.store = store  # to avoid duplicating connect()

    def get_watchlist_param(self, session: Optional[mwapi.Session]) -> Optional[WatchlistParam]:
        if session is None:
            return None
        local_user = _local_user_from_session(session)
        with self.store.connect() as connection, connection.cursor() as cursor:
            cursor.execute('''SELECT `preference_value`
                              FROM `preference`
                              WHERE `preference_global_user_id` = %s
                              AND `preference_key` = %s''',
                           (local_user.global_user_id, DatabasePreferenceStore._PREFERENCE_WATCHLIST_PARAM))
            result = cursor.fetchone()
            if result:
                return WatchlistParam(result[0])
            else:
                return None

    def set_watchlist_param(self, session: mwapi.Session, value: WatchlistParam) -> None:
        local_user = _local_user_from_session(session)
        with self.store.connect() as connection, connection.cursor() as cursor:
            cursor.execute('''INSERT INTO `preference`
                              (`preference_global_user_id`, `preference_key`, `preference_value`)
                              VALUES (%s, %s, %s)
                              ON DUPLICATE KEY UPDATE `preference_value` = %s''',
                           (local_user.global_user_id, DatabasePreferenceStore._PREFERENCE_WATCHLIST_PARAM, value.value, value.value))
            connection.commit()

import flask
import json
import pymysql
import pytest
from typing import Any, Optional, cast
from unittest.mock import Mock, patch

from batch import StoredBatch
from command import CommandEdit, CommandFinish, CommandNoop, CommandRecord
from database import DatabaseBatchStore, _LocalUserStore
from localuser import LocalUser
from stringstore import StringTableStore

from test_batch import newBatch1
from test_command import commandPlan1, commandPending1, commandEdit1, commandNoop1, commandPageMissing1, commandTitleInvalid1, commandPageProtected1, commandPageBadContentFormat, commandPageBadContentModel, commandEditConflict1, commandMaxlagExceeded1, commandBlocked1, blockinfo, commandBlocked2, commandWikiReadOnly1, commandWikiReadOnly2
from test_localuser import localUser1, localUser2
from test_utils import FakeSession


fake_session = FakeSession({
    'query': {
        'userinfo': {
            'id': 6198807,
            'name': 'Lucas Werkmeister',
            'centralids': {
                'CentralAuth': 46054761,
                'local': 6198807
            },
            'attachedlocal': {
                'CentralAuth': '',
                'local': ''
            }
        }
    }
})
fake_session.host = 'https://commons.wikimedia.org'


def test_DatabaseBatchStore_store_batch(database_connection_params: dict) -> None:
    store = DatabaseBatchStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    command2 = open_batch.command_records.get_slice(1, 1)[0]

    with store.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT `command_page_title`, `command_page_resolve_redirects`, `actions_tpsv` FROM `command` JOIN `actions` on `command_actions` = `actions_id` WHERE `command_id` = %s AND `command_batch` = %s', (command2.id, open_batch.id))
            command2_page_title, command2_page_resolve_redirects, command2_actions_tpsv = cast(tuple[Any, ...], cursor.fetchone())
            assert command2_page_title == command2.command.page.title
            assert command2_page_resolve_redirects == command2.command.page.resolve_redirects
            assert command2_actions_tpsv == command2.command.actions_tpsv()

def test_DatabaseBatchStore_update_batch(database_connection_params: dict, frozen_time: Any) -> None:
    store = DatabaseBatchStore(database_connection_params)
    stored_batch = store.store_batch(newBatch1, fake_session)
    loaded_batch = cast(StoredBatch, store.get_batch(stored_batch.id))

    [command_plan_1, command_plan_2] = loaded_batch.command_records.get_slice(0, 2)

    command_edit = CommandEdit(command_plan_1.id, command_plan_1.command, 1234, 1235)
    loaded_batch.command_records.store_finish(command_edit)
    command_edit_loaded = loaded_batch.command_records.get_slice(0, 1)[0]
    assert command_edit == command_edit_loaded

    command_noop = CommandNoop(command_plan_1.id, command_plan_1.command, 1234)
    frozen_time.tick()  # make sure that this update increases last_updated
    loaded_batch.command_records.store_finish(command_noop)
    command_noop_loaded = loaded_batch.command_records.get_slice(0, 1)[0]
    assert command_noop == command_noop_loaded

    assert stored_batch.command_records.get_slice(0, 2) == loaded_batch.command_records.get_slice(0, 2)

    # TODO ideally, the timestamps on stored_batch and loaded_batch would update as well
    reloaded_batch = cast(StoredBatch, store.get_batch(stored_batch.id))
    assert reloaded_batch.last_updated > reloaded_batch.created

def test_DatabaseBatchStore_start_background_inserts_row(database_connection_params: dict) -> None:
    store = DatabaseBatchStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    with store.connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `localuser_user_name`, `background_auth` FROM `background` JOIN `localuser` ON `background_started_localuser` = `localuser_id`')
        assert cursor.rowcount == 1
        user_name, auth = cast(tuple[Any, ...], cursor.fetchone())
        assert user_name == 'Lucas Werkmeister'
        assert json.loads(auth) == {'resource_owner_key': 'fake resource owner key',
                                    'resource_owner_secret': 'fake resource owner secret'}

def test_DatabaseBatchStore_start_background_does_not_insert_extra_row(database_connection_params: dict) -> None:
    store = DatabaseBatchStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    with store.connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `background_id`, `background_started_utc_timestamp` FROM `background`')
        assert cursor.rowcount == 1
        background_id, background_started_utc_timestamp = cast(tuple[Any, ...], cursor.fetchone())
    store.start_background(open_batch, fake_session)  # should be no-op
    with store.connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `background_id`, `background_started_utc_timestamp` FROM `background`')
        assert cursor.rowcount == 1
        assert (background_id, background_started_utc_timestamp) == cursor.fetchone()

def test_DatabaseBatchStore_stop_background_updates_row_removes_auth(database_connection_params: dict) -> None:
    store = DatabaseBatchStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    store.stop_background(open_batch, fake_session)
    with store.connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `background_auth`, `background_stopped_utc_timestamp`, `localuser_user_name` FROM `background` JOIN `localuser` ON `background_stopped_localuser` = `localuser_id`')
        assert cursor.rowcount == 1
        auth, stopped_utc_timestamp, stopped_user_name = cast(tuple[Any, ...], cursor.fetchone())
        assert stopped_utc_timestamp > 0
        assert stopped_user_name == 'Lucas Werkmeister'
        assert auth is None

def test_DatabaseBatchStore_stop_background_without_session(database_connection_params: dict) -> None:
    store = DatabaseBatchStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    store.stop_background(open_batch)
    with store.connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `background_stopped_utc_timestamp`, `background_stopped_localuser` FROM `background`')
        assert cursor.rowcount == 1
        stopped_utc_timestamp, stopped_localuser = cast(tuple[Any, ...], cursor.fetchone())
        assert stopped_utc_timestamp > 0
        assert stopped_localuser is None

def test_DatabaseBatchStore_stop_background_multiple_closes_all_raises_exception(database_connection_params: dict) -> None:
    store = DatabaseBatchStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    with store.connect() as connection, connection.cursor() as cursor:
        cursor.execute('INSERT INTO `background` (`background_batch`, `background_auth`, `background_started_utc_timestamp`, `background_started_localuser`) SELECT `background_batch`, `background_auth`, `background_started_utc_timestamp`, `background_started_localuser` FROM `background`')
        connection.commit()
    with pytest.raises(RuntimeError, match='Should have stopped at most 1 background operation, actually affected 2!'):
        store.stop_background(open_batch)
    with store.connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT 1 FROM `background` WHERE `background_stopped_utc_timestamp` IS NOT NULL')
        assert cursor.rowcount == 2
        cursor.execute('SELECT 1 FROM `background` WHERE `background_stopped_utc_timestamp` IS NULL')
        assert cursor.rowcount == 0

def test_DatabaseBatchStore_closing_batch_stops_background(database_connection_params: dict) -> None:
    store = DatabaseBatchStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    [command_record_1, command_record_2] = open_batch.command_records.get_slice(0, 2)
    open_batch.command_records.store_finish(CommandNoop(command_record_1.id, command_record_1.command, revision=1))
    open_batch.command_records.store_finish(CommandNoop(command_record_2.id, command_record_2.command, revision=2))
    with store.connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `background_stopped_utc_timestamp`, `background_stopped_localuser` FROM `background`')
        assert cursor.rowcount == 1
        stopped_utc_timestamp, stopped_localuser = cast(tuple[Any, ...], cursor.fetchone())
        assert stopped_utc_timestamp > 0
        assert stopped_localuser is None


command_unfinishes_and_rows: list[tuple[CommandRecord, tuple[int, Optional[dict]]]] = [
    (commandPlan1, (DatabaseBatchStore._COMMAND_STATUS_PLAN, None)),
    (commandPending1, (DatabaseBatchStore._COMMAND_STATUS_PENDING, None)),
]
command_finishes_and_rows: list[tuple[CommandRecord, tuple[int, Optional[dict]]]] = [
    (commandEdit1, (DatabaseBatchStore._COMMAND_STATUS_EDIT, {'base_revision': 1234, 'revision': 1235})),
    (commandNoop1, (DatabaseBatchStore._COMMAND_STATUS_NOOP, {'revision': 1234})),
    (commandPageMissing1, (DatabaseBatchStore._COMMAND_STATUS_PAGE_MISSING, {'curtimestamp': '2019-03-11T23:26:02Z'})),
    (commandTitleInvalid1, (DatabaseBatchStore._COMMAND_STATUS_TITLE_INVALID, {'curtimestamp': '2019-03-11T23:26:02Z'})),
    (commandPageProtected1, (DatabaseBatchStore._COMMAND_STATUS_PAGE_PROTECTED, {'curtimestamp': '2019-03-11T23:26:02Z'})),
    (commandPageBadContentFormat, (DatabaseBatchStore._COMMAND_STATUS_PAGE_BAD_CONTENT_FORMAT, {'content_format': 'text/css', 'content_model': 'sanitized-css', 'revision': 12345})),
    (commandPageBadContentModel, (DatabaseBatchStore._COMMAND_STATUS_PAGE_BAD_CONTENT_MODEL, {'content_format': 'text/x-wiki', 'content_model': 'unknown', 'revision': 12345})),
    (commandEditConflict1, (DatabaseBatchStore._COMMAND_STATUS_EDIT_CONFLICT, {})),
    (commandMaxlagExceeded1, (DatabaseBatchStore._COMMAND_STATUS_MAXLAG_EXCEEDED, {'retry_after_utc_timestamp': 1552749842})),
    (commandBlocked1, (DatabaseBatchStore._COMMAND_STATUS_BLOCKED, {'auto': False, 'blockinfo': blockinfo})),
    (commandBlocked2, (DatabaseBatchStore._COMMAND_STATUS_BLOCKED, {'auto': False, 'blockinfo': None})),
    (commandWikiReadOnly1, (DatabaseBatchStore._COMMAND_STATUS_WIKI_READ_ONLY, {'reason': 'maintenance', 'retry_after_utc_timestamp': 1552749842})),
    (commandWikiReadOnly2, (DatabaseBatchStore._COMMAND_STATUS_WIKI_READ_ONLY, {'reason': None})),
]

@pytest.mark.parametrize('command_finish, expected_row', command_finishes_and_rows)
def test_DatabaseBatchStore_command_finish_to_row(command_finish: CommandFinish, expected_row: tuple[int, Optional[dict]]) -> None:
    actual_row = DatabaseBatchStore({})._command_finish_to_row(command_finish)
    assert expected_row == actual_row

@pytest.mark.parametrize('expected_command_record, row', command_unfinishes_and_rows + command_finishes_and_rows)
def test_DatabaseBatchStore_row_to_command_record(expected_command_record: CommandRecord, row: tuple[int, Optional[dict]]) -> None:
    status, outcome = row
    outcome_json = json.dumps(outcome) if outcome else None
    full_row = expected_command_record.id, expected_command_record.command.page.title, expected_command_record.command.page.resolve_redirects, expected_command_record.command.actions_tpsv(), status, outcome_json
    actual_command_record = DatabaseBatchStore({})._row_to_command_record(*full_row)
    assert expected_command_record == actual_command_record

def test_DatabaseBatchStore_connection_reuse() -> None:
    with patch('database.DatabaseBatchStore._connect') as connect_patch:
        connect_patch.side_effect = lambda: Mock()  # new mock per call
        app = flask.Flask(__name__)
        store = DatabaseBatchStore({}, app)
        # reuse connection within one app context (and only close at the end)
        with app.app_context():
            with store.connect() as conn1:
                pass
            assert not cast(Mock, conn1.close).called
            with store.connect() as conn2:
                pass
            assert not cast(Mock, conn2.close).called
            assert conn2 is conn1
        assert cast(Mock, conn1.close).called
        assert cast(Mock, conn1.close).call_count == 1
        # don’t reuse connection in another app context
        with app.app_context():
            with store.connect() as conn3:
                pass
            assert conn3 is not conn1

def test_DatabaseBatchStore_connection_reuse_without_app() -> None:
    with patch('database.DatabaseBatchStore._connect') as connect_patch:
        connect_patch.side_effect = lambda: Mock()  # new mock per call
        store = DatabaseBatchStore({})
        # without an app, no connection reuse, close as soon as context manager exits
        with store.connect() as conn1:
            pass
        assert cast(Mock, conn1.close).called
        with store.connect() as conn2:
            pass
        assert cast(Mock, conn2.close).called
        assert conn2 is not conn1


def test_LocalUserStore_store_two_users(database_connection_params: dict) -> None:
    connection = pymysql.connect(**database_connection_params)
    try:
        domain_store = StringTableStore('domain', 'domain_id', 'domain_hash', 'domain_name')
        local_user_store = _LocalUserStore(domain_store)

        localuser_id_1 = local_user_store.acquire_localuser_id(connection, localUser1)
        localuser_id_2 = local_user_store.acquire_localuser_id(connection, localUser2)

        assert localuser_id_1 != localuser_id_2

        with connection.cursor() as cursor:
            cursor.execute('''SELECT localuser_user_name, localuser_local_user_id, localuser_global_user_id
                              FROM localuser
                              WHERE localuser_id = %s''',
                           (localuser_id_1,))
            assert cursor.fetchone() == (localUser1.user_name, localUser1.local_user_id, localUser1.global_user_id)

        with connection.cursor() as cursor:
            cursor.execute('''SELECT localuser_user_name, localuser_local_user_id, localuser_global_user_id
                              FROM localuser
                              WHERE localuser_id = %s''',
                           (localuser_id_2,))
            assert cursor.fetchone() == (localUser2.user_name, localUser2.local_user_id, localUser2.global_user_id)
    finally:
        connection.close()

def test_LocalUserStore_store_same_user_twice(database_connection_params: dict) -> None:
    connection = pymysql.connect(**database_connection_params)
    try:
        domain_store = StringTableStore('domain', 'domain_id', 'domain_hash', 'domain_name')
        local_user_store = _LocalUserStore(domain_store)

        localuser_id_1 = local_user_store.acquire_localuser_id(connection, localUser1)
        localuser_id_2 = local_user_store.acquire_localuser_id(connection, localUser1)

        assert localuser_id_1 == localuser_id_2

        with connection.cursor() as cursor:
            cursor.execute('''SELECT localuser_user_name, localuser_local_user_id, localuser_global_user_id
                              FROM localuser
                              WHERE localuser_id = %s''',
                           (localuser_id_1,))
            assert cursor.fetchone() == (localUser1.user_name, localUser1.local_user_id, localUser1.global_user_id)
    finally:
        connection.close()

def test_LocalUserStore_store_renamed_user(database_connection_params: dict) -> None:
    connection = pymysql.connect(**database_connection_params)
    try:
        domain_store = StringTableStore('domain', 'domain_id', 'domain_hash', 'domain_name')
        local_user_store = _LocalUserStore(domain_store)

        localuser_id_1 = local_user_store.acquire_localuser_id(connection, localUser1)
        localuser_id_2 = local_user_store.acquire_localuser_id(connection, LocalUser(localUser1.user_name + ' (renamed)',
                                                                                     localUser1.domain,
                                                                                     localUser1.local_user_id,
                                                                                     localUser1.global_user_id))

        assert localuser_id_1 == localuser_id_2

        with connection.cursor() as cursor:
            cursor.execute('''SELECT localuser_user_name, localuser_local_user_id, localuser_global_user_id
                              FROM localuser
                              WHERE localuser_id = %s''',
                           (localuser_id_1,))
            assert cursor.fetchone() == (localUser1.user_name + ' (renamed)', localUser1.local_user_id, localUser1.global_user_id)
    finally:
        connection.close()

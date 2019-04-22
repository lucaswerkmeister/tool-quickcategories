import datetime
import json
import mwoauth # type: ignore
import os
import pymysql
import pytest # type: ignore
import random
import re
import string
import time
from typing import List, Optional, Tuple

from command import CommandRecord, CommandEdit, CommandNoop
from database import DatabaseStore, _StringTableStore, _LocalUserStore
from localuser import LocalUser

from test_batch import newBatch1
from test_command import commandPlan1, commandPending1, commandEdit1, commandNoop1, commandPageMissing1, commandPageProtected1, commandEditConflict1, commandMaxlagExceeded1, commandBlocked1, blockinfo, commandBlocked2, commandWikiReadOnly1, commandWikiReadOnly2
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


@pytest.fixture(scope="module")
def fresh_database_connection_params():
    if 'MARIADB_ROOT_PASSWORD' not in os.environ:
        pytest.skip('MariaDB credentials not provided')
    connection = pymysql.connect(host='localhost',
                                 user='root',
                                 password=os.environ['MARIADB_ROOT_PASSWORD'])
    database_name = 'quickcategories_test_' + ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(16))
    user_name = 'quickcategories_test_user_' + ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(16))
    user_password = 'quickcategories_test_password_' + ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(16))
    try:
        with connection.cursor() as cursor:
            cursor.execute('CREATE DATABASE `%s`' % database_name)
            cursor.execute('GRANT ALL PRIVILEGES ON `%s`.* TO `%s` IDENTIFIED BY %%s' % (database_name, user_name), (user_password,))
            cursor.execute('USE `%s`' % database_name)
            with open('tables.sql') as tables:
                queries = tables.read()
                # PyMySQL does not support multiple queries in execute(), so we have to split
                for query in queries.split(';'):
                    query = query.strip()
                    if query:
                        cursor.execute(query)
        connection.commit()
        yield {'host': 'localhost', 'user': user_name, 'password': user_password, 'db': database_name}
    finally:
        with connection.cursor() as cursor:
            cursor.execute('DROP DATABASE IF EXISTS `%s`' % database_name)
            cursor.execute('DROP USER IF EXISTS `%s`' % user_name)
            connection.commit()
        connection.close()

@pytest.fixture
def database_connection_params(fresh_database_connection_params):
    connection = pymysql.connect(**fresh_database_connection_params)
    try:
        with open('tables.sql') as tables:
            queries = tables.read()
        with connection.cursor() as cursor:
            for table in re.findall(r'CREATE TABLE ([^ ]+) ', queries):
                cursor.execute('DELETE FROM `%s`' % table) # more efficient than TRUNCATE TABLE on my system :/
                # cursor.execute('ALTER TABLE `%s` AUTO_INCREMENT = 1' % table) # currently not necessary
        connection.commit()
    finally:
        connection.close()
    return fresh_database_connection_params


def test_DatabaseStore_store_batch(database_connection_params):
    store = DatabaseStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    command2 = open_batch.command_records.get_slice(1, 1)[0]

    with store._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT `command_page`, `actions_tpsv` FROM `command` JOIN `actions` on `command_actions_id` = `actions_id` WHERE `command_id` = %s AND `command_batch` = %s', (command2.id, open_batch.id))
            command2_page, command2_actions_tpsv = cursor.fetchone()
            assert command2_page == command2.command.page
            assert command2_actions_tpsv == command2.command.actions_tpsv()

def test_DatabaseStore_update_batch(database_connection_params):
    store = DatabaseStore(database_connection_params)
    stored_batch = store.store_batch(newBatch1, fake_session)
    loaded_batch = store.get_batch(stored_batch.id)

    [command_plan_1, command_plan_2] = loaded_batch.command_records.get_slice(0, 2)

    command_edit = CommandEdit(command_plan_1.id, command_plan_1.command, 1234, 1235)
    loaded_batch.command_records.store_finish(command_edit)
    command_edit_loaded = loaded_batch.command_records.get_slice(0, 1)[0]
    assert command_edit == command_edit_loaded

    command_noop = CommandNoop(command_plan_1.id, command_plan_1.command, 1234)
    time.sleep(1) # make sure that this update increases last_updated
    loaded_batch.command_records.store_finish(command_noop)
    command_noop_loaded = loaded_batch.command_records.get_slice(0, 1)[0]
    assert command_noop == command_noop_loaded

    assert stored_batch.command_records.get_slice(0, 2) == loaded_batch.command_records.get_slice(0, 2)

    # TODO ideally, the timestamps on stored_batch and loaded_batch would update as well
    reloaded_batch = store.get_batch(stored_batch.id)
    assert reloaded_batch.last_updated > reloaded_batch.created

def test_DatabaseStore_datetime_to_utc_timestamp():
    store = DatabaseStore({})
    dt = datetime.datetime(2019, 3, 17, 13, 23, 28, tzinfo=datetime.timezone.utc)
    assert store._datetime_to_utc_timestamp(dt) == 1552829008

@pytest.mark.parametrize('dt', [
    datetime.datetime.now(),
    datetime.datetime.utcnow(),
    datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=1))),
    datetime.datetime(2019, 3, 17, 13, 23, 28, 251638, tzinfo=datetime.timezone.utc)
])
def test_DatabaseStore_datetime_to_utc_timestamp_invalid_timezone(dt):
    store = DatabaseStore({})
    with pytest.raises(AssertionError):
        store._datetime_to_utc_timestamp(dt)

def test_DatabaseStore_utc_timestamp_to_datetime():
    store = DatabaseStore({})
    dt = datetime.datetime(2019, 3, 17, 13, 23, 28, tzinfo=datetime.timezone.utc)
    assert store._utc_timestamp_to_datetime(1552829008) == dt

def test_DatabaseStore_start_background_inserts_row(database_connection_params):
    store = DatabaseStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    with store._connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `localuser_user_name`, `background_auth` FROM `background` JOIN `localuser` ON `background_started_localuser_id` = `localuser_id`')
        assert cursor.rowcount == 1
        user_name, auth = cursor.fetchone()
        assert user_name == 'Lucas Werkmeister'
        assert json.loads(auth) == {'resource_owner_key': 'fake resource owner key',
                                    'resource_owner_secret': 'fake resource owner secret'}

def test_DatabaseStore_start_background_does_not_insert_extra_row(database_connection_params):
    store = DatabaseStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    with store._connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `background_id`, `background_started_utc_timestamp` FROM `background`')
        assert cursor.rowcount == 1
        background_id, background_started_utc_timestamp = cursor.fetchone()
    store.start_background(open_batch, fake_session) # should be no-op
    with store._connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `background_id`, `background_started_utc_timestamp` FROM `background`')
        assert cursor.rowcount == 1
        assert (background_id, background_started_utc_timestamp) == cursor.fetchone()

def test_DatabaseStore_stop_background_updates_row_removes_auth(database_connection_params):
    store = DatabaseStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    store.stop_background(open_batch, fake_session)
    with store._connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `background_auth`, `background_stopped_utc_timestamp`, `localuser_user_name` FROM `background` JOIN `localuser` ON `background_stopped_localuser_id` = `localuser_id`')
        assert cursor.rowcount == 1
        auth, stopped_utc_timestamp, stopped_user_name = cursor.fetchone()
        assert stopped_utc_timestamp > 0
        assert stopped_user_name == 'Lucas Werkmeister'
        assert auth is None

def test_DatabaseStore_stop_background_without_session(database_connection_params):
    store = DatabaseStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    store.stop_background(open_batch)
    with store._connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `background_stopped_utc_timestamp`, `background_stopped_localuser_id` FROM `background`')
        assert cursor.rowcount == 1
        stopped_utc_timestamp, stopped_localuser_id = cursor.fetchone()
        assert stopped_utc_timestamp > 0
        assert stopped_localuser_id is None

def test_DatabaseStore_stop_background_multiple_closes_all_raises_exception(database_connection_params):
    store = DatabaseStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    with store._connect() as connection, connection.cursor() as cursor:
        cursor.execute('INSERT INTO `background` (`background_batch`, `background_auth`, `background_started_utc_timestamp`, `background_started_localuser_id`) SELECT `background_batch`, `background_auth`, `background_started_utc_timestamp`, `background_started_localuser_id` FROM `background`')
        connection.commit()
    with pytest.raises(RuntimeError, match='Should have stopped at most 1 background operation, actually affected 2!'):
        store.stop_background(open_batch)
    with store._connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT 1 FROM `background` WHERE `background_stopped_utc_timestamp` IS NOT NULL')
        assert cursor.rowcount == 2
        cursor.execute('SELECT 1 FROM `background` WHERE `background_stopped_utc_timestamp` IS NULL')
        assert cursor.rowcount == 0

def test_DatabaseStore_closing_batch_stops_background(database_connection_params):
    store = DatabaseStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    store.start_background(open_batch, fake_session)
    [command_record_1, command_record_2] = open_batch.command_records.get_slice(0, 2)
    open_batch.command_records.store_finish(CommandNoop(command_record_1.id, command_record_1.command, revision=1))
    open_batch.command_records.store_finish(CommandNoop(command_record_2.id, command_record_2.command, revision=2))
    with store._connect() as connection, connection.cursor() as cursor:
        cursor.execute('SELECT `background_stopped_utc_timestamp`, `background_stopped_localuser_id` FROM `background`')
        assert cursor.rowcount == 1
        stopped_utc_timestamp, stopped_localuser_id = cursor.fetchone()
        assert stopped_utc_timestamp > 0
        assert stopped_localuser_id is None

def test_DatabaseStore_make_plan_pending_background(database_connection_params):
    store = DatabaseStore(database_connection_params)
    batch_1 = store.store_batch(newBatch1, fake_session)
    time.sleep(1)
    batch_2 = store.store_batch(newBatch1, fake_session) # NOQA: F841 (unused)
    time.sleep(1)
    batch_3 = store.store_batch(newBatch1, fake_session)
    time.sleep(1)
    batch_4 = store.store_batch(newBatch1, fake_session)
    time.sleep(1)
    batch_5 = store.store_batch(newBatch1, fake_session)

    # batch 1 cannot be run because it is already finished
    [batch_1_command_record_1, batch_1_command_record_2] = batch_1.command_records.get_slice(0, 2)
    batch_1.command_records.store_finish(CommandNoop(batch_1_command_record_1.id, batch_1_command_record_1.command, revision=1))
    batch_1.command_records.store_finish(CommandNoop(batch_1_command_record_2.id, batch_1_command_record_2.command, revision=2))

    # batch 2 cannot be run because there is no background run
    # batch 3 cannot be run because the only background run is already stopped
    store.start_background(batch_3, fake_session)
    store.stop_background(batch_3, fake_session)

    # batch 4 and 5 have background runs and can be run
    store.start_background(batch_4, fake_session)
    store.start_background(batch_5, fake_session)

    # first batch 4 (older)
    pending_1 = store.make_plan_pending_background(mwoauth.ConsumerToken('fake', 'fake'), 'fake user agent')
    assert pending_1 is not None
    background_batch_1, background_command_1, background_session_1 = pending_1
    assert background_batch_1.id == batch_4.id
    assert background_command_1.id == batch_4.command_records.get_slice(0, 1)[0].id
    time.sleep(1)
    batch_4.command_records.store_finish(CommandNoop(background_command_1.id, background_command_1.command, revision=3))

    # next batch 5, even though batch 4 isn’t done yet, because batch 4 is now newer
    pending_2 = store.make_plan_pending_background(mwoauth.ConsumerToken('fake', 'fake'), 'fake user agent')
    assert pending_2 is not None
    background_batch_2, background_command_2, background_session_2 = pending_2
    assert background_batch_2.id == batch_5.id
    assert background_command_2.id == batch_5.command_records.get_slice(0, 1)[0].id
    time.sleep(1)
    batch_5.command_records.store_finish(CommandNoop(background_command_2.id, background_command_2.command, revision=4))

    # then batch 4 again
    pending_3 = store.make_plan_pending_background(mwoauth.ConsumerToken('fake', 'fake'), 'fake user agent')
    assert pending_3 is not None
    background_batch_3, background_command_3, background_session_3 = pending_3
    assert background_batch_3.id == batch_4.id
    assert background_command_3.id == batch_4.command_records.get_slice(1, 1)[0].id
    batch_4.command_records.store_finish(CommandNoop(background_command_3.id, background_command_3.command, revision=5))

    # meanwhile, we finish batch 5 independently
    batch_5_command_record_2 = batch_5.command_records.get_slice(1, 1)[0]
    batch_5.command_records.store_finish(CommandNoop(batch_5_command_record_2.id, batch_5_command_record_2.command, revision=6))

    # therefore, there is now nothing to do
    pending_4 = store.make_plan_pending_background(mwoauth.ConsumerToken('fake', 'fake'), 'fake user agent')
    assert pending_4 is None


command_unfinishes_and_rows = [
    (commandPlan1, (DatabaseStore._COMMAND_STATUS_PLAN, None)),
    (commandPending1, (DatabaseStore._COMMAND_STATUS_PENDING, None)),
] # type: List[Tuple[CommandRecord, Tuple[int, Optional[dict]]]]
command_finishes_and_rows = [
    (commandEdit1, (DatabaseStore._COMMAND_STATUS_EDIT, {'base_revision': 1234, 'revision': 1235})),
    (commandNoop1, (DatabaseStore._COMMAND_STATUS_NOOP, {'revision': 1234})),
    (commandPageMissing1, (DatabaseStore._COMMAND_STATUS_PAGE_MISSING, {'curtimestamp': '2019-03-11T23:26:02Z'})),
    (commandPageProtected1, (DatabaseStore._COMMAND_STATUS_PAGE_PROTECTED, {'curtimestamp': '2019-03-11T23:26:02Z'})),
    (commandEditConflict1, (DatabaseStore._COMMAND_STATUS_EDIT_CONFLICT, {})),
    (commandMaxlagExceeded1, (DatabaseStore._COMMAND_STATUS_MAXLAG_EXCEEDED, {'retry_after_utc_timestamp': 1552749842})),
    (commandBlocked1, (DatabaseStore._COMMAND_STATUS_BLOCKED, {'auto': False, 'blockinfo': blockinfo})),
    (commandBlocked2, (DatabaseStore._COMMAND_STATUS_BLOCKED, {'auto': False, 'blockinfo': None})),
    (commandWikiReadOnly1, (DatabaseStore._COMMAND_STATUS_WIKI_READ_ONLY, {'reason': 'maintenance', 'retry_after_utc_timestamp': 1552749842})),
    (commandWikiReadOnly2, (DatabaseStore._COMMAND_STATUS_WIKI_READ_ONLY, {'reason': None})),
] # type: List[Tuple[CommandRecord, Tuple[int, Optional[dict]]]]

@pytest.mark.parametrize('command_finish, expected_row', command_finishes_and_rows)
def test_DatabaseStore_command_finish_to_row(command_finish, expected_row):
    actual_row = DatabaseStore({})._command_finish_to_row(command_finish)
    assert expected_row == actual_row

@pytest.mark.parametrize('expected_command_record, row', command_unfinishes_and_rows + command_finishes_and_rows)
def test_DatabaseStore_row_to_command_record(expected_command_record, row):
    status, outcome = row
    outcome_json = json.dumps(outcome) if outcome else None
    full_row = expected_command_record.id, expected_command_record.command.page, expected_command_record.command.actions_tpsv(), status, outcome_json
    actual_command_record = DatabaseStore({})._row_to_command_record(*full_row)
    assert expected_command_record == actual_command_record


@pytest.mark.parametrize('string, expected_hash', [
    # all hashes obtained in MariaDB via SELECT CAST(CONV(SUBSTRING(SHA2(**string**, 256), 1, 8), 16, 10) AS unsigned int);
    ('', 3820012610),
    ('test.wikipedia.org', 3277830609),
    ('äöü', 3157433791),
    ('☺', 3752208785),
    ('🤔', 1622577385),
])
def test_StringTableStore_hash(string, expected_hash):
    store = _StringTableStore('', '', '', '')

    actual_hash = store._hash(string)

    assert expected_hash == actual_hash

def test_StringTableStore_acquire_id_database(database_connection_params):
    connection = pymysql.connect(**database_connection_params)
    try:
        store = _StringTableStore('domain', 'domain_id', 'domain_hash', 'domain_name')

        store.acquire_id(connection, 'test.wikipedia.org')

        with connection.cursor() as cursor:
            cursor.execute('SELECT domain_name FROM domain WHERE domain_hash = 3277830609')
            result = cursor.fetchone()
            assert result == ('test.wikipedia.org',)

        with store._cache_lock:
            store._cache.clear()

        store.acquire_id(connection, 'test.wikipedia.org')

        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM domain')
            result = cursor.fetchone()
            assert result == (1,)
    finally:
        connection.close()

def test_StringTableStore_acquire_id_cached():
    store = _StringTableStore('', '', '', '')

    with store._cache_lock:
        store._cache['test.wikipedia.org'] = 1

    assert store.acquire_id(None, 'test.wikipedia.org') == 1


def test_LocalUserStore_store_two_users(database_connection_params):
    connection = pymysql.connect(**database_connection_params)
    try:
        domain_store = _StringTableStore('domain', 'domain_id', 'domain_hash', 'domain_name')
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

def test_LocalUserStore_store_same_user_twice(database_connection_params):
    connection = pymysql.connect(**database_connection_params)
    try:
        domain_store = _StringTableStore('domain', 'domain_id', 'domain_hash', 'domain_name')
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

def test_LocalUserStore_store_renamed_user(database_connection_params):
    connection = pymysql.connect(**database_connection_params)
    try:
        domain_store = _StringTableStore('domain', 'domain_id', 'domain_hash', 'domain_name')
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

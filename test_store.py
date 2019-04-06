import datetime
import json
import os
import pymysql
import pytest # type: ignore
import random
import re
import string
import time
from typing import List, Optional, Tuple

from batch import OpenBatch, ClosedBatch
from command import CommandRecord, CommandEdit, CommandNoop
from store import InMemoryStore, DatabaseStore, _BatchCommandRecordsDatabase, _StringTableStore

from test_batch import newBatch1
from test_command import commandPlan1, commandPending1, commandEdit1, commandNoop1, commandPageMissing1, commandEditConflict1, commandMaxlagExceeded1, commandBlocked1, blockinfo, commandBlocked2, commandWikiReadOnly1, commandWikiReadOnly2
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


def test_InMemoryStore_store_batch_command_ids():
    open_batch = InMemoryStore().store_batch(newBatch1, fake_session)
    assert len(open_batch.command_records) == 2
    [command_record_1, command_record_2] = open_batch.command_records.get_slice(0, 2)
    assert command_record_1.id != command_record_2.id

def test_InMemoryStore_store_batch_batch_ids():
    store = InMemoryStore()
    open_batch_1 = store.store_batch(newBatch1, fake_session)
    open_batch_2 = store.store_batch(newBatch1, fake_session)
    assert open_batch_1.id != open_batch_2.id

def test_InMemoryStore_store_batch_metadata():
    open_batch = InMemoryStore().store_batch(newBatch1, fake_session)
    assert open_batch.user_name == 'Lucas Werkmeister'
    assert open_batch.local_user_id == 6198807
    assert open_batch.global_user_id == 46054761
    assert open_batch.domain == 'commons.wikimedia.org'

def test_InMemoryStore_get_batch():
    store = InMemoryStore()
    open_batch = store.store_batch(newBatch1, fake_session)
    assert open_batch is store.get_batch(open_batch.id)

def test_InMemoryStore_get_batch_None():
    assert InMemoryStore().get_batch(0) is None

def test_InMemoryStore_get_latest_batches():
    store = InMemoryStore()
    open_batches = []
    for i in range(25):
        open_batches.append(store.store_batch(newBatch1, fake_session))
    open_batches.reverse()
    assert open_batches[:10] == store.get_latest_batches()

def test_InMemoryStore_closes_batch():
    store = InMemoryStore()
    open_batch = store.store_batch(newBatch1, fake_session)
    [command_record_1, command_record_2] = open_batch.command_records.get_slice(0, 2)
    open_batch.command_records.store_finish(CommandNoop(command_record_1.id, command_record_1.command, revision=1))
    assert type(store.get_batch(open_batch.id)) is OpenBatch
    open_batch.command_records.store_finish(CommandNoop(command_record_2.id, command_record_2.command, revision=2))
    assert type(store.get_batch(open_batch.id)) is ClosedBatch


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

def test_DatabaseStore_get_batch(database_connection_params):
    store = DatabaseStore(database_connection_params)
    stored_batch = store.store_batch(newBatch1, fake_session)
    loaded_batch = store.get_batch(stored_batch.id)

    assert loaded_batch.id == stored_batch.id
    assert loaded_batch.user_name == 'Lucas Werkmeister'
    assert loaded_batch.local_user_id == 6198807
    assert loaded_batch.global_user_id == 46054761
    assert loaded_batch.domain == 'commons.wikimedia.org'

    assert len(loaded_batch.command_records) == 2
    assert loaded_batch.command_records.get_slice(0, 2) == stored_batch.command_records.get_slice(0, 2)

def test_DatabaseStore_get_batch_missing(database_connection_params):
    store = DatabaseStore(database_connection_params)
    loaded_batch = store.get_batch(1)
    assert loaded_batch is None

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

def test_DatabaseStore_closes_batch(database_connection_params):
    store = DatabaseStore(database_connection_params)
    open_batch = store.store_batch(newBatch1, fake_session)
    [command_record_1, command_record_2] = open_batch.command_records.get_slice(0, 2)
    open_batch.command_records.store_finish(CommandNoop(command_record_1.id, command_record_1.command, revision=1))
    assert type(store.get_batch(open_batch.id)) is OpenBatch
    open_batch.command_records.store_finish(CommandNoop(command_record_2.id, command_record_2.command, revision=2))
    assert type(store.get_batch(open_batch.id)) is ClosedBatch

def test_DatabaseStore_get_latest_batches(database_connection_params):
    store = DatabaseStore(database_connection_params)
    open_batches = []
    for i in range(25):
        open_batches.append(store.store_batch(newBatch1, fake_session))
    open_batches.reverse()
    assert open_batches[:10] == store.get_latest_batches()

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


command_unfinishes_and_rows = [
    (commandPlan1, (DatabaseStore._COMMAND_STATUS_PLAN, None)),
    (commandPending1, (DatabaseStore._COMMAND_STATUS_PENDING, None)),
] # type: List[Tuple[CommandRecord, Tuple[int, Optional[dict]]]]
command_finishes_and_rows = [
    (commandEdit1, (DatabaseStore._COMMAND_STATUS_EDIT, {'base_revision': 1234, 'revision': 1235})),
    (commandNoop1, (DatabaseStore._COMMAND_STATUS_NOOP, {'revision': 1234})),
    (commandPageMissing1, (DatabaseStore._COMMAND_STATUS_PAGE_MISSING, {'curtimestamp': '2019-03-11T23:26:02Z'})),
    (commandEditConflict1, (DatabaseStore._COMMAND_STATUS_EDIT_CONFLICT, {})),
    (commandMaxlagExceeded1, (DatabaseStore._COMMAND_STATUS_MAXLAG_EXCEEDED, {'retry_after_utc_timestamp': 1552749842})),
    (commandBlocked1, (DatabaseStore._COMMAND_STATUS_BLOCKED, {'auto': False, 'blockinfo': blockinfo})),
    (commandBlocked2, (DatabaseStore._COMMAND_STATUS_BLOCKED, {'auto': False, 'blockinfo': None})),
    (commandWikiReadOnly1, (DatabaseStore._COMMAND_STATUS_WIKI_READ_ONLY, {'reason': 'maintenance'})),
    (commandWikiReadOnly2, (DatabaseStore._COMMAND_STATUS_WIKI_READ_ONLY, {'reason': None})),
] # type: List[Tuple[CommandRecord, Tuple[int, Optional[dict]]]]

@pytest.mark.parametrize('command_finish, expected_row', command_finishes_and_rows)
def test_BatchCommandRecordsDatabase_command_finish_to_row(command_finish, expected_row):
    actual_row = _BatchCommandRecordsDatabase(0, DatabaseStore({}))._command_finish_to_row(command_finish)
    assert expected_row == actual_row

@pytest.mark.parametrize('expected_command_record, row', command_unfinishes_and_rows + command_finishes_and_rows)
def test_BatchCommandRecordsDatabase_row_to_command_record(expected_command_record, row):
    status, outcome = row
    outcome_json = json.dumps(outcome) if outcome else None
    full_row = expected_command_record.id, expected_command_record.command.page, expected_command_record.command.actions_tpsv(), status, outcome_json
    actual_command_record = _BatchCommandRecordsDatabase(0, DatabaseStore({}))._row_to_command_record(*full_row)
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

import contextlib
import json
import os
import pymysql
import pytest
import random
import string

from command import CommandEdit, CommandNoop
from store import InMemoryStore, DatabaseStore, _DatabaseCommandRecords

from test_batch import newBatch1
from test_command import commandPlan1, commandEdit1, commandNoop1, commandPageMissing1, commandEditConflict1, commandMaxlagExceeded1, commandBlocked1, blockinfo, commandBlocked2
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
    assert open_batch.command_records[0].id != open_batch.command_records[1].id

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


@contextlib.contextmanager
def temporary_database():
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
            cursor.execute('USE mysql')
        connection.commit()
        yield {'host': 'localhost', 'user': user_name, 'password': user_password, 'db': database_name}
    finally:
        with connection.cursor() as cursor:
            cursor.execute('DROP DATABASE IF EXISTS `%s`' % database_name)
            cursor.execute('DROP USER IF EXISTS `%s`' % user_name)
            connection.commit()
        connection.close()

def test_DatabaseStore_store_batch():
    with temporary_database() as connection_params:
        store = DatabaseStore(connection_params)
        open_batch = store.store_batch(newBatch1, fake_session)
        command2 = open_batch.command_records[1]

        with store._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT * FROM `batch`')
            with connection.cursor() as cursor:
                cursor.execute('SELECT * FROM `command`')
            with connection.cursor() as cursor:
                cursor.execute('SELECT `command_tpsv` FROM `command` WHERE `command_id` = %s AND `command_batch` = %s', (command2.id, open_batch.id))
                (command2_tpsv,) = cursor.fetchone()
                assert command2_tpsv == str(command2.command)

def test_DatabaseStore_get_batch():
    with temporary_database() as connection_params:
        store = DatabaseStore(connection_params)
        stored_batch = store.store_batch(newBatch1, fake_session)
        loaded_batch = store.get_batch(stored_batch.id)

        assert loaded_batch.id == stored_batch.id
        assert loaded_batch.user_name == 'Lucas Werkmeister'
        assert loaded_batch.local_user_id == 6198807
        assert loaded_batch.global_user_id == 46054761
        assert loaded_batch.domain == 'commons.wikimedia.org'

        assert len(loaded_batch.command_records) == 2
        assert loaded_batch.command_records[0] == stored_batch.command_records[0]
        assert loaded_batch.command_records[1] == stored_batch.command_records[1]
        assert loaded_batch.command_records[0:2] == stored_batch.command_records[0:2]

def test_DatabaseStore_get_batch_missing():
    with temporary_database() as connection_params:
        store = DatabaseStore(connection_params)
        loaded_batch = store.get_batch(1)

    assert loaded_batch is None

def test_DatabaseStore_update_batch():
    with temporary_database() as connection_params:
        store = DatabaseStore(connection_params)
        stored_batch = store.store_batch(newBatch1, fake_session)
        loaded_batch = store.get_batch(stored_batch.id)

        [command_plan_1, command_plan_2] = loaded_batch.command_records[0:2]

        command_edit = CommandEdit(command_plan_1.id, command_plan_1.command, 1234, 1235)
        loaded_batch.command_records[0] = command_edit
        command_edit_loaded = loaded_batch.command_records[0]
        assert command_edit == command_edit_loaded

        command_noop = CommandNoop(command_plan_1.id, command_plan_1.command, 1234)
        loaded_batch.command_records[1] = command_noop
        command_noop_loaded = loaded_batch.command_records[0]
        assert command_noop == command_noop_loaded

        assert stored_batch.command_records[0:2] == loaded_batch.command_records[0:2]


command_records_and_rows = [
    # (commandPlan1, (DatabaseStore._COMMAND_STATUS_PLAN, None)), # not supported for update, but perhaps turn into test for initial store?
    (commandEdit1, (DatabaseStore._COMMAND_STATUS_EDIT, {'base_revision': 1234, 'revision': 1235})),
    (commandNoop1, (DatabaseStore._COMMAND_STATUS_NOOP, {'revision': 1234})),
    (commandPageMissing1, (DatabaseStore._COMMAND_STATUS_PAGE_MISSING, {'curtimestamp': '2019-03-11T23:26:02Z'})),
    (commandEditConflict1, (DatabaseStore._COMMAND_STATUS_EDIT_CONFLICT, {})),
    (commandMaxlagExceeded1, (DatabaseStore._COMMAND_STATUS_MAXLAG_EXCEEDED, {'retry_after_utc_timestamp': 1552749842.607831})),
    (commandBlocked1, (DatabaseStore._COMMAND_STATUS_BLOCKED, {'auto': False, 'blockinfo': blockinfo})),
    (commandBlocked2, (DatabaseStore._COMMAND_STATUS_BLOCKED, {'auto': False, 'blockinfo': None})),
]

@pytest.mark.parametrize('command_record, expected_row', command_records_and_rows)
def test_DatabaseCommandRecords_command_record_to_row(command_record, expected_row):
    actual_row = _DatabaseCommandRecords(0, DatabaseStore({}))._command_record_to_row(command_record)
    assert expected_row == actual_row

@pytest.mark.parametrize('expected_command_record, row', command_records_and_rows)
def test_DatabaseCommandRecords_row_to_command_record(expected_command_record, row):
    status, outcome = row
    full_row = expected_command_record.id, str(expected_command_record.command), status, json.dumps(outcome)
    actual_command_record = _DatabaseCommandRecords(0, DatabaseStore({}))._row_to_command_record(*full_row)
    assert expected_command_record == actual_command_record

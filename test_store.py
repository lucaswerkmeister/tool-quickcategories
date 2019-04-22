import pytest # type: ignore

from batch import NewBatch, OpenBatch, ClosedBatch
from command import Command, CommandPlan, CommandPending, CommandNoop, CommandWikiReadOnly
from database import DatabaseStore
from in_memory import InMemoryStore
from localuser import LocalUser

from test_action import addCategory1
from test_batch import newBatch1
from test_database import fresh_database_connection_params, database_connection_params # NOQA F401 “unused” imports needed for store fixture
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


@pytest.fixture(params=[InMemoryStore, DatabaseStore])
def store(request):
    if request.param is InMemoryStore:
        yield InMemoryStore()
    elif request.param is DatabaseStore:
        database_connection_params = request.getfixturevalue('database_connection_params')
        yield DatabaseStore(database_connection_params)
    else:
        raise ValueError('Unknown param!')


def test_BatchStore_get_batch(store):
    stored_batch = store.store_batch(newBatch1, fake_session)
    loaded_batch = store.get_batch(stored_batch.id)

    assert loaded_batch.id == stored_batch.id
    assert loaded_batch.local_user == LocalUser('Lucas Werkmeister', 'commons.wikimedia.org', 6198807, 46054761)
    assert loaded_batch.domain == 'commons.wikimedia.org'

    assert len(loaded_batch.command_records) == 2
    assert loaded_batch.command_records.get_slice(0, 2) == stored_batch.command_records.get_slice(0, 2)

def test_BatchStore_get_batch_missing(store):
    loaded_batch = store.get_batch(1)
    assert loaded_batch is None

def test_BatchStore_closes_batch(store):
    open_batch = store.store_batch(newBatch1, fake_session)
    [command_record_1, command_record_2] = open_batch.command_records.get_slice(0, 2)
    open_batch.command_records.store_finish(CommandNoop(command_record_1.id, command_record_1.command, revision=1))
    assert type(store.get_batch(open_batch.id)) is OpenBatch
    open_batch.command_records.store_finish(CommandNoop(command_record_2.id, command_record_2.command, revision=2))
    assert type(store.get_batch(open_batch.id)) is ClosedBatch

def test_BatchStore_get_latest_batches(store):
    open_batches = []
    for i in range(25):
        open_batches.append(store.store_batch(newBatch1, fake_session))
    open_batches.reverse()
    assert open_batches[:10] == store.get_latest_batches()

def test_BatchStore_stop_background_noop(store):
    open_batch = store.store_batch(newBatch1, fake_session)
    store.stop_background(open_batch)
    # no error

def test_BatchStore_retry(store):
    open_batch = store.store_batch(newBatch1, fake_session)
    [command_record_1, command_record_2] = open_batch.command_records.get_slice(0, 2)
    open_batch.command_records.store_finish(CommandWikiReadOnly(command_record_1.id, command_record_1.command, reason=None, retry_after=None))
    assert len(open_batch.command_records) == 3
    open_batch.command_records.store_finish(CommandWikiReadOnly(command_record_2.id, command_record_2.command, reason=None, retry_after=None))
    assert len(open_batch.command_records) == 4
    [command_record_1, command_record_2, command_record_3, command_record_4] = open_batch.command_records.get_slice(0, 4)
    assert command_record_3.command == command_record_1.command
    assert command_record_4.command == command_record_2.command
    assert isinstance(command_record_3, CommandPlan)
    assert isinstance(command_record_4, CommandPlan)
    assert command_record_3.id != command_record_1.id
    assert command_record_3.id != command_record_4.id

def test_BatchStore_make_plans_pending_and_make_pendings_planned(store):
    command_1 = Command('Page 1', [addCategory1])
    command_2 = Command('Page 2', [addCategory1])
    command_3 = Command('Page 3', [addCategory1])
    command_4 = Command('Page 4', [addCategory1])
    open_batch = store.store_batch(NewBatch([command_1, command_2, command_3, command_4]), fake_session)
    command_records = open_batch.command_records
    [id_1, id_2, id_3, id_4] = [command_record.id for command_record in command_records.get_slice(0, 4)]

    [pending_1, pending_2] = command_records.make_plans_pending(offset=0, limit=2)
    assert [pending_1.id, pending_2.id] == [id_1, id_2]
    [pending_3, pending_4] = command_records.make_plans_pending(offset=0, limit=4) # does not return commands that are already pending
    assert [pending_3.id, pending_4.id] == [id_3, id_4]

    command_records.make_pendings_planned([id_1, id_3])
    assert [CommandPlan, CommandPending, CommandPlan, CommandPending] == [type(command_record) for command_record in command_records.get_slice(0, 4)]
    command_records.make_pendings_planned([id_2, id_4])
    assert [CommandPlan, CommandPlan, CommandPlan, CommandPlan] == [type(command_record) for command_record in command_records.get_slice(0, 4)]

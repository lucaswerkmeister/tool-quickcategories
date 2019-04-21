from batch import OpenBatch, ClosedBatch
from command import CommandNoop
from in_memory import InMemoryStore
from localuser import LocalUser

from test_batch import newBatch1
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
    assert open_batch.local_user == LocalUser('Lucas Werkmeister', 'commons.wikimedia.org', 6198807, 46054761)
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

# TODO add tests for InMemoryStore start_background + stop_background + make_plan_pending_background

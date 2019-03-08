from store import InMemoryStore

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

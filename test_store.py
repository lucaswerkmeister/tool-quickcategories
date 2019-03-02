from store import InMemoryStore

from test_batch import newBatch1


def test_InMemoryStore_store_batch_command_ids():
    open_batch = InMemoryStore().store_batch(newBatch1)
    assert len(open_batch.command_plans.keys()) == 2

def test_InMemoryStore_store_batch_batch_ids():
    store = InMemoryStore()
    open_batch_1 = store.store_batch(newBatch1)
    open_batch_2 = store.store_batch(newBatch1)
    assert open_batch_1.id != open_batch_2.id

def test_InMemoryStore_get_batch():
    store = InMemoryStore()
    open_batch = store.store_batch(newBatch1)
    assert open_batch is store.get_batch(open_batch.id)

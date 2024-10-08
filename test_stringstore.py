import pymysql
import pytest
from typing import cast

from stringstore import StringTableStore


@pytest.mark.parametrize('string, expected_hash', [
    # all hashes obtained in MariaDB via SELECT CAST(CONV(SUBSTRING(SHA2(**string**, 256), 1, 8), 16, 10) AS unsigned int);
    ('', 3820012610),
    ('test.wikipedia.org', 3277830609),
    ('äöü', 3157433791),
    ('☺', 3752208785),
    ('🤔', 1622577385),
])
def test_StringTableStore_hash(string: str, expected_hash: int) -> None:
    store = StringTableStore('', '', '', '')

    actual_hash = store._hash(string)

    assert expected_hash == actual_hash

def test_StringTableStore_acquire_id_database(database_connection_params: dict) -> None:
    connection = pymysql.connect(**database_connection_params)
    try:
        store = StringTableStore('domain', 'domain_id', 'domain_hash', 'domain_name')

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

def test_StringTableStore_acquire_id_cached() -> None:
    store = StringTableStore('', '', '', '')

    with store._cache_lock:
        store._cache['test.wikipedia.org'] = 1

    connection = cast(pymysql.connections.Connection, None)
    assert store.acquire_id(connection, 'test.wikipedia.org') == 1

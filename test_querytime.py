import datetime
import freezegun  # type: ignore
import pymysql
import pytest  # type: ignore
from typing import Any, Iterator, Tuple, cast

from querytime import QueryTimingCursor, QueryTimingSSCursor, flush_querytime, slow_queries, query_summary, _querytext_store, _query_times
from timestamp import now, utc_timestamp_to_datetime


@pytest.fixture(autouse=True)
def clean_querytime() -> Iterator[None]:
    with _querytext_store._cache_lock:
        _querytext_store._cache.clear()
    _query_times.clear()
    yield
    with _querytext_store._cache_lock:
        _querytext_store._cache.clear()
    _query_times.clear()


@pytest.fixture(params=[QueryTimingCursor, QueryTimingSSCursor])
def database_connection_params_with_cursorclass(database_connection_params: dict, request: Any) -> Iterator[dict]:
    params = database_connection_params.copy()
    params['cursorclass'] = request.param
    yield params


def test_QueryTimingCursor_no_write_without_flush(database_connection_params_with_cursorclass: dict) -> None:
    connection = pymysql.connect(**database_connection_params_with_cursorclass)
    with connection.cursor() as cursor:
        cursor.execute('''SELECT 1''')
    # no flush
    with connection.cursor() as cursor:
        cursor.execute('''SELECT COUNT(*) AS `count`
                          FROM `querytime`''')
        assert cursor.fetchone() == (0,)
        cursor.execute('''SELECT COUNT(*) AS `count`
                          FROM `querytext`''')
        assert cursor.fetchone() == (0,)

def test_flush_querytime(database_connection_params_with_cursorclass: dict) -> None:
    with freezegun.freeze_time(utc_timestamp_to_datetime(1557340918)):
        connection = pymysql.connect(**database_connection_params_with_cursorclass)
        with connection.cursor() as cursor:
            cursor.execute('''SELECT 1''')
        flush_querytime(connection)
    with connection.cursor() as cursor:
        cursor.execute('''SELECT querytime_utc_timestamp, querytext_sql, querytime_duration
                          FROM `querytime`
                          JOIN `querytext` ON `querytime_querytext` = `querytext_id`''')
        timestamp, sql, duration = cast(Tuple[Any, ...], cursor.fetchone())
        assert timestamp == 1557340918
        assert sql == '''SELECT 1'''
        assert cursor.fetchone() is None

def test_flush_querytime_twice_records_querytime_times(database_connection_params_with_cursorclass: dict) -> None:
    connection = pymysql.connect(**database_connection_params_with_cursorclass)
    with connection.cursor() as cursor:
        cursor.execute('''SELECT 1''')
    flush_querytime(connection)
    flush_querytime(connection)
    with connection.cursor() as cursor:
        cursor.execute('''SELECT COUNT(*) AS `count`
                          FROM `querytime`
                          JOIN `querytext` ON `querytime_querytext` = `querytext_id`
                          WHERE `querytext_sql` LIKE '%querytime%\'''')
        (count,) = cast(Tuple[Any, ...], cursor.fetchone())
        assert count > 0

def test_slow_queries(database_connection_params: dict) -> None:
    # three expensive queries
    _query_times.append((now(), '''SELECT "1 second"''', 1.0))
    _query_times.append((now(), '''SELECT "3 seconds"''', 3.0))
    _query_times.append((now(), '''SELECT "2.5 seconds"''', 2.5))
    # loads of cheap queries
    for i in range(500):
        _query_times.append((now(), '''SELECT "0.01 seconds"''', 0.01))
    # queries outside the range
    _query_times.append((now() - datetime.timedelta(days=30), '''SELECT "too long ago"''', 1.0))
    _query_times.append((now() + datetime.timedelta(days=30), '''SELECT "in the future?"''', 1.0))
    # write them out
    connection = pymysql.connect(**database_connection_params)
    flush_querytime(connection)

    queries = slow_queries(connection,
                           since=now() - datetime.timedelta(days=7),
                           until=now() + datetime.timedelta(days=7))
    assert len(queries) == 50
    assert queries[0][1] == 3.0
    assert queries[0][2] == '''SELECT "3 seconds"'''
    assert queries[1][1] == 2.5
    assert queries[1][2] == '''SELECT "2.5 seconds"'''
    assert queries[2][1] == 1.0
    assert queries[2][2] == '''SELECT "1 second"'''
    for i in range(3, 50):
        assert queries[i][1] == 0.01
        assert queries[i][2] == '''SELECT "0.01 seconds"'''

def test_query_summary(database_connection_params: dict) -> None:
    _query_times.append((now(), '''SELECT "query 1"''', 1.0))
    _query_times.append((now(), '''SELECT "query 2"''', 1.0))
    _query_times.append((now(), '''SELECT "query 1"''', 3.0))
    _query_times.append((now(), '''SELECT "query 2"''', 3.0))
    _query_times.append((now(), '''SELECT "query 1"''', 8.0))
    connection = pymysql.connect(**database_connection_params)
    flush_querytime(connection)

    summary = query_summary(connection,
                            since=now() - datetime.timedelta(days=7),
                            until=now() + datetime.timedelta(days=7))
    assert summary == [
        ('''SELECT "query 1"''', {'count': 3, 'avg': 4.0, 'min': 1.0, 'max': 8.0, 'sum': 12.0}),
        ('''SELECT "query 2"''', {'count': 2, 'avg': 2.0, 'min': 1.0, 'max': 3.0, 'sum': 4.0}),
    ]

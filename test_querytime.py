import freezegun # type: ignore
import pymysql
import pytest # type: ignore

from querytime import QueryTimingCursor, flush_querytime, _querytext_store, _query_times
from timestamp import utc_timestamp_to_datetime


@pytest.fixture(autouse=True)
def clean_querytime():
    with _querytext_store._cache_lock:
        _querytext_store._cache.clear()
    _query_times.clear()
    yield
    with _querytext_store._cache_lock:
        _querytext_store._cache.clear()
    _query_times.clear()


def test_QueryTimingCursor_no_write_without_flush(database_connection_params):
    connection = pymysql.connect(cursorclass=QueryTimingCursor,
                                 **database_connection_params)
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

def test_flush_querytime(database_connection_params):
    with freezegun.freeze_time(utc_timestamp_to_datetime(1557340918)):
        connection = pymysql.connect(cursorclass=QueryTimingCursor,
                                     **database_connection_params)
        with connection.cursor() as cursor:
            cursor.execute('''SELECT 1''')
        flush_querytime(connection)
    with connection.cursor() as cursor:
        cursor.execute('''SELECT querytime_utc_timestamp, querytext_sql, querytime_duration
                          FROM `querytime`
                          JOIN `querytext` ON `querytime_querytext` = `querytext_id`''')
        timestamp, sql, duration = cursor.fetchone()
        assert timestamp == 1557340918
        assert sql == '''SELECT 1'''
        assert cursor.fetchone() is None

def test_flush_querytime_twice_records_querytime_times(database_connection_params):
    connection = pymysql.connect(cursorclass=QueryTimingCursor,
                                 **database_connection_params)
    with connection.cursor() as cursor:
        cursor.execute('''SELECT 1''')
    flush_querytime(connection)
    flush_querytime(connection)
    with connection.cursor() as cursor:
        cursor.execute('''SELECT COUNT(*) AS `count`
                          FROM `querytime`
                          JOIN `querytext` ON `querytime_querytext` = `querytext_id`
                          WHERE `querytext_sql` LIKE '%querytime%\'''')
        (count,) = cursor.fetchone()
        assert count > 0

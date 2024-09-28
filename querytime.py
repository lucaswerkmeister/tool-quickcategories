from collections.abc import Iterable
import datetime
from pymysql.connections import Connection
from pymysql.cursors import Cursor, SSCursor
import time
from typing import Any, Optional

from stringstore import StringTableStore
from timestamp import now, datetime_to_utc_timestamp, utc_timestamp_to_datetime


_querytext_store = StringTableStore('querytext',
                                    'querytext_id',
                                    'querytext_hash',
                                    'querytext_sql')


_query_times: list[tuple[datetime.datetime, str, float]] = []


class QueryTimingCursor(Cursor):
    """A cursor that records query execution time.

       Query times are buffered in memory,
       and should be flushed out to the database
       by periodic calls to the flush_querytime function.
       Don’t call it too frequently, though,
       because the query used by that function is also timed.

       Only unmogrified queries (without interpolated arguments) are stored."""

    def __init__(self, connection: Connection) -> None:
        super().__init__(connection)
        self._in_executemany = False

    def execute(self, query: str, args: Optional[Any] = None) -> int:
        if self._in_executemany:
            return super().execute(query, args)
        begin = time.time()
        ret = super().execute(query, args)
        end = time.time()
        _query_times.append((now(), query, end-begin))
        return ret

    def executemany(self, query: str, args: Iterable[Any]) -> Optional[int]:
        self._in_executemany = True
        try:
            begin = time.time()
            ret = super().executemany(query, args)
            end = time.time()
            _query_times.append((now(), query, end-begin))
            return ret
        finally:
            self._in_executemany = False


class QueryTimingSSCursor(QueryTimingCursor, SSCursor):
    """An unbuffered cursor that records query execution time."""


def flush_querytime(connection: Connection) -> None:
    query_times = _query_times.copy()
    _query_times.clear()
    querytime_values: list[tuple[int, int, float]] = []
    for dt, query, duration in query_times:
        utc_timestamp = datetime_to_utc_timestamp(dt)
        query_id = _querytext_store.acquire_id(connection, query)
        querytime_values.append((utc_timestamp, query_id, duration))
    if not querytime_values:
        return
    with connection.cursor() as cursor:
        cursor.executemany('''INSERT INTO `querytime`
                              (`querytime_utc_timestamp`, `querytime_querytext`, `querytime_duration`)
                              VALUES (%s, %s, %s)''',
                           querytime_values)
    connection.commit()


def slow_queries(connection: Connection, since: datetime.datetime, until: datetime.datetime) -> list[tuple[datetime.datetime, float, str]]:
    with connection.cursor() as cursor:
        cursor.execute('''SELECT `querytime_utc_timestamp`, `querytime_duration`, `querytext_sql`
                          FROM `querytime`
                          JOIN `querytext` ON `querytime_querytext` = `querytext_id`
                          WHERE `querytime_utc_timestamp` >= %s
                          AND `querytime_utc_timestamp` < %s
                          ORDER BY `querytime_duration` DESC
                          LIMIT 50''',
                       (datetime_to_utc_timestamp(since), datetime_to_utc_timestamp(until)))
        ret: list[tuple[datetime.datetime, float, str]] = []
        for utc_timestamp, duration, sql in cursor.fetchall():
            ret.append((utc_timestamp_to_datetime(utc_timestamp), duration, sql))
        return ret


def query_summary(connection: Connection, since: datetime.datetime, until: datetime.datetime) -> list[tuple[str, dict[str, float | int]]]:
    with connection.cursor() as cursor:
        cursor.execute('''SELECT `querytext_sql`,
                          COUNT(*) AS `count`,
                          AVG(`querytime_duration`) AS `avg`,
                          MIN(`querytime_duration`) AS `min`,
                          MAX(`querytime_duration`) AS `max`,
                          SUM(`querytime_duration`) AS `sum`
                          FROM `querytime`
                          JOIN `querytext` ON `querytime_querytext` = `querytext_id`
                          WHERE `querytime_utc_timestamp` >= %s
                          AND `querytime_utc_timestamp` < %s
                          GROUP BY `querytext_sql`''',
                       (datetime_to_utc_timestamp(since), datetime_to_utc_timestamp(until)))
        summary = [(sql, {'count': count, 'avg': avg, 'min': min, 'max': max, 'sum': sum})
                   for sql, count, avg, min, max, sum in cursor.fetchall()]
    summary.sort(key=lambda result: result[1]['avg'], reverse=True)
    return summary

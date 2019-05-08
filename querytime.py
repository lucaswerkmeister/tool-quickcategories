import datetime
from pymysql.connections import Connection
from pymysql.cursors import Cursor
import time
from typing import Any, List, Optional, Tuple

from stringstore import StringTableStore
from timestamp import now, datetime_to_utc_timestamp


_querytext_store = StringTableStore('querytext',
                                    'querytext_id',
                                    'querytext_hash',
                                    'querytext_sql')


_query_times = [] # type: List[Tuple[datetime.datetime, str, float]]


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

    def executemany(self, query: str, args) -> int:
        self._in_executemany = True
        try:
            begin = time.time()
            ret = super().executemany(query, args)
            end = time.time()
            _query_times.append((now(), query, end-begin))
            return ret
        finally:
            self._in_executemany = False


def flush_querytime(connection: Connection) -> None:
    query_times = _query_times.copy()
    _query_times.clear()
    querytime_values = [] # type: List[Tuple[int, int, float]]
    for dt, query, duration in query_times:
        utc_timestamp = datetime_to_utc_timestamp(dt)
        query_id = _querytext_store.acquire_id(connection, query)
        querytime_values.append((utc_timestamp, query_id, duration))
    with connection.cursor() as cursor:
        cursor.executemany('''INSERT INTO `querytime`
                              (`querytime_utc_timestamp`, `querytime_querytext`, `querytime_duration`)
                              VALUES (%s, %s, %s)''',
                           querytime_values)
    connection.commit()

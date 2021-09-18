import cachetools
from dataclasses import dataclass
import hashlib
import operator
import pymysql
import threading


@dataclass
class StringTableStore:
    """Encapsulates access to a string that has been extracted into a separate table.

    The separate table is expected to have three columns:
    an automatically incrementing ID,
    an unsigned integer hash (the first four bytes of the SHA2-256 hash of the string),
    and the string itself.

    IDs for the least recently used strings are cached,
    but to look up the string for an ID,
    callers should use a plain SQL JOIN for now."""

    table_name: str
    id_column_name: str
    hash_column_name: str
    string_column_name: str

    def __post_init__(self) -> None:
        self._cache: cachetools.LRUCache[str, int] = cachetools.LRUCache(maxsize=1024)
        self._cache_lock = threading.RLock()

    def _hash(self, string: str) -> int:
        hex = hashlib.sha256(string.encode('utf8')).hexdigest()
        return int(hex[:8], base=16)

    @cachetools.cachedmethod(operator.attrgetter('_cache'), key=lambda connection, string: string, lock=operator.attrgetter('_cache_lock'))
    def acquire_id(self, connection: pymysql.connections.Connection, string: str) -> int:
        hash = self._hash(string)

        with connection.cursor() as cursor:
            cursor.execute('''SELECT `%s`
                              FROM `%s`
                              WHERE `%s` = %%s
                              FOR UPDATE''' % (self.id_column_name, self.table_name, self.hash_column_name),
                           (hash,))
            result = cursor.fetchone()
        if result:
            connection.commit()  # finish the FOR UPDATE
            return result[0]

        with connection.cursor() as cursor:
            cursor.execute('''INSERT INTO `%s` (`%s`, `%s`)
                              VALUES (%%s, %%s)''' % (self.table_name, self.string_column_name, self.hash_column_name),
                           (string, hash))
            string_id = cursor.lastrowid
        connection.commit()
        return string_id

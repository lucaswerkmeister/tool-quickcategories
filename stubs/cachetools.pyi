import threading
from typing import Any, Callable, Iterator, MutableMapping, TypeVar


Key = TypeVar('Key')
Value = TypeVar('Value')

class Cache(MutableMapping[Key, Value]):

    def __init__(self, maxsize: int): ...
    def __getitem__(self, key: Key) -> Value: ...
    def __setitem__(self, key: Key, value: Value): ...
    def __delitem__(self, key: Key): ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[Any]: ...

class LRUCache(Cache[Key, Value]):
    pass

class TTLCache(Cache[Key, Value]):

    def __init__(self, maxsize: int, ttl: int): ...

# the ... here all need to be the same (list) type, but apparently mypy doesn’t support a typevar there
def cached(cache: Cache[Key, Value],
           key: Callable[..., Key],
           lock: threading.RLock) -> Callable[[Callable[..., Value]], Callable[..., Value]]:
    ...
def cachedmethod(cache: Callable[[Any], Cache[Key, Value]],
                 key: Callable[..., Key],
                 lock: Callable[[Any], threading.RLock]) -> Callable[[Callable[..., Value]], Callable[..., Value]]:
    ...

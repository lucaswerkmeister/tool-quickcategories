from typing import Any, Iterator, Optional, Tuple, TypeVar

from .connections import Connection


Gen = Tuple[Any, ...] # rather than typeshed’s Union of that with Dict[str, Any]
_SelfT = TypeVar("_SelfT")

class Cursor:
    rowcount: int
    lastrowid: int
    def __init__(self, connection: Connection) -> None: ...
    def execute(self, query: str, args: Optional[Any] = ...) -> int: ...
    def executemany(self, query: str, args) -> int: ...
    def fetchone(self) -> Optional[Gen]: ...
    def fetchall(self) -> Tuple[Gen, ...]: ...
    def __enter__(self: _SelfT) -> _SelfT: ...
    def __exit__(self, *exc_info: Any) -> None: ...


class SSCursor(Cursor):
    def fetchall_unbuffered(self) -> Iterator[Gen]: ...

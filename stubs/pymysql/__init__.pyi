from collections.abc import Callable

from .connections import Connection as _Connection

connect: Callable[..., _Connection]

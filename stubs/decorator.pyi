from collections.abc import Callable
from typing import Any, TypeVar


Ret = TypeVar('Ret')


def decorator(func: Callable[[Callable[..., Ret], list[Any], dict[str, Any]], Ret]) -> Callable[[Callable[..., Ret]], Callable[..., Ret]]:
    ...

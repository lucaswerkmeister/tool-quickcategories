from typing import Any, Callable, Dict, List, TypeVar


Ret = TypeVar('Ret')


def decorator(func: Callable[[Callable[..., Ret], List[Any], Dict[str, Any]], Ret]) -> Callable[[Callable[..., Ret]], Callable[..., Ret]]:
    ...

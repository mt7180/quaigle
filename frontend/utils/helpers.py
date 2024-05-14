import functools
from typing import TypeVar, Generic
from collections.abc import Callable

F = TypeVar("F", bound=Callable[..., None])


class MultiPage(Generic[F]):
    """decorator to register multiple streamlit pages (functions)
    in a registry dict
    """

    registry: dict[str, F] = {}

    def __init__(self, func: F):
        self.func = func
        functools.update_wrapper(self, func)
        self.registry[func.__name__] = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

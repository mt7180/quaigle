from typing import TypeVar
from collections.abc import Callable

F = TypeVar("F", bound=Callable[..., None])


def register_page(page_registry_dict: dict[str, F]) -> Callable[[F], F]:
    """
    Streamlit page decorator (factory) which takes the page registry dict
    as argument and returns the actual decorator, which itself registers
    all decorated page functions automatically in page dict.

    Args:
        page_registry_dict: the dict where to register the page

    Returns:
        Callable: the actual decorator, a callable which takes a callable as
        argument and returns it.
    """

    def inner(func):
        page_registry_dict[func.__name__] = func

    return inner

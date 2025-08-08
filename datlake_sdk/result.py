from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, Union, Any

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")
F = TypeVar("F")

@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

@dataclass(frozen=True)
class Err(Generic[E]):
    error: E

Result = Union[Ok[T], Err[E]]

# Combinators

def map(result: Result[T, E], f: Callable[[T], U]) -> Result[U, E]:
    if isinstance(result, Ok):
        try:
            return Ok(f(result.value))
        except Exception as ex:  # mapping should not normally raise; surface as Err[Any]
            return Err(ex)  # type: ignore[return-value]
    return result  # type: ignore[return-value]


def map_err(result: Result[T, E], f: Callable[[E], F]) -> Result[T, F]:
    if isinstance(result, Err):
        try:
            return Err(f(result.error))
        except Exception as ex:
            return Err(ex)  # type: ignore[return-value]
    return result  # type: ignore[return-value]


def and_then(result: Result[T, E], f: Callable[[T], Result[U, E]]) -> Result[U, E]:
    if isinstance(result, Ok):
        try:
            return f(result.value)
        except Exception as ex:
            return Err(ex)  # type: ignore[return-value]
    return result  # type: ignore[return-value]


def tee(result: Result[T, E], f: Callable[[T], None]) -> Result[T, E]:
    if isinstance(result, Ok):
        try:
            f(result.value)
        except Exception as _:
            pass
    return result


def recover(result: Result[T, E], f: Callable[[E], Result[T, E]]) -> Result[T, E]:
    if isinstance(result, Err):
        try:
            return f(result.error)
        except Exception as ex:
            return Err(ex)
    return result

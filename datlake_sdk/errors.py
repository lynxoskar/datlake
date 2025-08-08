from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class SDKError(Exception):
    message: str
    code: Optional[int] = None

    def __str__(self) -> str:  # pragma: no cover
        return f"SDKError(code={self.code}, message={self.message})"

@dataclass(frozen=True)
class AuthError(SDKError):
    pass

@dataclass(frozen=True)
class NotFound(SDKError):
    pass

@dataclass(frozen=True)
class Conflict(SDKError):
    pass

@dataclass(frozen=True)
class Transient(SDKError):
    pass

@dataclass(frozen=True)
class ServerError(SDKError):
    pass

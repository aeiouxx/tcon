from __future__ import annotations
from typing import TypeVar, Generic
from common.status import AimsunStatus

T = TypeVar("T")


class Result(Generic[T]):
    def __init__(
        self,
        status: AimsunStatus,
        value: T | None = None,
        raw_code: int | None = None,
        message: str | None = None,
    ):
        self.status = status
        self.value = value
        self.raw_code = raw_code
        self.message = message

    @classmethod
    def ok(cls, value: T | None, message: str | None = None) -> "Result[T]":
        """Create a Result that represents success."""
        return cls(status=AimsunStatus.OK, value=value, message=message)

    @classmethod
    def err(cls, message: str, code: int | None = None) -> "Result[None]":
        """Create a Result that represents failure."""
        return cls(status=AimsunStatus.API_FAILURE,
                   raw_code=code,
                   message=message)

    def is_ok(self) -> bool:
        return self.status == AimsunStatus.OK

    def unwrap(self) -> T:
        if not self.is_ok():
            raise RuntimeError("error unwrapped")
        return self.value

    def __repr__(self) -> str:
        return f"Result(status={self.status}, value={self.value}, code={self.raw_code}, msg={self.message})"

    # TODO: hopefully the API is consistent with err values as < 0... (it wasn't)
    @classmethod
    def from_aimsun(cls,
                    result: int, *,
                    msg_ok: str | None = None,
                    msg_err: str | None = None) -> Result[int]:
        success = result >= 0
        status = AimsunStatus.OK if success else AimsunStatus.from_code(result)
        message = (msg_ok if success else msg_err)
        return cls(status=status,
                   raw_code=result,
                   value=result if success else None,
                   message=message)

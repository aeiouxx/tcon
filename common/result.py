from __future__ import annotations
from typing import TypeVar, Generic, Optional
from common.status import AimsunStatus

T = TypeVar("T")


class Result(Generic[T]):
    def __init__(
        self,
        status: AimsunStatus,
        value: Optional[T] = None,
        raw_code: Optional[int] = None,
        message: Optional[str] = None,
    ):
        self.status = status
        self.value = value
        self.raw_code = raw_code
        self.message = message

    def is_ok(self) -> bool:
        return self.status == AimsunStatus.OK

    def unwrap(self) -> T:
        if not self.is_ok():
            raise RuntimeError("error unwrapped")
        return self.value

    def __repr__(self) -> str:
        return f"Result(status={self.status}, value={self.value}, code={self.raw_code}, msg={self.message})"

    # TODO: hopefully the API is consistent with err values as < 0...
    @classmethod
    def from_aimsun(cls,
                    result: int, *,
                    msg_ok: str = None,
                    msg_fail: str = None) -> Result[int]:
        success = result >= 0
        status = AimsunStatus.OK if success else AimsunStatus.from_code(result)
        message = (msg_ok if success else msg_fail)
        return cls(status=status,
                   raw_code=result,
                   value=result if success else None,
                   message=message)

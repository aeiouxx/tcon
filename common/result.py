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


def from_aimsun_code(code: int, *, value: Optional[T] = None, msg: Optional[str] = None) -> Result[T]:
    status = AimsunStatus.from_code(code)
    return Result(status=status, value=value if status == AimsunStatus.OK else None, raw_code=code, message=msg)

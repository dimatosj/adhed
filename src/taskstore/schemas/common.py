from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Meta(BaseModel):
    total: int = 0
    limit: int = 50
    offset: int = 0


class ErrorDetail(BaseModel):
    rule_id: str | None = None
    rule_name: str | None = None
    message: str


class Envelope(BaseModel, Generic[T]):
    data: T | None = None
    meta: Meta | None = None
    errors: list[ErrorDetail] = []
    warnings: list[str] = []

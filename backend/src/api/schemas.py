from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field
from datetime import datetime


T = TypeVar("T")


class BaseResponse(BaseModel):
    success: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseResponse):
    success: bool = False
    error: str
    details: Optional[dict] = None


class ListResponse(BaseResponse, Generic[T]):
    data: List[T]
    total: int
    limit: int = 50
    offset: int = 0


class SingleResponse(BaseResponse, Generic[T]):
    data: T


class PaginatedResponse(BaseResponse, Generic[T]):
    data: List[T]
    total: int
    limit: int
    offset: int
    has_more: bool


class MessageResponse(BaseResponse):
    message: str


class ValidationErrorDetail(BaseModel):
    field: str
    message: str
    type: str


class ValidationErrorResponse(ErrorResponse):
    details: List[ValidationErrorDetail]


# Common response models
class HealthCheckResponse(BaseModel):
    status: str
    checks: dict


class APIInfoResponse(BaseModel):
    message: str
    version: str
    docs: str
from datetime import datetime, timezone
from typing import Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class TimestampedModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IdentifiedModel(TimestampedModel):
    id: str = Field(default_factory=lambda: str(uuid4()))


class MessageResponse(BaseModel):
    message: str


class PingResponse(BaseModel):
    pong: str = "pong"


class Envelope(BaseModel, Generic[T]):
    success: bool = True
    message: str = "success"
    data: T | None = None

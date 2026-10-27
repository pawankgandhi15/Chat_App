from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EventBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = 1
    container_id: str = Field(min_length=1, max_length=64)
    user: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")
    sent_at: str = Field(pattern=r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")

    @field_validator("sent_at")
    @classmethod
    def real_timestamp(cls, value):
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value


UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


class SessionEvent(EventBase):
    type: Literal["session"] = "session"
    connection_id: str = Field(pattern=UUID4)


class BroadcastEvent(EventBase):
    type: Literal["chat", "system"]
    event_id: str = Field(pattern=UUID4)
    text: str = Field(min_length=1, max_length=2000)
    time: str = Field(pattern=r"^\d\d:\d\d:\d\d UTC$")


def session_event(user: str, replica: str, connection_id: str) -> str:
    return SessionEvent(user=user, container_id=replica, connection_id=connection_id,
                        sent_at=timestamp()).model_dump_json()


def broadcast_event(kind: Literal["chat", "system"], user: str, text: str, replica: str) -> str:
    now = timestamp()
    return BroadcastEvent(type=kind, user=user, text=text, container_id=replica,
                          event_id=str(uuid4()), sent_at=now,
                          time=now[11:19] + " UTC").model_dump_json()

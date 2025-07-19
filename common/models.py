from __future__ import annotations
from enum import Enum
from typing import Annotated
from pydantic import BaseModel, Field, Validator


class CommandType(str, Enum):
    PING = "ping"
    INCIDENT_CREATE = "incident_create"
    INCIDENT_CANCEL = "incident_cancel"


# TODO: stuff
class Incident(BaseModel):
    """Represents an incident to be generated"""


class Command(BaseModel):
    type: CommandType
    payload: dict | Incident | None = None

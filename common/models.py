from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class CommandType(str, Enum):
    PING = "ping"
    INCIDENT_CREATE = "incident_create"
    INCIDENT_CANCEL = "incident_cancel"


"""
For API we want the following:
    1. ability to invoke incident(s)
    2. ability to cancel ongoing incident(s)
    3. ability to implement traffic measures
    4. ability to cancel traffic measures

* Perhaps the ability to send whole definition at once?
"""

# TODO: stuff


class Incident(BaseModel):
    """Represents an incident to be generated"""


# TODO:
class Command(BaseModel):
    type: CommandType
    payload: dict | Incident | None = None

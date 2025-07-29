from __future__ import annotations
from enum import Enum
from typing import NamedTuple, Annotated, Literal, Union
from pydantic import BaseModel, Field, ValidationError, ConfigDict, field_validator, model_validator, PydanticCustomError

# INCIDENTS: https://docs.aimsun.com/next/23.0.2/UsersManual/ApiIncidents.html
# MEASURES:  https://docs.aimsun.com/next/23.0.2/UsersManual/ApiManagementActions.html


# > Command ----------------------------------------------------------
class CommandType(str, Enum):
    INCIDENT_CREATE = "incident_create"
    INCIDENT_REMOVE = "incident_remove"
    INCIDENTS_CLEAR_SECTION = "incidents_clear_section"
    INCIDENTS_RESET = "incidents_reset"
    # First let's test double indirection as measures
    # will have custom scheduling in common as they can't be
    # scheduled via the API
    MEASURE_CREATE = "measure_create"
    MEASURE_REMOVE = "measure_remove"
    MEASURES_CLEAR = "measures_clear"


class Command(BaseModel):
    type: CommandType
    payload: dict | None
# < Command ----------------------------------------------------------


# > Utilities ----------------------------------------------------------
_COMMAND_REGISTRY: dict[CommandType, type[BaseModel]] = {}
_DTO_TO_TYPE: dict[type[BaseModel], CommandType] = {}


def get_command_type(dto_cls: type[BaseModel]) -> CommandType | None:
    return _DTO_TO_TYPE.get(dto_cls)


def get_payload_cls(type: CommandType) -> type[BaseModel] | None:
    return _COMMAND_REGISTRY.get(type)


def register_command(type: CommandType):
    def decorator(cls: type[BaseModel]):
        if type not in _COMMAND_REGISTRY:
            _COMMAND_REGISTRY[type] = cls
            _DTO_TO_TYPE[cls] = type
        return cls
    return decorator
# < Utilities ----------------------------------------------------------


# > Incidents ----------------------------------------------------------
@register_command(CommandType.INCIDENT_CREATE)
class IncidentCreateDto(BaseModel):
    """Incident to be generated"""
    section_id: int = Field(...,
                            description="Identifier of the section of the incident")
    lane: int = Field(...,
                      description="Lane number (1-indexed) where the incident occurs",
                      gt=0)
    position: float = Field(
        ..., description="Position (distance from section start) of the incident")
    length: float = Field(..., description="Length of the incident")
    ini_time: float = Field(
        ..., description="Time of the simulation, in seconds from midnight, when the incident will start")
    duration: float = Field(...,
                            description="Duration of the incident (seconds).")
    visibility_distance: float = Field(
        default=200, description="Visibility distance in meters of the incident to be used in Aimsun 7.0 models.")
    update_id_group: bool = Field(
        default=False, description="True when the incident is a new group of incidents and False if the incidents is to be treated as a part of the last created incident (when creating incidents in adjacent lanes that need to be treated as a whole).")
    apply_speed_reduction: bool = Field(
        default=True, description="True to apply a speed reduction around the incident to slow vehicles as they pass it and False otherwise")
    upstream_distance_SR: float = Field(
        default=200, description="If the reduction is to be applied, the distance upstream of the incident")
    downstream_distance_SR: float = Field(
        default=200, description="If the reduction is to be applied, the distance downstream of the incident")
    max_speed_SR: float = Field(
        default=50, description="If the reduction is to be applied, the target reduced speed")


@register_command(CommandType.INCIDENT_REMOVE)
class IncidentRemoveDto(BaseModel):
    section_id: int = Field(
        ..., description="Identifier of the section where the incident to remove is located")
    lane: int = Field(...,
                      description="Lane where the incident will be generated")
    position: float = Field(
        ..., description="Position of the incident in the section (from the beginning of the section).")


@register_command(CommandType.INCIDENTS_CLEAR_SECTION)
class IncidentsClearSectionDto(BaseModel):
    section_id: int = Field(
        ..., description="Identifier of the section to clear of incidents")
# < Incidents ----------------------------------------------------------


# > Measure --------------------------------------------------------------------
class MeasureType(str, Enum):
    """
    Enumerates supported traffic‑management actions
    """
    # Because we're in Python we have to supply the ID for each action
    # which makes integration with REST tricky
    # (we will either autogenerate the ID or user will provide one which can result in async errors).
    # This mechanism also makes integration with decision making software subpar as we only
    # cancel actions based on time, more sophisticated implementation should use C++ anyway
    # as some actions aren't even supported in Python
    SPEED_SECTION = "speed_section"                     # AKIActionAddSpeedSectionById
    SPEED_DETAILED = "detailed_speed"                   # AKIActionAddDetailedSpeedById
    LANE_CLOSURE = "lane_closure"                       # AKIActionAddLaneClosureById
    LANE_CLOSURE_DETAILED = "detailed_lane_closure"     # AKIActionAddDetailedLaneClosureById

    # AKIActionAddNextTurningResultActionByID => when traffic demand is based on traffic states
    # AKIActionAddNextTurningODActionByID => when traffic demand is based on OD matrices
    FORCE_TURN = "force_turn"


class _MeasureBase(BaseModel):
    id_action: int = Field(default=-1,
                           description="Preallocate the ID only if you know what you're doing")
    ini_time: float | None
    duration: float | None


class MeasureSpeedSection(_MeasureBase):
    type: Literal[MeasureType.SPEED_SECTION] = MeasureType.SPEED_SECTION


class MeasureSpeedDetailed(_MeasureBase):
    type: Literal[MeasureType.SPEED_DETAILED] = MeasureType.SPEED_DETAILED


class MeasureLaneClosure(_MeasureBase):
    type: Literal[MeasureType.LANE_CLOSURE] = MeasureType.LANE_CLOSURE


class MeasureLaneClosureDetailed(_MeasureBase):
    type: Literal[MeasureType.LANE_CLOSURE_DETAILED] = MeasureType.LANE_CLOSURE_DETAILED


class MeasureForceTurn(_MeasureBase):
    type: Literal[MeasureType.FORCE_TURN] = MeasureType.FORCE_TURN


MeasurePayload = Annotated[
    Union[MeasureSpeedSection, MeasureSpeedDetailed, MeasureLaneClosure, MeasureLaneClosureDetailed, MeasureForceTurn],
    Field(discriminator="type")]


@register_command(CommandType.MEASURE_CREATE)
class MeasureCreateDto(MeasurePayload):
    __root__: MeasurePayload  # define as a thin wrapper around the actual thing

    @property
    def measure(self) -> MeasurePayload:
        return self.__root__


@register_command(CommandType.MEASURE_REMOVE)
class MeasureRemoveDto(BaseModel):
    id_action: int = Field(...,
                           description="ID of the measure to remove",
                           gt=0)

# < Measure --------------------------------------------------------------------


# > Scheduled command ----------------------------------------------------------
class ScheduledCommand(BaseModel):
    """Represents a scheduled command loaded from configuration.

    Attributes
    ----------
    command:
        The command type corresponding to ``CommandType``. Must match one
        of the known command identifiers such as ``incident_create`` or
        ``measure_create``.
    time:
        Simulation time (seconds from midnight) at which to execute the
        command. Events are executed when the current simulation time is
        greater than or equal to this value.
    payload:
        Arbitrary payload dictionary. The structure depends on the
        command type. It is passed to the handler unchanged.
    """
    command: CommandType
    time: float = Field(default=-1,
                        description="Sim-time in seconds from midnight,"
                        "omit or set to -1 for measures that"
                        "shouldn't be automatically terminated")
    payload: dict | BaseModel = Field(...,
                                      description="Payload as a DTO or a raw dict")

    @field_validator("payload")
    @classmethod
    def _cast_payload(cls, v, info):
        if isinstance(v, BaseModel):
            return v
        model_cls = get_payload_cls(info.data["command"])
        return model_cls.model_validate(v) if model_cls else v

    @model_validator(mode="after")
    def _ini_must_follow_schedule(self):
        ini_time = getattr(self.payload, "ini_time", None)
        if ini_time is not None and ini_time <= self.time:
            raise PydanticCustomError(
                "ini_time_before_schedule",
                "payload.ini_time ({ini_time}) must be greater than "
                "schedule.time ({scheduled_time})",
                {"ini_time": ini_time, "scheduled_time": self.time})
        return self

# simple v


class ScheduleRoot(BaseModel):
    __root__: list[ScheduledCommand]
# < Scheduled command ----------------------------------------------------------

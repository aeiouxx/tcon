from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class CommandType(str, Enum):
    INCIDENT_CREATE = "incident_create"
    INCIDENT_REMOVE = "incident_remove"
    INCIDENTS_CLEAR_SECTION = "incidents_clear_section"
    INCIDENTS_RESET = "incidents_reset"
    MEASURE_CREATE = "measure_create"
    MEASURE_REMOVE = "measure_remove"


class Command(BaseModel):
    type: CommandType
    payload: dict | None


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

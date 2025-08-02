from __future__ import annotations
from enum import Enum

from typing import (Annotated, Literal, Union,  ClassVar)

from pydantic import (
    RootModel,
    BaseModel,
    Field,
    field_validator,
    model_validator)

from pydantic_core import PydanticCustomError

# INCIDENTS: https://docs.aimsun.com/next/23.0.2/UsersManual/ApiIncidents.html
# MEASURES:  https://docs.aimsun.com/next/23.0.2/UsersManual/ApiManagementActions.html

# FIXME: Apparently theres a simpler dispatch in the stdlib, rework our
# registration mechanisms?


# > Enums ---------------------------------------------------------------------
class CommandType(str, Enum):
    INCIDENT_CREATE = "incident_create"
    INCIDENT_REMOVE = "incident_remove"
    INCIDENTS_CLEAR_SECTION = "incidents_clear_section"
    INCIDENTS_RESET = "incidents_reset"
    MEASURE_CREATE = "measure_create"
    MEASURE_REMOVE = "measure_remove"
    MEASURES_CLEAR = "measures_clear"


class MeasureType(str, Enum):
    """
    Enumerates supported traffic‑management actions
    """
    SPEED_SECTION = "speed_section"
    SPEED_DETAILED = "speed_detailed"
    LANE_CLOSURE = "lane_closure"
    LANE_CLOSURE_DETAILED = "lane_closure_detailed"
    LANE_DEACTIVATE_RESERVED = "lane_deactivate_reserved"
    TURN_CLOSE = "turn_close"
    TURN_FORCE = "turn_force"

# < Enums ----------------------------------------------------------


# > Incidents -----------------------------------------------------------------
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


class IncidentRemoveDto(BaseModel):
    section_id: int = Field(...,
                            description="Identifier of the section where the incident to remove is located")
    lane: int = Field(...,
                      description="Lane where the incident will be generated")
    position: float = Field(...,
                            description="Position of the incident in the section (from the beginning of the section).")


class IncidentsClearSectionDto(BaseModel):
    section_id: int = Field(...,
                            description="Identifier of the section to clear of incidents")
# < Incidents -----------------------------------------------------------------

# > Measures --------------------------------------------------------------------


class _MeasureBase(BaseModel):
    id_action: int | None = Field(default=None,
                                  description="Preallocate the ID only if you know what you're doing, otherwise omit this field")
    duration: float | None = Field(default=None,
                                   description="If set, automatically generate cancellation command for the action")


class MeasureSpeedSection(_MeasureBase):
    """
    Changes the speed limit in one or many sections.
    Calls the AKIActionAddSpeedSectionById API function.
    """
    type: Literal[MeasureType.SPEED_SECTION] = MeasureType.SPEED_SECTION
    section_ids: list[int] = Field(...,
                                   min_length=1,
                                   description="List of section IDs to apply measure to")
    speed: float = Field(...,
                         gt=0,
                         description="Target speed (km/h")
    veh_type: int = Field(default=0,
                          ge=0,
                          description="0 = all vehicles, 1..N specific vehicle types")
    compliance: float = Field(default=1.0,
                              ge=0.0,
                              le=1.0,
                              description="Share of drivers obeying the measure <0-1>")
    consider_speed_acceptance: bool = Field(default=True,
                                            description="False -> override speed acceptance factor")


class MeasureSpeedDetailed(_MeasureBase):
    type: Literal[MeasureType.SPEED_DETAILED] = MeasureType.SPEED_DETAILED
    section_ids: list[int] = Field(...,
                                   min_length=1,
                                   description="List of section IDs to apply measure to")
    lane_id: int = Field(default=-1,
                         description="The lane identifier (-1 for all lanes, 1 for the rightmost lane"
                         "and N, where N is the number of lanes in the section, for the leftmost lane")
    from_segment_id: int = Field(default=-1,
                                 description="-1 for all the segments, "
                                 "1 for the first segment the vehicles face when crossing the section, "
                                 "and N, where N is the number of segments, "
                                 "for the last segment the vehicles face when crossing the section")
    to_segment_id: int = Field(default=-1,
                               description="-1 for all the segments, "
                               "1 for the first segment the vehicles face when crossing the section, "
                               "and N, where N is the number of segments, "
                               "for the last segment the vehicles face when crossing the section")
    speed: float = Field(...,
                         gt=0,
                         description="Target speed (km/h")
    veh_type: int = Field(default=0,
                          ge=0,
                          description="0 = all vehicles, 1..N specific vehicle types")
    compliance: float = Field(default=1.0,
                              ge=0.0,
                              le=1.0,
                              description="Share of drivers obeying the measure <0-1>")
    consider_speed_acceptance: bool = Field(default=True,
                                            description="False -> override speed acceptance factor")


class MeasureLaneClosure(_MeasureBase):
    type: Literal[MeasureType.LANE_CLOSURE] = MeasureType.LANE_CLOSURE
    section_id: int = Field(..., description="Identifier of the section to apply action to")
    lane_id: int = Field(..., description="Identifier of the lane to apply action to")
    veh_type: int = Field(default=0,
                          ge=0,
                          description="0 = all vehicles, 1..N specific vehicle types")


class MeasureLaneClosureDetailed(_MeasureBase):
    type: Literal[MeasureType.LANE_CLOSURE_DETAILED] = MeasureType.LANE_CLOSURE_DETAILED
    section_id: int = Field(..., description="Identifier of the section to apply action to")
    lane_id: int = Field(..., description="Identifier of the lane to apply action to")
    veh_type: int = Field(default=0,
                          ge=0,
                          description="0 = all vehicles, 1..N specific vehicle types")
    apply_2LCF: bool = Field(default=False,
                             description="True if the 2-lanes car following model is to be considered")
    visibility_distance: float = Field(default=200,
                                       description="The distance at which the lane closure will start to be visible for vehicles")


class MeasureLaneDeactivateReserved(_MeasureBase):
    type: Literal[MeasureType.LANE_DEACTIVATE_RESERVED] = MeasureType.LANE_DEACTIVATE_RESERVED
    section_id: int = Field(..., description="Identifier of the section to apply action to")
    lane_id: int = Field(..., description="Identifier of the lane to apply action to")
    segment_id: int = Field(default=-1,
                            description="0..N-1 where N is number of segments present within section or -1 to apply to all segments.")


# TODO: For OD matrices only?
class MeasureTurnClose(_MeasureBase):
    type: Literal[MeasureType.TURN_CLOSE] = MeasureType.TURN_CLOSE
    from_section_id: int = Field(..., description="Turn origin section identifier.")
    to_section_id: int = Field(..., description="Turn destination section identifier.")
    origin_centroid:  int = Field(
        default=-1, description="Centroid origin identifier, -1 means do not consider origin with set compliance")
    destination_centroid:  int = Field(
        default=-1, description="Centroid destination identifier, -1 means do not consider destination with set compliance")
    veh_type: int = Field(default=0,
                          ge=0,
                          description="0 = all vehicles, 1..N specific vehicle types")
    compliance: float = Field(default=1.0,
                              ge=0.0,
                              le=1.0,
                              description="Share of drivers obeying the measure <0-1>")
    visibility_distance: float = Field(default=200,
                                       description="The distance at which the lane closure will start to be visible for vehicles")
    local_effect: bool = Field(default=True,
                               description="If vehicles do not have apriori knowledge of closure - true, else global knowledge")
    section_affecting_path_cost_id: int = Field(default=-1,
                                                description="Identifier to the section meant to affect the path calculation cost when the path comes from it")


class MeasureTurnForce(_MeasureBase):
    type: Literal[MeasureType.TURN_FORCE] = MeasureType.TURN_FORCE


MeasurePayload = Annotated[
    Union[
        MeasureSpeedSection,
        MeasureSpeedDetailed,
        MeasureLaneClosure,
        MeasureLaneClosureDetailed,
        MeasureLaneDeactivateReserved,
        MeasureTurnClose,
        MeasureTurnForce
    ],
    Field(discriminator="type")]


class MeasureCreateDto(RootModel[MeasurePayload]):
    @property
    def measure(self) -> MeasurePayload:
        return self.root


class MeasureRemoveDto(BaseModel):
    id_action: int = Field(...,
                           description="ID of the measure to remove",
                           gt=0)

# < Measures --------------------------------------------------------------------


# > Command Wrappers ------------------------------------------------------------
class CommandBase(BaseModel):
    IMMEDIATE: ClassVar[float] = -1

    command: CommandType
    time: float = Field(default=IMMEDIATE,
                        description="Sim-time in seconds from midnight,"
                        f"omit or set to {IMMEDIATE} to run as soon as possible")


class IncidentCreateCmd(CommandBase):
    command: Literal[CommandType.INCIDENT_CREATE] = CommandType.INCIDENT_CREATE
    payload: IncidentCreateDto

    @model_validator(mode="after")
    def _ini_after_time(self):
        if self.payload.ini_time <= self.time:
            raise PydanticCustomError(
                "ini_time_before_schedule",
                "payload.ini_time ({ini_time}) must be greater than "
                "schedule.time ({scheduled_time})",
                {
                    "ini_time": self.payload.ini_time,
                    "scheduled_time": self.time,
                },
            )
        return self


class IncidentRemoveCmd(CommandBase):
    command: Literal[CommandType.INCIDENT_REMOVE] = CommandType.INCIDENT_REMOVE
    payload: IncidentRemoveDto


class IncidentsClearSectionCmd(CommandBase):
    command: Literal[CommandType.INCIDENTS_CLEAR_SECTION] = CommandType.INCIDENTS_CLEAR_SECTION
    payload: IncidentsClearSectionDto


class IncidentsResetCmd(CommandBase):
    command: Literal[CommandType.INCIDENTS_RESET] = CommandType.INCIDENTS_RESET
    payload: None = Field(default=None)


class MeasureCreateCmd(CommandBase):
    command: Literal[CommandType.MEASURE_CREATE] = CommandType.MEASURE_CREATE
    payload: MeasureCreateDto


class MeasureRemoveCmd(CommandBase):
    command: Literal[CommandType.MEASURE_REMOVE] = CommandType.MEASURE_REMOVE
    payload: MeasureRemoveDto


class MeasuresClearCmd(CommandBase):
    command: Literal[CommandType.MEASURES_CLEAR] = CommandType.MEASURES_CLEAR
    payload: None = Field(default=None)


Command = Annotated[
    Union[
        IncidentCreateCmd,
        IncidentRemoveCmd,
        IncidentsClearSectionCmd,
        IncidentsResetCmd,
        MeasureCreateCmd,
        MeasureRemoveCmd,
        MeasuresClearCmd
    ],
    Field(discriminator="command")]
# < Command Wrappers ------------------------------------------------------------


class ScheduleRoot(RootModel[list[Command]]):
    pass
# < Scheduled command ----------------------------------------------------------

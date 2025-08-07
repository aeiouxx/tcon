from __future__ import annotations
from enum import Enum

from typing import (Annotated, Literal, Union,  ClassVar)
from math import isclose

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
    MEASURES_RESET = "measures_reset"
    POLICY_ACTIVATE = "policy_activate"
    POLICY_DEACTIVATE = "policy_deactivate"


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
    TURN_FORCE_OD = "turn_force_od"
    TURN_FORCE_RESULT = "turn_force_result"
    DESTINATION_CHANGE = "destination_change"

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


class _MeasureTurnForceBase(_MeasureBase):
    """
        Force the next turning movement of the vehicle on a section.
        We use the same DTO to represent both measures for OD matrices and
        traffic state objects.
    """
    from_section_id: int = Field(...,
                                 description="Section where the forced turn begins")
    next_section_ids: list[int] = Field(...,
                                        min_length=1,
                                        description="One or more candidate sections vehicles should take instead.")
    veh_type: int = Field(default=0,
                          ge=0,
                          description="0 = all vehicles, 1..N specific vehicle types")
    compliance: float = Field(default=1.0,
                              ge=0.0,
                              le=1.0,
                              description="Share of drivers obeying the measure <0-1>")


class MeasureTurnForceOD(_MeasureTurnForceBase):
    """ Force turn action evaluated against OD paths. """
    type: Literal[MeasureType.TURN_FORCE_OD] = MeasureType.TURN_FORCE_OD
    origin_centroid:  int = Field(default=-1,
                                  description="Centroid origin identifier, -1 means do not consider origin with set compliance")
    destination_centroid:  int = Field(default=-1,
                                       description="Centroid destination identifier, -1 means do not consider destination with set compliance")
    section_in_path: int = Field(default=-1,
                                 description="Restrict action to vehicles whose planned path already contains this section. -1 = ignore")
    visibility_distance: float = Field(default=200,
                                       description="Visibility distance in meters of the incident to be used in Aimsun 7.0 models.")


class MeasureTurnForceResult(_MeasureTurnForceBase):
    type: Literal[MeasureType.TURN_FORCE_RESULT] = MeasureType.TURN_FORCE_RESULT
    old_next_section_id: int = Field(...,
                                     description="Which outgoing section of the node to affect")


class NewDestinations(BaseModel):
    """Helper class for `MeasureType.DESTINATION_CHANGE`"""
    dest_id: int = Field(...,
                         description="Candidate destination centroid identifier")
    percentage: float = Field(default=1.0,
                              ge=0.0,
                              le=100.0,
                              description="Percentage of complying vehicles sent to this centroid")


class MeasureDestinationChange(_MeasureBase):
    """
    Redirect vehicles on `section_id` to one or many destination centroids.

    If you pass `new_destinations`, the proportions must sum to 100.0 (±1e-6).
    If you pass the legacy `new_destination` field, it will be
      auto-converted to `new_destinations=[{dest_id=new_destination, percentage=100.0}]`.
    """
    type: Literal[MeasureType.DESTINATION_CHANGE] = MeasureType.DESTINATION_CHANGE
    section_id: int = Field(...,
                            description="Section of action being applied")
    new_destinations: list[NewDestinations] | None = Field(
        default=None,
        description="List of centroid id/proportion objects",
        min_length=1)
    new_destination: int | None = Field(
        default=None,
        description="LEGACY: Single destination centroid",
        exclude=True)
    origin_centroid: int = Field(default=-1,
                                 description="Origin centroid filter (-1 ignores)")
    destination_centroid: int = Field(default=-1,
                                      description="Destination centroid filter (-1 ingores)")
    veh_type: int = Field(default=0,
                          ge=0,
                          description="0 = all vehicles, 1..N specific vehicle types")
    compliance: float = Field(default=1.0,
                              ge=0.0,
                              le=1.0,
                              description="Share of drivers obeying the measure <0-1>")

    @model_validator(mode="after")
    def _fill_and_check(self):
        # Legacy field handling:
        if self.new_destinations is None:
            if self.new_destination is None:
                raise ValueError("Either dest_proportions or new_destination must be provided")
            self.new_destinations = [NewDestinations(dest_id=self.new_destination, percentage=100.0)]

        total = sum(p.percentage for p in self.new_destinations)
        if not isclose(total, 100.0, rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError(f"Destination percentages must sum to 100.0 (got {total})")

        return self


MeasurePayload = Annotated[
    Union[
        MeasureSpeedSection,
        MeasureSpeedDetailed,
        MeasureLaneClosure,
        MeasureLaneClosureDetailed,
        MeasureLaneDeactivateReserved,
        MeasureTurnClose,
        MeasureTurnForceOD,
        MeasureTurnForceResult,
        MeasureDestinationChange
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


# > Policies --------------------------------------------------------------------
class PolicyTargetDto(BaseModel):
    policy_id: int = Field(...,
                           description="ID of the policy to affect",
                           gt=0)
# < Policies --------------------------------------------------------------------


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
    command: Literal[CommandType.MEASURES_RESET] = CommandType.MEASURES_RESET
    payload: None = Field(default=None)


class PolicyActivateCmd(CommandBase):
    command: Literal[CommandType.POLICY_ACTIVATE] = CommandType.POLICY_ACTIVATE
    payload: PolicyTargetDto


class PolicyDeactivateCmd(CommandBase):
    command: Literal[CommandType.POLICY_DEACTIVATE] = CommandType.POLICY_DEACTIVATE
    payload: PolicyTargetDto


Command = Annotated[
    Union[
        IncidentCreateCmd,
        IncidentRemoveCmd,
        IncidentsClearSectionCmd,
        IncidentsResetCmd,
        MeasureCreateCmd,
        MeasureRemoveCmd,
        MeasuresClearCmd,
        PolicyActivateCmd,
        PolicyDeactivateCmd
    ],
    Field(discriminator="command")]
# < Command Wrappers ------------------------------------------------------------


class ScheduleRoot(RootModel[list[Command]]):
    pass
# < Scheduled command ----------------------------------------------------------

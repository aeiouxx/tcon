"""
Just boilerplate to avoid having to specify the command field and wrapping our command parameters
in "payload" when sending to server.

So instead of having to send redundant information by reusing our ``common.models``
{
    "command": CMD_ID  <- we know this from the URI, no need to contain here
    "time": xxx
    "payload": {
        ...
    }
}

we flatten it into:
{
    "time": xxx
    "parameter_1": xxx
    .
    .
    .
    "parameter_n": xxx
}
"""
from typing import Optional
from pydantic import BaseModel, Field

from common.models import (
    CommandBase,
    CommandType,
    IncidentCreateDto,
    IncidentRemoveDto,
    _MeasureBase,
    MeasureType
)


class ScheduledBase(BaseModel):
    time: Optional[float] = Field(default=CommandBase.IMMEDIATE)


class IncidentCreateInput(IncidentCreateDto, ScheduledBase):
    pass


class IncidentRemoveInput(ScheduledBase):
    section_id: int = Field(...,
                            description="Section of the incident")
    lane: int = Field(...,
                      description="Lane of the incident")
    position: float = Field(...,
                            description="Position of the incident in the section (from the beginning of the section).")


class IncidentsClearSectionInput(ScheduledBase):
    pass


class _MeasureBaseInput(_MeasureBase, ScheduledBase):
    pass


class MeasureSpeedSectionInput(_MeasureBaseInput):
    """
    Changes the speed limit in one or many sections.
    Calls the AKIActionAddSpeedSectionById API function.
    """
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


class MeasureSpeedDetailedInput(_MeasureBaseInput):
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


class MeasureLaneClosureInput(_MeasureBaseInput):
    section_id: int = Field(..., description="Identifier of the section to apply action to")
    lane_id: int = Field(..., description="Identifier of the lane to apply action to")
    veh_type: int = Field(default=0,
                          ge=0,
                          description="0 = all vehicles, 1..N specific vehicle types")


class MeasureLaneClosureDetailedInput(_MeasureBaseInput):
    section_id: int = Field(..., description="Identifier of the section to apply action to")
    lane_id: int = Field(..., description="Identifier of the lane to apply action to")
    veh_type: int = Field(default=0,
                          ge=0,
                          description="0 = all vehicles, 1..N specific vehicle types")
    apply_2LCF: bool = Field(default=False,
                             description="True if the 2-lanes car following model is to be considered")
    visibility_distance: float = Field(default=200,
                                       description="The distance at which the lane closure will start to be visible for vehicles")


class MeasureLaneDeactivateReservedInput(_MeasureBaseInput):
    section_id: int = Field(..., description="Identifier of the section to apply action to")
    lane_id: int = Field(..., description="Identifier of the lane to apply action to")
    segment_id: int = Field(default=-1,
                            description="0..N-1 where N is number of segments present within section or -1 to apply to all segments.")


class MeasureTurnCloseInput(_MeasureBaseInput):
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

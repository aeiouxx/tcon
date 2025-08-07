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
from pydantic import BaseModel, Field, model_validator

from common.models import (
    CommandBase,
    CommandType,
    IncidentCreateDto,
    IncidentRemoveDto,
    _MeasureBase,
    MeasureType,
    NewDestinations
)


class ScheduledBase(BaseModel):
    time: float | None = Field(default=CommandBase.IMMEDIATE)


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


class _MeasureTurnForceBaseInput(_MeasureBaseInput):
    """ Body shared by both /measure/turn-force/* endpoints"""
    from_section_id: int = Field(..., description="Section where action starts.")
    next_section_ids: list[int] = Field(...,
                                        min_length=1,
                                        description="Destination section(s) vehicles should take")
    veh_type: int = Field(default=0,
                          ge=0,
                          description="0 = all vehicles, 1..N specific vehicle types")
    compliance: float = Field(default=1.0,
                              ge=0.0,
                              le=1.0,
                              description="Share of drivers obeying the measure <0-1>")


class MeasureTurnForceInputOd(_MeasureTurnForceBaseInput):
    origin_centroid:  int = Field(default=-1,
                                  description="Centroid origin identifier, -1 means do not consider origin with set compliance")
    destination_centroid:  int = Field(default=-1,
                                       description="Centroid destination identifier, -1 means do not consider destination with set compliance")
    section_in_path: int = Field(default=-1,
                                 description="Restrict action to vehicles whose planned path already contains this section. -1 = ignore")
    visibility_distance: float = Field(default=200,
                                       description="Visibility distance in meters of the incident to be used in Aimsun 7.0 models.")


class MeasureTurnForceInputResult(_MeasureTurnForceBaseInput):
    old_next_section_id: int = Field(...,
                                     description="Which outgoing section of the node to affect")


class MeasureDestinationChangeInput(_MeasureBaseInput):
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
        if not abs(total - 100.0) <= 1e-6:
            raise ValueError(f"Destination percentages must sum to 100.0 (got {total})")

        return self

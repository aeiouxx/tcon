import pytest
from common.models import (
    Command, CommandType,
    CreateIncidentDto, RemoveIncidentDto
)

# FIXME: just sum random BS to test actions etc


def _valid_incident():
    return dict(
        section_id=42,
        lane=1,
        position=30.0,
        length=10.0,
        ini_time=3600.0,
        duration=600.0
    )


def test_incident_dto_accepts_valid_payload():
    dto = CreateIncidentDto(**_valid_incident())
    assert dto.section_id == 42
    assert dto.apply_speed_reduction is True


def test_incident_dto_rejects_negative_lane():
    bad = _valid_incident() | {"lane": -1}
    with pytest.raises(ValueError):
        CreateIncidentDto(**bad)


def test_command_roundtrip():
    dto = CreateIncidentDto(**_valid_incident())
    cmd = Command(type=CommandType.INCIDENT_CREATE,
                  payload=dto.model_dump())
    cloned = Command.parse_raw(cmd.json())
    assert cloned == cmd

from __future__ import annotations
import multiprocessing as mp
from fastapi import FastAPI, Header, Path, Query
from typing import Any, Generic, TypeVar, Optional
from logging import DEBUG

import json

from common.models import (
    Command,
    CommandBase,
    IncidentCreateCmd,
    IncidentRemoveCmd,
    IncidentsResetCmd,
    IncidentsClearSectionCmd,
    IncidentsClearSectionDto,
    MeasurePayload,
    MeasureCreateCmd,
    MeasureSpeedSection,
    MeasureSpeedDetailed,
    MeasureLaneClosure,
    MeasureLaneClosureDetailed,
    MeasureLaneDeactivateReserved,
    MeasureTurnClose,
    MeasureTurnForceOD,
    MeasureTurnForceResult,
    MeasureRemoveDto,
    MeasureRemoveCmd,
    MeasuresClearCmd,
    PolicyActivateCmd,
    PolicyDeactivateCmd,
    PolicyTargetDto
)

from server.models import (
    ScheduledBase,
    IncidentCreateInput,
    IncidentRemoveInput,
    IncidentsClearSectionInput,
    _MeasureBaseInput,
    MeasureSpeedSectionInput,
    MeasureSpeedDetailedInput,
    MeasureLaneClosureInput,
    MeasureLaneClosureDetailedInput,
    MeasureLaneDeactivateReservedInput,
    MeasureTurnCloseInput,
    MeasureTurnForceInputOd,
    MeasureTurnForceInputResult)

from pydantic import BaseModel, Field
from common.logger import get_logger
from http import HTTPStatus


log = get_logger(__name__)


# > Helpers ---------------------------------------------------------------------
def _enqueue(queue: mp.Queue,
             cmd: Command) -> dict[str, Any]:
    payload = cmd.model_dump()
    if log.isEnabledFor(DEBUG):
        log.debug("Accepted command: \n%s", json.dumps(payload, indent=2))
    queue.put(payload)
    return {"accepted": True}


def _as_command(data: ScheduledBase, command_cls: type[CommandBase]) -> Command:
    payload = data.model_dump()
    return command_cls(
        time=payload.pop("time", CommandBase.IMMEDIATE),
        payload=payload)


def _as_measure_create_cmd(data: _MeasureBaseInput,
                           payload_cls: type[MeasurePayload]) -> Command:
    payload = data.model_dump()
    time = payload.pop("time", CommandBase.IMMEDIATE)
    return MeasureCreateCmd(time=time,
                            payload=payload_cls.model_validate(payload))
# < Helpers ---------------------------------------------------------------------


# > FastAPI --------------------------------------------------------------------
def build_app(queue: mp.Queue) -> FastAPI:
    app = FastAPI(title="tcon API", version="1.0.0")
    register_incidents(app, queue)
    register_measures(app, queue)
    register_policies(app, queue)
    return app


def register_incidents(app: FastAPI, queue: mp.Queue) -> None:

    @app.post("/incident", status_code=HTTPStatus.ACCEPTED)
    def _incident_create(data: IncidentCreateInput):
        if log.isEnabledFor(DEBUG):
            log.debug(json.dumps(data.model_dump(), indent=2))
        return _enqueue(queue,
                        _as_command(data, IncidentCreateCmd))

    @app.delete("/incident", status_code=HTTPStatus.ACCEPTED)
    def _incident_remove(data: IncidentRemoveInput):
        if log.isEnabledFor(DEBUG):
            log.debug(json.dumps(data.model_dump(), indent=2))
        return _enqueue(queue,
                        _as_command(data, IncidentRemoveCmd))

    @app.delete("/incidents/section/{section_id}", status_code=HTTPStatus.ACCEPTED)
    def _incidents_clear_section(section_id: int = Path(..., gt=0),
                                 time: float = Query(default=CommandBase.IMMEDIATE)):
        cmd = IncidentsClearSectionCmd(time=time,
                                       payload=IncidentsClearSectionDto(section_id=section_id))
        return _enqueue(queue, cmd)

    @app.post("/incidents/reset", status_code=HTTPStatus.ACCEPTED)
    def _incidents_clear_all(time: float = Query(default=CommandBase.IMMEDIATE)):
        cmd = IncidentsResetCmd(time=time)
        return _enqueue(queue, cmd)


def register_measures(app: FastAPI, queue: mp.Queue) -> None:
    @app.post("/measure/speed", status_code=HTTPStatus.ACCEPTED)
    def _measure_speed(data: MeasureSpeedSectionInput):
        if log.isEnabledFor(DEBUG):
            log.debug(json.dumps(data.model_dump(), indent=2))
        return _enqueue(queue,
                        _as_measure_create_cmd(data, MeasureSpeedSection))

    @app.post("/measure/speed-detailed", status_code=HTTPStatus.ACCEPTED)
    def _measure_speed_detailed(data: MeasureSpeedDetailedInput):
        if log.isEnabledFor(DEBUG):
            log.debug(json.dumps(data.model_dump(), indent=2))
        return _enqueue(queue,
                        _as_measure_create_cmd(data, MeasureSpeedDetailed))

    @app.post("/measure/lane-closure", status_code=HTTPStatus.ACCEPTED)
    def _measure_lane_closure(data: MeasureLaneClosureInput):
        if log.isEnabledFor(DEBUG):
            log.debug(json.dumps(data.model_dump(), indent=2))
        return _enqueue(queue,
                        _as_measure_create_cmd(data, MeasureLaneClosure))

    @app.post("/measure/lane-closure-detailed", status_code=HTTPStatus.ACCEPTED)
    def _measure_lane_closure_detailed(data: MeasureLaneClosureDetailedInput):
        if log.isEnabledFor(DEBUG):
            log.debug(json.dumps(data.model_dump(), indent=2))
        return _enqueue(queue,
                        _as_measure_create_cmd(data, MeasureLaneClosureDetailed))

    @app.post("/measure/lane-unreserve", status_code=HTTPStatus.ACCEPTED)
    def _measure_lane_unreserve(data: MeasureLaneDeactivateReservedInput):
        if log.isEnabledFor(DEBUG):
            log.debug(json.dumps(data.model_dump(), indent=2))
        return _enqueue(queue,
                        _as_measure_create_cmd(data, MeasureLaneDeactivateReserved))

    @app.post("/measure/turn-close", status_code=HTTPStatus.ACCEPTED)
    def _measure_turn_close(data: MeasureTurnCloseInput):
        if log.isEnabledFor(DEBUG):
            log.debug(json.dumps(data.model_dump(), indent=2))
        return _enqueue(queue,
                        _as_measure_create_cmd(data, MeasureTurnClose))

    @app.post("/measure/turn-force/od", status_code=HTTPStatus.ACCEPTED)
    def _measure_turn_force_od(data: MeasureTurnForceInputOd):
        if log.isEnabledFor(DEBUG):
            log.debug(json.dumps(data.model_dump(), indent=2))
        return _enqueue(queue,
                        _as_measure_create_cmd(data, MeasureTurnForceOD))

    @app.post("/measure/turn-force/result", status_code=HTTPStatus.ACCEPTED)
    def _measure_turn_force_od(data: MeasureTurnForceInputResult):
        if log.isEnabledFor(DEBUG):
            log.debug(json.dumps(data.model_dump(), indent=2))
        return _enqueue(queue,
                        _as_measure_create_cmd(data, MeasureTurnForceResult))

    @app.delete("/measure/{measure_id}", status_code=HTTPStatus.ACCEPTED)
    def _measure_remove(measure_id: int = Path(..., gt=0),
                        time: float = Query(default=CommandBase.IMMEDIATE)):
        cmd = MeasureRemoveCmd(time=time,
                               payload=MeasureRemoveDto(id_action=measure_id))
        return _enqueue(queue, cmd)

    @app.post("/measures/reset", status_code=HTTPStatus.ACCEPTED)
    def _measures_clear(time: float = Query(default=CommandBase.IMMEDIATE)):
        cmd = MeasuresClearCmd(time=time)
        return _enqueue(queue, cmd)


def register_policies(app: FastAPI, queue: mp.Queue) -> None:
    @app.post("/policy/{policy_id}", status_code=HTTPStatus.ACCEPTED)
    def _policy_activate(policy_id: int = Path(..., gt=0),
                         time: float = Query(default=CommandBase.IMMEDIATE)):
        cmd = PolicyActivateCmd(time=time,
                                payload=PolicyTargetDto(policy_id=policy_id))
        return _enqueue(queue, cmd)

    @app.delete("/policy/{policy_id}", status_code=HTTPStatus.ACCEPTED)
    def _policy_deactivate(policy_id: int = Path(..., gt=0),
                           time: float = Query(default=CommandBase.IMMEDIATE)):
        cmd = PolicyDeactivateCmd(time=time,
                                  payload=PolicyTargetDto(policy_id=policy_id))
        return _enqueue(queue, cmd)

# < FastAPI --------------------------------------------------------------------


def run_api_process(
        queue: mp.Queue,
        host: str = "127.0.0.1",
        port: int = 6969) -> None:
    import uvicorn
    log.info("API listening on http://%s:%d", host, port)
    app = build_app(queue)
    uvicorn.run(app,
                host=host,
                port=port,
                log_level="warning")


if __name__ == "__main__":
    log.setLevel("DEBUG")
    run_api_process(mp.Queue())

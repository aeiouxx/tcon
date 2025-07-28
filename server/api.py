from __future__ import annotations
import multiprocessing as mp
from fastapi import FastAPI, Header, Path
import json
from common.models import (
    Command,
    CommandType,
    IncidentCreateDto,
    IncidentRemoveDto,
    IncidentsClearSectionDto)
from pydantic import BaseModel
from common.logger import get_logger
from http import HTTPStatus


log = get_logger(__file__, level="DEBUG", disable_ansi=False)


def build_app(queue: mp.Queue):
    app = FastAPI(title="tcon API", version="0.0.2")
    register_utility(app, queue)
    register_incidents(app, queue)

    return app


def _accept(queue: mp.Queue,
            command_type: CommandType,
            payload: dict[str, any] = None) -> dict[str, any]:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump()
    command = Command(type=command_type, payload=payload).model_dump()

    queue.put(command)

    log.debug("Accepted command: \n%s", json.dumps(command, indent=2))
    return {"accepted": True}


def register_incidents(app: FastAPI,
                       queue: mp.Queue):

    @app.post("/incident", status_code=HTTPStatus.ACCEPTED)
    def incident_create(incident: IncidentCreateDto):
        # TODO: support the aimsun visibility for 7.0 models or not?
        return _accept(queue,  CommandType.INCIDENT_CREATE, incident.model_dump())

    # FIXME: this doesn't work, incident not present... WTF
    @app.delete("/incident", status_code=HTTPStatus.ACCEPTED)
    def incident_remove(incident: IncidentRemoveDto):
        _accept(queue,  CommandType.INCIDENT_REMOVE, incident.model_dump())
        return {"msg": "Thanks for the command, sadly this one isn't implemented in Aimsun API correctly..."}

    @app.delete("/incidents/section/{section_id}")
    def incidents_clear_section(section_id=Path(...)):
        return _accept(queue,

                       CommandType.INCIDENTS_CLEAR_SECTION,
                       IncidentsClearSectionDto(section_id=section_id))

    @app.delete("/incidents/reset")
    def incidents_reset_all():
        return _accept(queue,  CommandType.INCIDENTS_RESET)


def register_utility(app: FastAPI,
                     queue: mp.Queue):
    @app.get("/health", status_code=HTTPStatus.OK)
    def _health():
        return {"status": "chilling"}


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

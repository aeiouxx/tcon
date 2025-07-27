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


def build_app(queue: mp.Queue,
              notify_event: mp.Event):
    app = FastAPI(title="tcon API", version="0.0.2")
    register_incidents(app, queue, notify_event)

    return app


def _accept(queue: mp.Queue,
            notify_event: mp.Event,
            command_type: CommandType,
            payload: dict[str, any] = None) -> dict[str, any]:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump()
    command = Command(type=command_type, payload=payload).model_dump()

    queue.put(command)
    notify_event.set()

    log.debug("Accepted command: \n%s", json.dumps(command, indent=2))
    return {"accepted": True}


def register_incidents(app: FastAPI,
                       queue: mp.Queue,
                       notify_event: mp.Event):

    @app.post("/incident", status_code=HTTPStatus.ACCEPTED)
    def incident_create(incident: IncidentCreateDto):
        return _accept(queue, notify_event, CommandType.INCIDENT_CREATE, incident.model_dump())

    @app.delete("/incident", status_code=HTTPStatus.ACCEPTED)
    def incident_remove(incident: IncidentRemoveDto):
        return _accept(queue, notify_event, CommandType.INCIDENT_REMOVE, incident.model_dump())

    @app.delete("/incidents/section/{section_id}")
    def incidents_clear_section(section_id=Path(...)):
        return _accept(queue,
                       notify_event,
                       CommandType.INCIDENTS_CLEAR_SECTION,
                       IncidentsClearSectionDto(section_id=section_id))

    @app.delete("/incidents/reset")
    def incidents_reset_all():
        return _accept(queue, notify_event, CommandType.INCIDENTS_RESET)


def run_api_process(
        queue: mp.Queue,
        notify_event: mp.Event,
        host: str = "127.0.0.1",
        port: int = 6969) -> None:
    import uvicorn
    log.info("API listening on http://%s:%d", host, port)
    app = build_app(queue, notify_event)
    uvicorn.run(app,
                host=host,
                port=port,
                log_level="warning")

from __future__ import annotations
import multiprocessing as mp
from fastapi import FastAPI
import json
from common.models import (
    Command,
    CommandType,
    CreateIncidentDto,
    RemoveIncidentDto)
from common.logger import get_logger
from http import HTTPStatus


log = get_logger(__file__, level="DEBUG", disable_ansi=False)


def build_app(queue: mp.Queue,
              notify_event: mp.Event):
    def _accept(command_type: CommandType,
                payload: dict[str, any]) -> dict[str, any]:
        command = Command(type=command_type, payload=payload).model_dump()

        queue.put(command)
        notify_event.set()

        log.debug("Accepted command: \n%s", json.dumps(command, indent=2))
        return {"accepted": True}

    app = FastAPI(title="tcon API", version="0.0.2")

    @app.get("/health", status_code=HTTPStatus.OK)
    def health():
        log.debug("Health check request")
        return {"status": "I'm chilling."}

    @app.post("/incident", status_code=HTTPStatus.ACCEPTED)
    def create_incident(incident: CreateIncidentDto):
        return _accept(CommandType.INCIDENT_CREATE, incident.model_dump())

    # RFC 9110 - `content received in a DELETE request has no generally defined semantics`
    # we could put the information in request parameters, but this is more comfortable
    @app.delete("/incident", status_code=HTTPStatus.ACCEPTED)
    def remove_incident(incident: RemoveIncidentDto):
        return _accept(CommandType.INCIDENT_REMOVE, incident.model_dump())

    return app


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

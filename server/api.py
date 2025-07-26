from __future__ import annotations
import multiprocessing as mp
from fastapi import FastAPI
import argparse
import json
import multiprocessing.connection as mpc
from common.models import Command, CommandType, CreateIncidentDto, RemoveIncidentDto
from common.logger import get_logger
from common.status import StatusCode
from common.ipc import TconQueue


log = get_logger(__file__, level="DEBUG", disable_ansi=False)


# FIXME: No straightforward way to give results back to the client.


def build_app(pipe_addr: str, notify_event: mp.Event) -> FastAPI:
    # WARNING: On windows when the client closes a connection,
    # our pipe object gets marked as BROKEN,
    # so we need to keep a persistent connection.
    # On UNIX we could reuse the same descriptor...
    _client = mpc.Client(pipe_addr, TconQueue.family())

    def _accept_command(command_type: CommandType, payload: dict[str, any]) -> dict[str, any]:
        command = Command(type=command_type, payload=payload).model_dump()

        notify_event.set()
        _client.send(command)

        log.debug("Accepted command: \n%s", json.dumps(command, indent=2))
        return {"accepted": True}

    app = FastAPI(title="tcon API", version="0.0.2")

    @app.get("/health")
    def health():
        log.debug("Health check request")
        return {"status": "it's alive!"}

    @app.post("/incident", status_code=StatusCode.ACCEPTED)
    def create_incident(incident: CreateIncidentDto):
        return _accept_command(CommandType.INCIDENT_CREATE, incident.model_dump())

    @app.delete("/incident", status_code=StatusCode.ACCEPTED)
    def remove_incident(incident: RemoveIncidentDto):
        return _accept_command(CommandType.INCIDENT_REMOVE, incident.model_dump())

    @app.on_event("shutdown")
    def _cleanup():
        log.info("Releasing client...")
        if not _client.closed:
            _client.close()

    return app


def run_api_process(
        pipe_addr: str,
        notify_event: mp.Event,
        host: str = "127.0.0.1",
        port: int = 6969) -> None:
    import uvicorn
    log.info("API listening on http://%s:%d", host, port)
    app = build_app(pipe_addr, notify_event)
    uvicorn.run(app,
                host=host,
                port=port,
                log_level="warning")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=6969)
    ap.add_argument("--host", type=str, default="127.0.0.1")
    args = ap.parse_args()
    # run_api_process(queue, args.host, args.port)

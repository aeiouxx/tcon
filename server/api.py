from __future__ import annotations
import multiprocessing as mp
from fastapi import FastAPI
import argparse
from common.models import Command, CommandType, Incident
from common.logger import get_logger
from common.status import StatusCode

log = get_logger(__file__, disable_ansi=False)


# TODO: figure out API for incident creation + measure creation
def build_app(queue: mp.Queue) -> FastAPI:
    app = FastAPI(title="tcon API", version="0.0.1")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # FIXME: better API design sorely needed
    @app.post("/incident", status_code=StatusCode.ACCEPTED)
    def create_incident(incident: Incident):
        queue.put(Command(type=CommandType.INCIDENT_CREATE,
                  payload=incident.dict()).dict())
        return {"accepted": True}

    return app


def run_api_process(queue: mp.Queue, host: str = "127.0.0.1", port: int = 6969):
    import uvicorn
    app = build_app(queue)
    log.info("Listening on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=6969)
    ap.add_argument("--host", type=str, default="127.0.0.1")
    args = ap.parse_args()
    queue = mp.Queue()
    run_api_process(queue, args.host, args.port)

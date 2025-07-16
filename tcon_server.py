"""FastAPI service for forwarding commands to controller"""
from __future__ import annotations
import argparse
import logging
import pathlib
import multiprocessing as mp
from fastapi import FastAPI
import uvicorn
import queue


def _logger() -> logging.Logger:
    path = pathlib.Path(__file__).with_name("server.log")
    path.touch(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        handlers=[logging.FileHandler(
            path, "a", "utf-8"), logging.StreamHandler()],
    )
    return logging.getLogger("tcon.server")

# > Server --------------------------------------------------------------------


class TconServer:
    def __init__(self, port: int = 6969, queue: mp.Queue | None = None):
        self.port = port
        if not queue:
            raise ValueError("A multiprocessing.Queue must be supplied!")
        self.queue = queue
        self.log = _logger()
        self.api = FastAPI(title="MyApi", version=0.1)
        self._routes()

    def _enqueue(self, payload: dict) -> None:
        """Enqueue a payload to a queue"""
        try:
            self.queue.put(payload)
        except queue.Full:
            self.log.info("Queue was full, do we need a better mechanism")

    def _routes(self) -> None:
        """ Setting up routes"""
        @self.api.get("/hello")
        def hello() -> dict:
            """Health-check endpoint."""
            self.log.info("Received /hello")
            self._enqueue({"cmd": "hello"})
            return {"message": "hello"}

    def run(self) -> None:
        self.log.info("Serving on http://127.0.0.1:%d …", self.port)
        uvicorn.run(
            self.api,
            host="127.0.0.1",
            port=self.port,
            workers=None,
            log_level="info")


# < Server

# > CLI -----------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=6969)
    args = ap.parse_args()
    # When launched from shell (testing), supply our own queue
    q = mp.Queue()
    TconServer(port=args.port, queue=q).run()
# < CLI

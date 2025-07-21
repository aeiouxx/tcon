"""Multiprocessing queue and process wrapper for the Server"""
from __future__ import annotations
import multiprocessing as mp
from multiprocessing.queues import Queue
import shutil

from common.logger import get_logger

log = get_logger(__file__)


class ServerProcess:
    _python_executable: str | None = None

    def __init__(self, host: str = "127.0.0.1", port: int = 6969):
        self.executable = self._resolve_python()
        self.host = host
        self.port = port
        self.queue: Queue = mp.Queue()
        self._proc: mp.Process | None = None

    def start(self):
        if self._proc and self._proc.is_alive():
            log.warn("Duplicit start call, process already alive")
        from server.api import run_api_process
        mp.set_executable(self.executable)
        self._proc = mp.Process(target=run_api_process, args=(
            self.queue, self.host, self.port), name="tcon-api")
        self._proc.start()
        log.info("API started on port %d (pid=%d)",
                 self.port, self._proc.pid)

    def stop(self, timeout: float = 3):
        if self._proc and self._proc.is_alive():
            log.info("Shutting down server process (pid=%d)...",
                     self._proc.pid)
            self._proc.terminate()
            self._proc.join(timeout)
        self._proc = None
        log.info("Server process terminated")

    # FIXME: initial resolution is quite expensive if we end up
    # expanding it to work more robustly, cache on filesystem?
    # HACK: sys.executable is set to aimsun, because we're running on
    # an embedded CPython interpreter, so we would just relaunch aimsun
    # we need to lookup a valid executable via path [or just ask user in config file]
    def _resolve_python(self) -> str:
        if ServerProcess._python_executable:
            return ServerProcess._python_executable
        interpreter_path = shutil.which("python")
        if interpreter_path:
            log.info("Resolved python path: %s", interpreter_path)
            ServerProcess._python_executable = interpreter_path
            return interpreter_path
        else:
            log.critical(
                "Unable to resolve path to interpreter, server can't run!")
            raise RuntimeError("Could not find Python 3.10 interpreter.")

from __future__ import annotations
import multiprocessing as mp
import sys
from types import TracebackType
from typing import Iterator, Type
import shutil


from common.logger import get_logger

log = get_logger(__name__)
# ServerProcess > --------------------------------------------------------------


class ServerProcess:
    _python_exe: str | None = None

    def __init__(self,
                 host: str = "127.0.0.1",
                 port: int = 6969):
        self.host = host
        self.port = port
        self.executable = self._resolve_pajtn()
        # IPC
        self.queue: mp.Queue = mp.Queue()
        # Handle
        self._proc: mp.Process | None = None

    def start(self) -> None:
        from server.api import run_api_process
        mp.set_executable(self.executable)

        self._proc = mp.Process(
            target=run_api_process,
            args=(self.queue, self.host, self.port),
            name="tcon-api")
        self._proc.start()
        log.info("API started on http://%s:%d (pid=%d)",
                 self.host, self.port, self._proc.pid)

    def stop(self, timeout: float = 3.0) -> None:
        if self._proc and self._proc.is_alive():
            log.info("Terminating API process (pid=%d)...", self._proc.pid)
            self._proc.terminate()
            self._proc.join(timeout)

        self._proc.close()
        self._proc = None

        self.queue.close()
        self.queue.join_thread()
        self.queue = None

    def try_recv_all(self) -> Iterator[object]:
        """ Drain all pending messagess """
        while True:
            try:
                yield self.queue.get_nowait()
            except mp.queues.Empty:
                break

    @classmethod
    def _resolve_pajtn(cls) -> str:
        """ Lazy way to lookup the real python executable"""
        # FIXME: This needs to be more robust!
        if cls._python_exe is None:
            cls._python_exe = shutil.which("python") or sys.executable
        return cls._python_exe

    def __enter__(self) -> "ServerProcess":
        self.start()
        return self

    def __exit__(
            self,
            exc_type: Type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None) -> None:
        self.stop()

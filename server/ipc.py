from __future__ import annotations
import multiprocessing as mp
from types import TracebackType
from typing import Iterator, Type
import shutil
import pathlib

import re


from common.logger import get_logger, get_log_manager

log = get_logger(__name__)
# ServerProcess > --------------------------------------------------------------

if "_PYTHON_EXE" not in globals():
    _PYTHON_EXE: str | None = None


class ServerProcess:
    def __init__(self,
                 host: str = "127.0.0.1",
                 port: int = 6969,
                 executable: str | None = None):
        self.host = host
        self.port = port
        self.executable = self._resolve_python_location(executable)
        # IPC
        self.queue: mp.Queue = mp.Queue()
        # Handle
        self._proc: mp.Process | None = None

    def start(self) -> None:
        from server.api import run_api_process, module_name
        mp.set_executable(self.executable)

        # FIXME: Log manager instance is not shared across process boundaries,
        # as it lives in the global symbol table (unique per process)
        # we have to export the current log configuration for the server.api module to the
        # server process (or we could reparse the config in the api process, but this is quicker)
        # albeit less clean
        api_log_cfg = get_log_manager().export_config(module_name())

        self._proc = mp.Process(
            target=run_api_process,
            args=(self.queue, api_log_cfg, self.host, self.port),
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
    def _resolve_python_location(cls,
                                 configured: str | None) -> str:
        global _PYTHON_EXE
        if _PYTHON_EXE is not None:
            return _PYTHON_EXE

        def ok(path: str | None) -> str | None:
            if not path:
                return None
            p = pathlib.Path(path)
            log.debug("Checking python location %s", path)
            if not (p.exists() and p.is_file()):
                log.debug("Microsoft store stub application???")
                return None
            import subprocess
            try:
                out = subprocess.check_output([path, "-V"], text=True)
                major, minor = map(int, re.search(r"(\d+)\.(\d+)", out).groups())
                if (major, minor) == (3, 10):
                    return path
            except Exception as exc:
                log.debug("Skipping %s: %s", path, exc)
            return None

        # sys.executable will be the embedded interpreter inside
        # the aimsun executable, so we would just relaunch aimsun instead
        # of running server...
        _PYTHON_EXE = (
            configured  # we assume that the user supplied value is actually correct to speed up launch
            or ok(shutil.which("python3.10"))
            or ok(shutil.which("python3"))
            or ok(shutil.which("python")))

        if _PYTHON_EXE is None:
            raise RuntimeError(
                "Could not locate a Python 3.10 executable; "
                "set 'python_location' in config.json, or add python executable to your PATH.")
        return _PYTHON_EXE

    def __enter__(self) -> "ServerProcess":
        self.start()
        return self

    def __exit__(
            self,
            exc_type: Type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None) -> None:
        self.stop()

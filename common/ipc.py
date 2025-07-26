from __future__ import annotations
import os
import pathlib
import tempfile
import multiprocessing as mp
import multiprocessing.connection as mpc
import sys
from contextlib import suppress
from typing import Any
from pathlib import Path
from types import TracebackType
from typing import Iterator, Type
import shutil


from common.logger import get_logger
log = get_logger(__file__)


# TconQueue > -------------------------------------------------------------------
class TconQueue:
    r"""
        Windows: Named Pipe -> \\.pipe\<name>
        Unix: UNIX‑domain socket file  ->  /tmp/<name>.sock
    """

    def __init__(
            self,
            name: str = "tcon_ipc", *,
            tmpdir: str | pathlib.Path | None = None,
            notify_event: mp.Event | None = None):
        self.name = name
        self._path = self._make_addr(name, tmpdir)
        self._listener: mpc.Listener | None = None
        self._conn: mpc.Connection | None = None
        self._notify = notify_event or mp.Event()

# PUBLIC
    @property
    def address(self) -> str:
        return self._path

    @property
    def notify(self) -> mp.Event:
        """ Set by producer, cleared by consumer. """
        return self._notify

    def start(self) -> None:
        self._cleanup()
        self._listener = mpc.Listener(self._path, family=self.family())

    def poll(self) -> bool:
        self._ensure_connection()
        return self._conn.poll(0)

    def recv(self) -> Any:
        self._ensure_connection()
        return self._conn.recv()

    def close(self) -> None:
        if self._conn:
            with suppress(OSError):
                self._conn.close()
        if self._listener:
            with suppress(OSError):
                self._listener.close()
        self._cleanup()
# HELPERS

    def take_client(self) -> mpc.Client:
        return mpc.Client(self.address, self.family())

    @staticmethod
    def family() -> str:
        return "AF_PIPE" if os.name == "nt" else "AF_UNIX"

    @staticmethod
    def _make_addr(name: str, tmpdir) -> str:
        if os.name == "nt":
            return fr"\\.\pipe\{name}"
        root = pathlib.Path(tmpdir or tempfile.gettempdir())
        return str(root / f"{name}.sock")

    def _cleanup(self) -> None:
        """
            Windows:
                `An instance of a named pipe is always deleted
                when the last handle to the instance 
                of the named pipe is closed.`
            Unix:
                Actual filesystem entry -> needs unlinking
        """
        if os.name != "nt" and os.path.exists(self._path):
            with suppress(OSError):
                os.unlink(self._path)

    def _ensure_connection(self) -> None:
        if self._conn is not None:
            return
        assert self._listener, "start() needs to be called first!"
        self._conn = self._listener.accept()


# < TconQueue ------------------------------------------------------------------
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
        self._queue = TconQueue()
        self.notify: mp.Event = self._queue.notify
        # Handle
        self._proc: mp.Process | None = None

    def start(self) -> None:
        from server.api import run_api_process
        self._queue.start()
        mp.set_executable(self.executable)

        self._proc = mp.Process(
            target=run_api_process,
            args=(self._queue.address, self.notify, self.host, self.port),
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

        self._queue.close()
        self._queue = None

        self.notify.clear()
        self.notify = None

    def try_recv_all(self) -> Iterator[object]:
        """ Drain all pending messagess """
        while self._queue.poll():
            yield self._queue.recv()

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

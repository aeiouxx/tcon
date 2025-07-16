import importlib.util
import pathlib
import sys
import logging
import shutil
from dataclasses import dataclass
from queue import Empty
from typing import List
from logging.handlers import RotatingFileHandler
import multiprocessing as mp
from multiprocessing.queues import Queue
import json
# -----------------------------------------------------------------------------
# Ensure AAPI provided by Aimsun is importable
# try:
#     from AAPI import *
# except ImportError as err:
#     # FIXME: Do we even need a local copy?
#     _aapi_local = pathlib.Path(__file__).with_name("AAPI.py")
#     if _aapi_local.exists():
#         spec = importlib.util.spec_from_file_location("AAPI", _aapi_local)
#         AAPI = importlib.util.module_from_spec(spec)
#         sys.modules["AAPI"] = AAPI
#         spec.loader.exec_module(AAPI)
#     else:
#         raise ImportError(
#             "Cannot locate: 'AAPI.py'."
#             "Try copying the file located at your aimsun installation"
#             "under 'programming/Aimsun Next API/python/base/Micro/AAPI.py'"
#             "next to this file.")
# > Logging --------------------------------------------------------------------


def _make_logger(name: str, level: int = logging.DEBUG, filepath: str = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    print(f"RETRIEVING LOGGER: {name}")
    if logger.handlers:
        return logger
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)
    if filepath:
        path = pathlib.Path(__file__).with_name(filepath)
        file = RotatingFileHandler(path, maxBytes=5 *
                                   1024**2, backupCount=3, encoding="utf-8")
        file.setFormatter(fmt)
        logger.addHandler(file)
    return logger


LOG = _make_logger("MyController")
# < Logging
# > Data Models ----------------------------------------------------------------


@dataclass
class Incident:
    """Represents an incident to be generated"""
    section_id: int
    """Identifier of the section where the incident will be generated"""
    lane: int = -1
    """Lane where the incident will be generated (1..N)"""
    position: float = 0
    """Position of the incident"""
    length: float = 0
    """Length of the incident"""
    initime: int = 0
    """Seconds from midnight when to start incident."""
    duration: int = 0
    """Duration in seconds"""
    visibility_distance: int = 200,
    """For Aimsun 7.0 models"""
    update_id_group: bool = True
    """True if creating new incident, False if 'adding' to last created incident, for example when blocking multiple lanes"""
    apply_speed_reduction: bool = True
    """Create a speed reduction around the incident"""
    upstream_distance_SR: float = 200.0
    """If the reduction is to be applied, the distance (meters) upstream of the incident"""
    downstream_distance_SR: float = 200.0
    """If the reduction is to be applied, the distance (meters) downstream of the incident"""
    max_speed_SR: float = 50.0
    """Target reduced speed (km/h)"""


# < Data Models
# > IPC ------------------------------------------------------------------------
_queue: Queue | None = None
_server: mp.Process | None = None
_pending: List[dict] = []
PORT = 6969


def _run_server_child(http_port: int, queue: mp.Queue) -> None:
    import traceback
    import pathlib
    crash = pathlib.Path(__file__).with_name("server_child_crash.log")
    try:
        from tcon_server import TconServer
        TconServer(port=http_port, queue=queue).run()
    except Exception:
        crash.write_text(traceback.format_exc())
        raise


def _resolve_python() -> str:
    path_py = shutil.which("python")
    if path_py:
        LOG.info("Found python executable %s", path_py)
        return path_py
    return None


def _server_start() -> None:
    global _queue, _server
    if _server and _server.is_alive():
        LOG.debug("Server is already running (pid=%d)", _server.pid)
        return
    executable = _resolve_python()
    if executable:
        LOG.debug("Setting executable %s", executable)
        mp.set_executable(executable)
    _queue = mp.Queue()
    process = mp.Process(
        name="tcon-server",
        target=_run_server_child,
        args=(PORT, _queue),
        daemon=False)
    process.start()
    _server = process
    LOG.info("Server started on port %d (pid=%d)", PORT, _server.pid)


def _server_terminate() -> None:
    global _server
    if _server and _server.is_alive():
        LOG.info("Terminating server (pid=%d)...", _server.pid)
        _server.terminate()
        _server.join(timeout=5)
    _server = None


def _drain_queue() -> None:
    """Pickup things from queue"""
    # FIXME: bad code, pickup directly from queue in AAPIManage
    if not _queue:
        return
    while True:
        try:
            _pending.append(_queue.get_nowait())
        except Empty:
            break


def _cleanup(*_sig: object, **_kw: object) -> None:
    _server_terminate()


# < IPC
# > AAPI CALLBACKS -------------------------------------------------------------


def AAPILoad() -> int:
    # TODO: difference between this and INIT?
    LOG.debug("AAPILoad()")
    _server_start()
    return 0


def AAPIInit() -> int:
    # TODO: difference between this and LOAD?
    LOG.debug("AAPIInit()")

    return 0


def AAPISimulationReady() -> int:
    LOG.debug("AAPISimulationReady()")
    return 0


def AAPIManage(time: float, timeSta: float, timTrans: float, acicle: float) -> int:
    _drain_queue()
    while _pending:
        cmd = _pending.pop(0)
        LOG.info("Handling command from server: %s", json.dumps(cmd))
        # TODO: do stuff
    return 0


def AAPIPostManage(time: float, timeSta: float, timTrans: float, acicle: float) -> int:
    return 0


def AAPIFinish() -> int:
    """Called when the current simulation run finishes"""
    LOG.debug("AAPIFinish()")
    return 0


def AAPIUnLoad() -> int:
    """Called when we cancel the current simulation run"""
    LOG.debug("AAPIUnLoad")
    _server_terminate()
    return 0


def AAPIEnterVehicle(idveh: int, idsection: int) -> int:
    return 0


def AAPIExitVehicle(idveh: int, idsection: int) -> int:
    return 0


def AAPIEnterPedestrian(idPedestrian: int, originCentroid: int) -> int:
    return 0


def AAPIExitPedestrian(idPedestrian: int, destinationCentroid: int) -> int:
    return 0


def AAPIEnterVehicleSection(idveh: int, idsection: int, atime: float) -> int:
    return 0


def AAPIExitVehicleSection(idveh: int, idsection: int, time: float) -> int:
    return 0


def AAPIPreRouteChoiceCalculation(time: float, timeSta: float) -> int:
    return 0


def AAPIVehicleStartParking(idveh: int, idsection: int, time: float) -> int:
    return 0
# < AAPI CALLBACKS


if __name__ == "__main__":
    _server_start()

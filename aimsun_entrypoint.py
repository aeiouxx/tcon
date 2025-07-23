"""
This file represents an entrypoint for the traffic control application, it must
be included in each scenario, where usage is required, directly via Aimsun
(Scenario > Properties > Aimsun Next APIs > Add).

Aimsun will then use the provided callbacks during simulation execution.

WARNING: While the simulation is paused / not executing, Aimsun holds the GIL, so threading does not work as one would expect here.
"""
from __future__ import annotations
import importlib
import sys
import pathlib
import logging
import json
from types import ModuleType
from queue import Empty
from pydantic import BaseModel

# HACK: Only for static analysis, at runtime we import only via our importing mechanism
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from common.logger import get_logger
    from common.ipc import ServerProcess
    from common.models import CommandType, Command, CreateIncidentDto, RemoveIncidentDto
    from common.config import Settings, get_settings

try:
    from AAPI import *
except ImportError:
    from sys import stderr
    stderr.write("This module should not be launched manually "
                 "nor via 'aconsole --script'. "
                 "It's meant to be managed by Aimsun Next APIs in Scenario > Properties > Aimsun Next APIs\n")

# > Module imports -------------------------------------------------------------
# FIXME: If we actually wanted a more robust system, the better way would be to
# recompile and patch the bytecode of the module
# piecemeal (just update __code__ pointer for required parts)
# we could set up a filewatcher and do this automatically, this
# would affect even transitive dependecies, which are not solved with this approach
# (we could define a simple dependency DAG but let's implement the stuff we actually need first...)
if "_MOD_MTIMES" not in globals():
    globals()["_MOD_MTIMES"] = {
    }
_MOD_MTIMES: dict[str, float] = globals()["_MOD_MTIMES"]


def hot_import(name: str, alias: str = None, from_list: list[str] = None, *, base_path: str | pathlib.Path = ".") -> None:
    # WARNING: HOT RELOADING MODULES WITH GLOBAL SCRIPTS IS NOT A GOOD IDEA, AS WE MIGHT RERUN
    # TODO: implement aliasing
    """
    Allows modifying imported code at runtime without having to relaunch Aimsun,
    just rerun the simulation to reload the imports.
    Reload `name` if its .py file changed. Supports:
      • import x                 -> hot_import("x")
      • import x as y            -> hot_import("x", alias="y")
      • from x import a, b       -> hot_import("x", from_list=["a", "b"])
    """
    base_path = pathlib.Path(base_path)
    module_file = base_path / (name.replace(".", "/") + ".py")
    if not module_file.exists():
        raise FileNotFoundError(f"No such module file: {module_file}")
    mtime = module_file.stat().st_mtime
    last_mtime = _MOD_MTIMES.get(name)
    if last_mtime is not None and last_mtime >= mtime:
        return
    if from_list:
        # reimporting symbols
        spec = importlib.util.spec_from_file_location(name, module_file)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(mod)
        globals().update({sym: getattr(mod, sym) for sym in from_list})
        _MOD_MTIMES[name] = mtime
    else:
        # reimporting module
        mod = importlib.reload(sys.modules[name])
        _MOD_MTIMES[name] = mtime


# < Module imports -------------------------------------------------------------
# > Command handling -----------------------------------------------------------
def _handle_incident_create(raw: dict) -> None:
    log.debug("incident_create...")
    pass


def _handle_incident_remove(raw: dict) -> None:
    log.debug("incident_remove...")
    pass


def _handle_simulation_pause(raw: dict = None) -> None:
    """ Here we keep the GIL at the cost of locking the GUI. Wakeup via commands. """
    log.debug("simulation_pause...")
    stop_simulation_cmd = 3
    noop = 0
    ANGSetSimulationOrder(stop_simulation_cmd, noop)
    return


def _handle_simulation_play(raw: dict = None) -> None:
    # FIXME: doesn't work very well...
    log.debug("simulation_play...")
    run_simulation_cmd = 0
    stop_simulation_cmd = 3
    noop = 0
    ANGSetSimulationOrder(stop_simulation_cmd, noop)
    ANGSetSimulationOrder(run_simulation_cmd, noop)
    return


def _dispatch() -> None:
    if not _SERVER.queue:
        log.critical("No queue!")
    while True:
        try:
            raw_cmd: dict = _SERVER.queue.get_nowait()
            cmd_type = CommandType(raw_cmd["type"])
            handler = _DISPATCH_TABLE.get(cmd_type)
            if handler is None:
                log.warning("Unhandled command type: %s", cmd_type)
                continue
            handler(raw_cmd.get("payload") or {})
        except Empty:
            break
        except ValueError:
            log.warning("Unknown command type string: %s", raw_cmd.get("type"))
            continue
        except Exception as exc:
            log.exception("Failed to process %s: %s", cmd_type, exc)


# < Command handling -----------------------------------------------------------
# > AAPI CALLBACKS -------------------------------------------------------------
log = None
_SERVER: ServerProcess | None = None
_DISPATCH_TABLE:  dict[CommandType, callable[[dict], None]]


def _load():
    global log, _SERVER, _DISPATCH_TABLE, _ATEXIT_REGISTERED
    base_path = pathlib.Path(__file__).parent
    hot_import("common.logger", from_list=["get_logger"], base_path=base_path)
    hot_import("common.ipc", from_list=["ServerProcess"], base_path=base_path)
    hot_import("common.models", from_list=[
               "CommandType", "Command", "CreateIncidentDto", "RemoveIncidentDto"], base_path=base_path)
    logfile = base_path.resolve() / "aimsun.log"
    log = get_logger(__file__, "DEBUG", disable_ansi=True, logfile=logfile)
    _DISPATCH_TABLE = {
        CommandType.INCIDENT_CREATE: _handle_incident_create,
        CommandType.INCIDENT_REMOVE: _handle_incident_remove,
        CommandType.SIMULATION_PLAY: _handle_simulation_play,
        CommandType.SIMULATION_PAUSE: _handle_simulation_pause
    }
    if _SERVER and _SERVER._proc and _SERVER._proc.is_alive():
        log.warning("Server is already running")
    else:
        _SERVER = ServerProcess()


def AAPILoad() -> int:
    _load()
    _SERVER.start()
    log.debug("AAPILoad()")
    return 0


def AAPIInit() -> int:
    return 0


def AAPISimulationReady() -> int:
    def pause_simulation_release_GIL() -> int:
        """
        Pauses the simulation, but releases the GIL to aimsun.
        Allows continuing via GUI, but not via our commands, for that we need the GIL
        """
        stop_simulation_cmd = 3
        noop = 0
        ANGSetSimulationOrder(stop_simulation_cmd, noop)
        return 0
    return pause_simulation_release_GIL()


# FIXME: how will we actually pickup stuff from the queue, what if we queue up a ton of stuff
# thats inconsequential, sort by initime and process only entries that will happen next step
# or just pickup everything from the queue? Processing will cost time (although not every time)
def AAPIManage(time: float, timeSta: float, timTrans: float, acicle: float) -> int:
    global _SERVER
    if _SERVER and _SERVER._proc and not _SERVER._proc.is_alive():
        log.warning("Detected server crash — cleaning up")
        _SERVER.stop()
        _SERVER = None
    _dispatch()
    return 0


def AAPIPostManage(time: float, timeSta: float, timTrans: float, acicle: float) -> int:
    return 0


def AAPIFinish() -> int:
    return 0


def AAPIUnLoad() -> int:
    global _SERVER
    log.debug("AAPIUnLoad()")
    _SERVER.stop()
    _SERVER = None
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
# < AAPI CALLBACKS -------------------------------------------------------------

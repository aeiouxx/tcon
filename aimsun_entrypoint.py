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
from types import ModuleType

# HACK: Only for static analysis, at runtime we import only via our importing mechanism
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from common.logger import get_logger
    from common.ipc import ServerProcess
    from common.models import CommandType, Command, Incident

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
# > AAPI CALLBACKS -------------------------------------------------------------
log = None

_SERVER: ServerProcess | None = None


def _load():
    global log, _SERVER
    base = pathlib.Path(__file__).parent
    hot_import("common.logger", from_list=["get_logger"], base_path=base)
    hot_import("common.ipc", from_list=["ServerProcess"], base_path=base)
    hot_import("common.models")
    log = get_logger(__file__, "DEBUG")
    _SERVER = ServerProcess()


def AAPILoad() -> int:
    _load()
    _SERVER.start()
    log.debug("AAPILoad()")
    return 0


def AAPIInit() -> int:
    return 0


def AAPISimulationReady() -> int:
    return 0


# FIXME: how will we actually pickup stuff from the queue, what if we queue up a ton of stuff
# thats inconsequential, sort by initime and process only entries that will happen next step
# or just pickup everything from the queue? Processing will cost time (although not every time)
def AAPIManage(time: float, timeSta: float, timTrans: float, acicle: float) -> int:
    return 0


def AAPIPostManage(time: float, timeSta: float, timTrans: float, acicle: float) -> int:
    return 0


def AAPIFinish() -> int:
    return 0


def AAPIUnLoad() -> int:
    log.debug("AAPIUnLoad()")
    _SERVER.stop()
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


if __name__ == "__main__":
    raise ImportError("DO NOT RUN ME MANUALLY")

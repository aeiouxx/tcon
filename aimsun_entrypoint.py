"""
This file represents an entrypoint for the traffic control application, it must
be included in each scenario, where usage is required, directly via Aimsun
(Scenario > Properties > Aimsun Next APIs > Add).

Aimsun will then use the provided callbacks during simulation execution.

WARNING: While the simulation is paused / not executing, Aimsun holds the GIL.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable
import importlib
import sys
import pathlib
import json
from logging import Logger
from pydantic import BaseModel

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


def _import_one(name: str,
                alias: str = None,
                from_list: list[str] = None,
                *,
                base_path: str | pathlib.Path = pathlib.Path(__file__).parent) -> None:
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
        mod = importlib.reload(
            sys.modules[name]) if name in sys.modules else importlib.import_module(name)
        _MOD_MTIMES[name] = mtime


def _imports():
    _import_one("common.logger", from_list=["get_logger"])
    _import_one("common.models",
                from_list=["CommandType",
                           "Command",
                           "IncidentCreateDto",
                           "IncidentRemoveDto",
                           "IncidentsClearSectionDto",
                           "get_payload_cls"])
    _import_one("common.config",
                from_list=["AppConfig",
                           "ScheduledCommand",
                           "load_config"])
    _import_one("common.result", from_list=["Result"])
    _import_one("server.ipc", from_list=["ServerProcess"])


if TYPE_CHECKING:
    from common.logger import get_logger
    from common.models import (
        CommandType,
        Command,
        IncidentCreateDto,
        IncidentRemoveDto,
        IncidentsClearSectionDto,
        get_payload_cls)
    from common.config import AppConfig, ScheduledCommand, load_config
    from common.result import Result
    from server.ipc import ServerProcess
else:
    _imports()

    # < Module imports -------------------------------------------------------------
    # > Command handlers -----------------------------------------------------------
_CONFIG: AppConfig


if "_HANDLERS" not in globals():
    _HANDLERS: dict[CommandType, Callable[..., Result]] = {}


def register_handler(type: CommandType):
    def decorator(func: callable):
        _HANDLERS[type] = func
        return func
    return decorator


@register_handler(CommandType.INCIDENT_CREATE)
def _incident_create(payload: IncidentCreateDto) -> Result[int]:
    result = AKIGenerateIncident(
        payload.section_id,
        payload.lane,
        payload.position,
        payload.length,
        payload.ini_time,
        payload.duration,
        payload.visibility_distance,
        payload.update_id_group,
        payload.apply_speed_reduction,
        payload.upstream_distance_SR,
        payload.downstream_distance_SR,
        payload.max_speed_SR)
    return Result.from_aimsun(result,
                              msg_ok=f"Incident created successfuly, id: {result}.",
                              msg_fail="Incident creation failed")


@register_handler(CommandType.INCIDENT_REMOVE)
def _incident_remove(payload: IncidentRemoveDto) -> Result[int]:
    # WARNING: This literally doesn't work 99.999 % of the time
    # did some intern at aimsun do strict comparison on floating point values?
    result = AKIRemoveIncident(
        payload.section_id,
        payload.lane,
        payload.position)
    return Result.from_aimsun(result,
                              msg_ok=f"Removed incident from section: {payload.section_id}",
                              msg_fail="Incident removal failed")


@register_handler(CommandType.INCIDENTS_CLEAR_SECTION)
def _incident_clear_section(payload: IncidentsClearSectionDto) -> Result[int]:
    result = AKIRemoveAllIncidentsInSection(payload.section_id)
    return Result.from_aimsun(result,
                              msg_ok=f"Cleared incidents from section: {payload.section_id}",
                              msg_fail=f"Failed clearing incidents for section: {payload.section_id}")


@register_handler(CommandType.INCIDENTS_RESET)
def _incidents_reset() -> Result[int]:
    result = AKIResetAllIncidents()
    return Result.from_aimsun(result,
                              msg_ok="Cleared all incidents",
                              msg_fail="Failed clearing incidents")


# < Command handlers -----------------------------------------------------------
# > AAPI CALLBACKS -------------------------------------------------------------
log: Logger | None
config: AppConfig
_SERVER: ServerProcess | None


def _load():
    """Initialize the entrypoint on simulation load.

    This function reloads dependent modules to support hot reloading,
    loads the application configuration, initialises the logger and
    constructs the HTTP API server. Configuration may override the
    default host, port and log level. The global ``_CONFIG`` is set for
    later use when scheduling events.
    """
    _imports()
    global log, _SERVER, _CONFIG, _SCHEDULE
    # Right now we reload the config every time _load() is called
    # we could calculate the config hash + mtime, cache the config and only reload if either
    # one changes, this would be useful mostly for larger configs with large schedules though,
    # because revalidating each event might end up being somewhat costly
    _CONFIG = load_config()
    log = get_logger("aimsun.entrypoint")
    _SERVER = ServerProcess(host=_CONFIG.api_host,
                            port=_CONFIG.api_port)


def AAPILoad() -> int:
    _load()
    _SERVER.start()
    log.debug("AAPILoad()")
    return 0


def AAPIInit() -> int:
    return 0


def AAPISimulationReady() -> int:
    # TODO: Queue up commands that are contained in config file here
    return 0


def AAPIManage(time: float, timeSta: float, timTrans: float, acicle: float) -> int:
    for raw_cmd in _SERVER.try_recv_all():
        try:
            cmd: Command = Command.parse_obj(raw_cmd)
            log.debug("Received '%s' command, body:\n%s",
                      cmd.type.name,
                      json.dumps(cmd.payload, indent=2))
            handler = _HANDLERS.get(cmd.type)
            if handler is None:
                log.warning(
                    "No handler registered for command type: %s", cmd.type)
                continue
            dto_cls: BaseModel = get_payload_cls(cmd.type)
            payload = dto_cls.parse_obj(
                cmd.payload) if dto_cls is not None else cmd.payload
            result = handler(payload)
            if isinstance(result, Result):
                if result.is_ok():
                    log.info("%s", result.message)
                else:
                    log.warning("%s: %s (code=%d)",
                                result.message,
                                result.status.name,
                                result.raw_code)
        except Exception as e:
            log.exception("Failed when processing message: %s", e)
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


if __name__ == "__main__":
    import signal
    _load()
    log = get_logger("AIMSUN_ENTRY", "DEBUG", disable_ansi=False)
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    with ServerProcess() as srv:
        while True:
            if not srv._proc or not srv._proc.is_alive():
                log.critical("Server is not running")
                break
            for raw_cmd in srv.try_recv_all():
                try:
                    cmd: Command = Command.model_validate(raw_cmd)
                    log.info("Received command:\n%s", json.dumps(cmd.__dict__, indent=2))
                    handler = _HANDLERS.get(cmd.type)
                    if handler is None:
                        log.warning(
                            "No handler registered for command type: %s", cmd.type)
                        continue
                except Exception as e:
                    import time
                    time.sleep(1)
                    log.exception("Failed when processing message: %s", e)

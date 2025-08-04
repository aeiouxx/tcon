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
from inspect import signature

from itertools import count
from functools import singledispatch, wraps
from logging import Logger, DEBUG

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
                from_list: list[str] = None,
                *,
                base_path: str | pathlib.Path = pathlib.Path(__file__).parent) -> None:
    # WARNING: hot reloading modules with global scripts is not a good idea, unless
    # the scripts are idempotent!
    """
    Allows modifying imported code at runtime without having to relaunch Aimsun,
    just rerun the simulation to reload the imports.
    Reload `name` if its .py file changed. Supports:
      • import x                 -> hot_import("x")
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
        sys.modules[name] = mod
        try:
            assert spec.loader
            spec.loader.exec_module(mod)
        except Exception:
            sys.modules.pop(name, None)
            raise
        globals().update({sym: getattr(mod, sym) for sym in from_list})
        _MOD_MTIMES[name] = mtime
    else:
        mod = importlib.reload(
            sys.modules[name]) if name in sys.modules else importlib.import_module(name)
        _MOD_MTIMES[name] = mtime


def _imports():
    _import_one("common.logger", from_list=["get_logger"])
    _import_one("common.models",
                from_list=[
                    "Command",
                    "CommandType",
                    "CommandBase",
                    "IncidentCreateDto",
                    "IncidentRemoveDto",
                    "IncidentsClearSectionDto",
                    "MeasureCreateDto",
                    "MeasureSpeedSection",
                    "MeasureSpeedDetailed",
                    "MeasureLaneClosure",
                    "MeasureLaneClosureDetailed",
                    "MeasureLaneDeactivateReserved",
                    "MeasureTurnClose",
                    "MeasureRemoveCmd",
                    "MeasureRemoveDto"
                    "PolicyActivateCmd",
                    "PolicyDeactivateCmd",
                    "PolicyTargetDto"])
    _import_one("common.config", from_list=["AppConfig", "load_config"])
    _import_one("common.result", from_list=["Result"])
    _import_one("server.ipc", from_list=["ServerProcess"])
    _import_one("common.schedule", from_list=["Schedule"])


if TYPE_CHECKING:
    from common.config import AppConfig, load_config
    from common.logger import get_logger
    from common.models import (
        Command,
        CommandType,
        CommandBase,
        IncidentCreateDto,
        IncidentRemoveDto,
        IncidentsClearSectionDto,
        MeasureCreateDto,
        MeasureSpeedSection,
        MeasureSpeedDetailed,
        MeasureLaneClosure,
        MeasureLaneClosureDetailed,
        MeasureLaneDeactivateReserved,
        MeasureTurnClose,
        MeasureRemoveCmd,
        MeasureRemoveDto,
        PolicyActivateCmd,
        PolicyDeactivateCmd,
        PolicyTargetDto
    )
    from common.schedule import Schedule
    from common.result import Result
    from server.ipc import ServerProcess
    from common.status import AimsunStatus
else:
    _imports()
# < Module imports -------------------------------------------------------------


# > Command handlers -----------------------------------------------------------
if "_HANDLERS" not in globals():
    _HANDLERS: dict[CommandType, Callable[..., Result]] = {}


def register_handler(type: CommandType):
    """
    Decorate a `Plain` handler or `TimedHandler` and register it
    """
    def deco(fn):
        sig_len = len(signature(fn).parameters)
        if sig_len == 0:
            @wraps(fn)
            def wrapper(cmd: Command):
                return fn()
        elif sig_len == 1:
            @wraps(fn)
            def wrapper(cmd: Command):
                return fn(cmd.payload)
        elif sig_len == 2:
            @wraps(fn)
            def wrapper(cmd: Command):
                return fn(cmd.payload, cmd.time)
        else:
            raise TypeError(
                f"Handler for {type.value} must take 0, 1, or 2 positional "
                f"parameters, not {sig_len}")
        _HANDLERS[type] = wrapper
        return fn
    return deco
# > Incident dispatch ----------------------------------------------------------


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
                              msg_err="Incident creation failed")


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
                              msg_err="Incident removal failed")


@register_handler(CommandType.INCIDENTS_CLEAR_SECTION)
def _incident_clear_section(payload: IncidentsClearSectionDto) -> Result[int]:
    result = AKIRemoveAllIncidentsInSection(payload.section_id)
    return Result.from_aimsun(result,
                              msg_ok=f"Cleared incidents from section: {payload.section_id}",
                              msg_err=f"Failed clearing incidents for section: {payload.section_id}")


@register_handler(CommandType.INCIDENTS_RESET)
def _incidents_reset() -> Result[int]:
    result = AKIResetAllIncidents()
    return Result.from_aimsun(result,
                              msg_ok="Cleared all incidents",
                              msg_err="Failed clearing incidents")
# < Incident dispatch ----------------------------------------------------------


# > Measure dispatch -----------------------------------------------------------
@register_handler(CommandType.MEASURE_CREATE)
def _measure_create(payload: MeasureCreateDto, starts_at: float) -> Result[int]:
    m = payload.root
    result = _apply_measure(m)
    if (result.is_ok() and m.duration and m.duration > 0 and _SCHEDULE is not None):
        action_id = result.unwrap()
        ends_at = starts_at + m.duration
        _SCHEDULE.push(
            MeasureRemoveCmd(
                time=ends_at,
                payload=MeasureRemoveDto(id_action=action_id)))
        log.debug("Auto‑scheduled MEASURE_REMOVE id=%s at t=%.1f s", action_id, ends_at)

    return result


@register_handler(CommandType.MEASURE_REMOVE)
def _measure_remove(measure: MeasureRemoveDto) -> Result[int]:
    code = 0
    try:
        AKIActionRemoveActionByID(measure.id_action)
    except Exception as exc:
        log.exception(exc)
        code = AimsunStatus.UNKNOWN_ERROR
    return Result.from_aimsun(code,
                              msg_ok=f"Removed measure {measure.id_action}",
                              msg_err=f"Failed to remove measure {measure.id_action}")


@register_handler(CommandType.MEASURES_CLEAR)
def _measures_clear() -> Result[int]:
    pass


@singledispatch
def _apply_measure(measure) -> Result[int]:
    raise NotImplementedError(type(measure))


@_apply_measure.register
def _(m: MeasureSpeedSection) -> Result[int]:
    section_count = len(m.section_ids)
    section_id_arr: intArray = intArray(section_count)
    for i, sid in enumerate(m.section_ids):
        section_id_arr[i] = sid
    action_id = m.id_action or next(_ID_GEN)
    try:
        AKIActionAddSpeedActionByID(action_id,
                                    section_count,
                                    section_id_arr.cast(),
                                    m.speed,
                                    m.veh_type,
                                    m.compliance,
                                    m.consider_speed_acceptance)
    except Exception as exc:
        log.exception("Speed section API call failed: %s", exc)
        return Result.err("Speed-section action failed")

    return Result.ok(action_id,
                     f"Speed {m.speed} km/h on {m.section_ids} (id={action_id})")


@_apply_measure.register
def _(m: MeasureSpeedDetailed) -> Result[int]:
    section_count = len(m.section_ids)
    section_id_arr: intArray = intArray(section_count)
    for i, sid in enumerate(m.section_ids):
        section_id_arr[i] = sid
    action_id = m.id_action or next(_ID_GEN)
    try:
        AKIActionAddDetailedSpeedActionByID(action_id,
                                            section_count,
                                            section_id_arr.cast(),
                                            m.lane_id,
                                            m.from_segment_id,
                                            m.to_segment_id,
                                            m.speed,
                                            m.veh_type,
                                            m.compliance,
                                            m.consider_speed_acceptance)
    except Exception as exc:
        log.exception("Detailed-speed API call failed: %s", exc)
        return Result.err("Detailed-speed action failed")

    msg = (
        f"Speed {m.speed} km/h on sections {m.section_ids}, "
        f"lane {m.lane_id}, seg {m.from_segment_id}-{m.to_segment_id} "
        f"(id={action_id})"
    )
    return Result.ok(action_id, msg)


@_apply_measure.register
def _(m: MeasureLaneClosure) -> Result[int]:
    action_id = m.id_action or next(_ID_GEN)
    try:
        AKIActionCloseLaneActionByID(action_id,
                                     m.section_id,
                                     m.lane_id,
                                     m.veh_type)
    except Exception as exc:
        log.exception("Lane-closure API failed: %s", exc)
        return Result.err("Lane-closure action failed")

    msg = f"Closed lane {m.lane_id} in section {m.section_id} (id={action_id})"
    return Result.ok(action_id, msg)


@_apply_measure.register
def _(m: MeasureLaneClosureDetailed) -> Result[int]:
    action_id = m.id_action or next(_ID_GEN)
    try:
        AKIActionCloseLaneDetailedActionByID(action_id,
                                             m.section_id,
                                             m.lane_id,
                                             m.veh_type,
                                             m.apply_2LCF,
                                             m.visibility_distance)
    except Exception as exc:
        log.exception("Lane-closure API failed: %s", exc)
        return Result.err("Lane-closure action failed")

    msg = f"Closed lane {m.lane_id} in section {m.section} (id={action_id})"
    return Result.ok(action_id, msg)


@_apply_measure.register
def _(m: MeasureLaneDeactivateReserved) -> Result[int]:
    action_id = m.id_action or next(_ID_GEN)
    try:
        AKIActionDisableReservedLaneActionByID(action_id,
                                               m.section_id,
                                               m.lane_id,
                                               m.segment_id)
    except Exception as exc:
        log.exception("Lane unreserve API failed: %s", exc)
        return Result.err("Lane unreserve action failed")

    msg = f"Unreserved lane {m.lane_id} in section {m.section_id} (id={action_id})"
    return Result.ok(action_id, msg)


@_apply_measure.register
def _(m: MeasureTurnClose) -> Result[int]:
    action_id = m.id_action or next(_ID_GEN)
    try:
        AKIActionAddCloseTurningODActionByID(action_id,
                                             m.from_section_id,
                                             m.to_section_id,
                                             m.origin_centroid,
                                             m.destination_centroid,
                                             m.veh_type,
                                             m.compliance,
                                             m.visibility_distance,
                                             m.local_effect,
                                             m.section_affecting_path_cost_id)
    except Exception as exc:
        log.exception("Close-turn API failed: %s", exc)
        return Result.err("Close-turn action failed")
    msg = (
        f"Closed turn {m.from_section_id}→{m.to_section_id} "
        f"(veh_type={m.veh_type}, id={action_id})"
    )
    return Result.ok(action_id, msg)

# < Measure dispatch -----------------------------------------------------------


# > Policy dispatch ------------------------------------------------------------
@register_handler(CommandType.POLICY_ACTIVATE)
def _policy_activate(payload: PolicyTargetDto):
    try:
        ANGConnActivatePolicy(payload.policy_id)
    except Exception as exc:
        log.exception("Policy activate API failed: %s", exc)
        return Result.err("Policy activate action failed")
    msg = f"Activated policy '{payload.policy_id}'."
    return Result.ok(payload.policy_id, msg)


@register_handler(CommandType.POLICY_DEACTIVATE)
def _policy_deactivate(payload: PolicyTargetDto):
    try:
        ANGConnDeactivatePolicy(payload.policy_id)
    except Exception as exc:
        log.exception("Policy deactivate API failed: %s", exc)
        return Result.err("Policy deactivate action failed")
    msg = f"Deactivated policy '{payload.policy_id}'."
    return Result.ok(payload.policy_id, msg)
# < Policy dispatch ------------------------------------------------------------


def _execute(cmd: Command) -> None:
    """
    Execute one validated Command
    """
    handler = _HANDLERS.get(cmd.command)
    if handler is None:
        log.warning(
            "No handler registered for command type: %s", cmd.command)
        return

    try:
        res = handler(cmd)
        if isinstance(res, Result):
            if res.is_ok():
                log.info("%s", res.message)
            else:
                log.warning("%s:%s (code=%s)",
                            res.message,
                            res.status.name,
                            res.raw_code)
    except Exception:
        log.exception("Unhandled error in handler for %s", cmd.command)


def _process_ipc(current_time: float) -> None:
    if not _SERVER:
        return
    if not _SCHEDULE:
        return
    for raw_cmd in _SERVER.try_recv_all():
        try:
            cmd: Command = Command.model_validate(raw_cmd)
            if log.isEnabledFor(DEBUG):
                log.debug("IPC‑recv %s, time=%s:\n%s",
                          cmd.command,
                          cmd.time,
                          json.dumps(cmd.payload.model_dump(), indent=2))
            if cmd.time <= current_time:
                _execute(cmd)
            else:
                _SCHEDULE.push(cmd)
        except Exception as e:
            log.exception("Failed when processing message: %s", e)


def _process_schedule(up_to: float) -> None:
    if not _SCHEDULE:
        return
    for cmd in _SCHEDULE.ready(up_to):
        log.debug("Scheduled %s fired at %.2f s", cmd.command, up_to)
        _execute(cmd)
# < Command handlers -----------------------------------------------------------


# > AAPI callbacks -------------------------------------------------------------
log: Logger | None
_CONFIG: AppConfig
_SCHEDULE: Schedule
_SERVER: ServerProcess | None
_ID_GEN = None


def _load():
    """Initialize the entrypoint on simulation load.

    This function reloads dependent modules to support hot reloading,
    loads the application configuration, initialises the logger and
    constructs the HTTP API server."""
    _imports()
    global log, _SERVER, _CONFIG, _SCHEDULE, _ID_GEN

    # hash / mtime on config -> cache it?
    _CONFIG = load_config()
    log = get_logger("aimsun.entrypoint")
    _SERVER = ServerProcess(host=_CONFIG.api_host, port=_CONFIG.api_port)
    _SCHEDULE = _CONFIG.schedule
    _ID_GEN = count(1)


def AAPILoad() -> int:
    _load()
    _SERVER.start()
    log.debug("AAPILoad()")
    return 0


def AAPIInit() -> int:
    return 0


def AAPISimulationReady() -> int:
    _process_schedule(up_to=0.0)
    return 0


def AAPIManage(time: float, timeSta: float, timTrans: float, acicle: float) -> int:
    _process_ipc(current_time=timeSta)
    _process_schedule(up_to=timeSta)
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

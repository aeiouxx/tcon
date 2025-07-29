"""
    Configuration loading utilities.

    Configuration can be provided via a JSON or YAML file
    whose location defaults to ``config.json`` in the project root.

    The configuration file may specify API parameters, logging levels and a list of
    scheduled events that are applied when the simulation is ready.

    The ``ScheduledCommand`` structure represents a scheduled command and
    corresponds roughly to a message that would otherwise be sent via the REST
    API.

    Each event has a ``command`` (matching the ``CommandType``), a
    ``time`` indicating when it should be executed (simulation seconds from
    midnight) and a ``payload`` dictionary containing the parameters for the
    command.

    With this mechanism it is possible to schedule commands that the API does not provide
    a way to schedule such as clear all incidents, clear section, etc...

    The ``AppConfig`` structure represents the entire application configuration,
    ``api_host`` and ``api_port`` server to configure the REST API.

    The ``schedule`` list contains ``ScheduledCommand`` instances and is used to schedule
    commands when the simulation starts

    The configuration file is optional, if it's missing or invalid, defaults will be supplied and
    no additional events will be scheduled.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from common.models import CommandType
from common.logger import get_log_manager, get_logger


log = get_logger(__name__)


@dataclass
class ScheduledCommand:
    """Represents a scheduled command loaded from configuration.

    Attributes
    ----------
    command:
        The command type corresponding to ``CommandType``. Must match one
        of the known command identifiers such as ``incident_create`` or
        ``measure_create``.
    time:
        Simulation time (seconds from midnight) at which to execute the
        command. Events are executed when the current simulation time is
        greater than or equal to this value.
    payload:
        Arbitrary payload dictionary. The structure depends on the
        command type. It is passed to the handler unchanged.
    """

    # TODO: just use Command directly?
    command: CommandType
    time: float
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # TODO: retrieve command model from registry, run validators
        # and check against ini_time if exists?
        ini_time = self.payload.get("ini_time")
        if ini_time is not None and ini_time <= self.time:
            raise ValueError(
                f"Scheduled command '{self.command.value}' is set to execute at {self.time}, "
                f"but it's payload ini_time is '{ini_time}', ini_time must be greater than schedule time.")


@dataclass
class AppConfig:
    """Top-level configuration loaded from file

    Attributes
    ----------
    api_host:
        Optional override for the API host. If ``None`` the default
        ``ServerProcess`` host is used.
    api_port:
        Optional override for the API port. If ``None`` the default
        ``ServerProcess`` port is used.
    schedule:
        Sequence of scheduled command that should be executed when the
        simulation runs either at a particular time or immediately.
        If empty, no events will be scheduled.
        WARNING: Schedule execution depends on simulation step, meaning
        events will get executed when simulation time >= ScheduledCommand.time
        as we could advance past the specific time because of our step value `acicle`
    """
    api_host: Optional[str] = None
    api_port: Optional[str] = None
    schedule: List[ScheduledCommand] = field(default_factory=list)


def _load_json(path: pathlib.Path) -> Dict[str, Any]:
    """Load JSON configuration from disk."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.exception("Failed to read config file '%s': %s", path, exc)
        return {}


def load_config(path: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent / "config.json") -> AppConfig:
    log.info("Reading config from path: '%s'", path)
    data = _load_json(path)
    if not data:
        return AppConfig()
    api_host = data.get("api", {}).get("host")
    api_port = data.get("api", {}).get("port")

    log_manager = get_log_manager()
    log_cfg = data.get("log", {})
    default_level = log_manager.parse_level(log_cfg.get("level", "INFO"))
    log_manager.default_level = default_level

    module_config = log_cfg.get("modules", {})
    for mod_name, settings in module_config.items():
        log_manager.configure_component(
            name=mod_name,
            level=settings.get("level"),
            logfile=settings.get("logfile"),
            ansi=settings.get("ansi"))

    schedule: List[ScheduledCommand] = []
    schedule_data = data.get("schedule", [])
    for item in schedule_data:
        try:
            log.debug("Processing: '%s'", json.dumps(item, indent=2))
            cmd_type_str = item.get("command")
            if not cmd_type_str:
                log.warning("Skipping entry with missing 'command': %s", item)
                continue
            cmd_type = CommandType(cmd_type_str)
            time_val = float(item.get("time", 0.0))
            payload = item.get("payload", {})
            schedule.append(ScheduledCommand(command=cmd_type, time=time_val, payload=payload))
        except ValueError as exc:
            log.exception("Error parsing entry: %s", exc)
            raise  # let's warn the user i guess
        except Exception as exc:
            log.exception("Error parsing entry: %s", exc)
            continue

    return AppConfig(api_host=api_host,
                     api_port=api_port,
                     schedule=schedule)

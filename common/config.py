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
from typing import Any, Dict, List, Final, ClassVar
from pydantic import ValidationError

from common.models import CommandType, ScheduledCommand, ScheduleRoot
from common.logger import get_log_manager, get_logger
from common.schedule import Schedule


log = get_logger(__name__)


@dataclass
class AppConfig:
    # For now just loads the whole config into memory, in
    # the future we can improve by adding stream / iterator support
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
    DEFAULT_HOST: ClassVar[Final[str]] = "127.0.0.1"
    DEFAULT_PORT: ClassVar[Final[int]] = 6969
    api_host: str = DEFAULT_HOST
    api_port: int = DEFAULT_PORT
    schedule: Schedule = field(default_factory=Schedule)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        if not data:
            return AppConfig()
        api_cfg = data.get("api", {})
        api_host = api_cfg.get("host") or AppConfig.DEFAULT_HOST
        api_port = api_cfg.get("port") or AppConfig.DEFAULT_PORT

        log_manager = get_log_manager()
        log_cfg = data.get("log", {})
        log_manager.default_level = log_manager.parse_level(log_cfg.get("level", "INFO"))

        for mod_name, settings in log_cfg.get("modules", {}).items():
            log_manager.configure_component(
                name=mod_name,
                level=settings.get("level"),
                logfile=settings.get("logfile"),
                ansi=settings.get("ansi"))

        log.debug("Reading schedule...")
        raw_schedule = data.get("schedule", [])
        try:
            parsed = ScheduleRoot.model_validate(raw_schedule)
            schedule = Schedule(parsed.root)
            log.info(f"Schedule parsed without errors, size: {len(schedule)}")
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(p) for p in err["loc"])
                log.error("Config error at %s → %s (input=%r)",
                          loc, err["msg"], err.get("input"))
            raise
        return AppConfig(api_host=api_host,
                         api_port=api_port,
                         schedule=schedule)


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
    return AppConfig.from_dict(data)

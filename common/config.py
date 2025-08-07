"""
    Configuration loading utilities.

    Configuration can be provided via a JSON file ```config.json``` located in the project root

    The configuration file may specify API parameters, logging levels and a [list of]
    schedule file[s] which can contain scheduled commands, the schedule can be placed in the
    configuration file itself as well via the "schedule" key

    Each event has a ``command`` (matching the ``CommandType``), a
    ``time`` indicating when it should be executed (simulation seconds from
    midnight) and a ``payload`` dictionary containing the parameters for the
    command.

    With this mechanism it is possible to schedule commands that the API does not provide
    a way to schedule such as clear all incidents, clear section, etc...

    The ``AppConfig`` structure represents the entire application configuration,
    ``api_host`` and ``api_port`` server to configure the REST API.

    The ``schedule`` list contains ``Command`` instances and is used to schedule
    commands when the simulation starts

    The configuration file and the schedule files are optional, if it's missing or invalid, defaults will be supplied and
    no additional command will be scheduled.
"""

from __future__ import annotations

import json
import yaml
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, Final, ClassVar, List
from pydantic import ValidationError

from common.models import ScheduleRoot
from common.logger import get_log_manager, get_logger
from common.schedule import Schedule
from common.constants import get_project_root


log = get_logger(__name__)

# TODO: Separate app config and schedules?
# config.json, schedule.yaml or json?


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

    @staticmethod
    def _iter_schedule_chunks(cfg: Dict[str, Any]) -> List[Any]:
        """Yield schedule chunks (lists) in the order they are defined in the config mapping"""
        for key, value in cfg.items():
            if key == "schedule":
                if value:
                    yield value
            elif key in {"schedule_file", "schedule_files"}:
                files = value if isinstance(value, list) else [value]
                for file in files:
                    if not file:
                        continue
                    yield ("@file", file)

    @classmethod
    def _parse_schedule(cls,
                        cfg: Dict[str, Any],
                        cfg_dir: pathlib.Path) -> Schedule:
        errors: list[str] = []
        schedule: Schedule = Schedule()

        def _try_insert(raw, label: str):
            nonlocal schedule
            nonlocal errors
            try:
                validated = ScheduleRoot.model_validate(raw).root
                schedule.extend(validated)
            except ValidationError as exc:
                for err in exc.errors():
                    loc = ".".join(map(str, err["loc"]))
                    msg = f"{label}:{loc} -> {err['msg']} (input={err.get('input')!r})"
                    errors.append(msg)
                return

        for chunk in cls._iter_schedule_chunks(cfg):
            if isinstance(chunk, tuple) and chunk[0] == "@file":
                path = pathlib.Path(chunk[1])
                if not path.is_absolute():
                    path = cfg_dir / path
                log.info("Loading schedule file: %s", path)
                _try_insert(_load_by_extension(path), str(path))
            else:
                _try_insert(chunk, "inline.schedule")

        if errors:
            log.error("Schedule contains errors:\n" + "\n".join(errors))

        return schedule

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

        log.debug("Processing schedule...")
        schedule = cls._parse_schedule(data,
                                       get_project_root())
        log.info("Loaded schedule, %d entries", len(schedule))
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


def _load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    """Load YAML file from disk"""
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        log.exception("Failed to read config file '%s': %s", path, exc)
        return {}


def _load_by_extension(path: pathlib.Path) -> Dict[str, Any]:
    try:
        if path.suffix.lower() in {".yml", ".yaml"}:
            return _load_yaml(path)
        return _load_json(path)
    except Exception as exc:
        log.exception("Failed to read '%s': %s", path, exc)
        return {}


def load_config(path: pathlib.Path | None = None) -> AppConfig:
    """
    Load main configuration; if *path* is None, default to
    <PROJECT_ROOT>/config.json.
    """
    if path is None:
        path = get_project_root() / "config.json"
    log.info("Reading config from path: '%s'", path)
    data = _load_by_extension(path)
    return AppConfig.from_dict(data)

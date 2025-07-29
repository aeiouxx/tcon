import json
import pytest
from pathlib import Path
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

from unittest.mock import MagicMock

from common.config import load_config, ScheduledCommand, AppConfig
from common.models import CommandType
from common.logger import get_log_manager
from pydantic import ValidationError

# If we wanted to unit test, we can just call from_dict directly on data instead of writing cfg


# Helpers ----------------------------------------------------------------------
def _write_config(path: Path, data: dict) -> None:
    """Helper to write config data to disk."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f)


# > GENERIC CONFIG TESTS -------------------------------------------------------
def test_empty_config_file(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_config(config_path, {})
    config = load_config(config_path)
    assert isinstance(config, AppConfig)
    assert config.api_host == AppConfig.DEFAULT_HOST
    assert config.api_port == AppConfig.DEFAULT_PORT
    assert len(config.schedule) == 0


def test_invalid_json_fallback(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{ invalid json }", encoding="utf-8")
    config = load_config(config_path)
    assert isinstance(config, AppConfig)
    assert len(config.schedule) == 0
# < GENERIC CONFIG TESTS -------------------------------------------------------


# > LOG CONFIG TESTS -----------------------------------------------------------
def test_logger_global_level(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, {"log": {"level": "WARNING"}})

    load_config(cfg_path)
    log = get_log_manager().get_logger("any.module")

    assert log.level == WARNING
#
#


def test_logger_module_override(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    _write_config(
        cfg_path,
        {
            "log": {
                "level": "ERROR",
                "modules": {"my.mod": {"level": "DEBUG"}}
            }
        }
    )

    load_config(cfg_path)
    assert get_log_manager().get_logger("my.mod").level == DEBUG
    assert get_log_manager().get_logger("other.mod").level == ERROR


def test_logger_logfile_resolved(tmp_path: Path, monkeypatch):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    rel = "logs/x.log"

    cfg_path = tmp_path / "config.json"
    _write_config(
        cfg_path,
        {"log": {"modules": {"m.a": {"level": "INFO", "logfile": rel}}}}
    )

    monkeypatch.setattr("common.logger.get_project_root", lambda: tmp_path)
    load_config(cfg_path)

    h_files = [
        Path(h.baseFilename).resolve()
        for h in get_log_manager().get_logger("m.a").handlers
        if hasattr(h, "baseFilename")
    ]
    assert (logs_dir / "x.log").resolve() in h_files
# < LOG CONFIG TESTS -----------------------------------------------------------


# > SCHEDULING TESTS -----------------------------------------------------------
def test_missing_command_field_raises(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    _write_config(cfg_path, {"schedule": [{"time": 1, "payload": {}}]})

    with pytest.raises(ValidationError) as exc:
        load_config(cfg_path)

    assert "0.command" in str(exc.value)


def test_schedule_parsing_incident_clear(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    _write_config(
        cfg_path,
        {
            "api": {"host": "127.1.1.1", "port": 9999},
            "schedule": [
                {
                    "command": "incidents_clear_section",
                    "time": 300.0,
                    "payload": {"section_id": 42}
                }
            ]
        }
    )

    cfg = load_config(cfg_path)

    assert cfg.api_host == "127.1.1.1"
    assert cfg.api_port == 9999                         # coerced to int
    sc: ScheduledCommand = next(iter(cfg.schedule))

    assert sc.command is CommandType.INCIDENTS_CLEAR_SECTION
    assert sc.time == 300.0
    assert sc.payload.section_id == 42                  # payload is DTO


def test_ini_time_before_schedule_raises(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    _write_config(
        cfg_path,
        {
            "schedule": [
                {
                    "command": "incident_create",
                    "time": 120,
                    "payload": {
                        "section_id": 1,
                        "lane": 1,
                        "position": 0,
                        "length": 5,
                        "ini_time": 100,
                        "duration": 30
                    }
                }
            ]
        }
    )

    with pytest.raises(ValidationError) as exc:
        load_config(cfg_path)

    assert "payload.ini_time" in str(exc.value)

# < SCHEDULING TESTS -----------------------------------------------------------

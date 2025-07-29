import json
import pytest
from pathlib import Path
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

from unittest.mock import MagicMock

from common.config import load_config, ScheduledCommand, AppConfig
from common.models import CommandType
from common.logger import get_log_manager


def write_config(path: Path, data: dict) -> None:
    """Helper to write config data to disk."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f)


# > GENERIC CONFIG TESTS -------------------------------------------------------
def test_empty_config_file(tmp_path: Path):
    config_path = tmp_path / "config.json"
    write_config(config_path, {})
    config = load_config(config_path)
    assert isinstance(config, AppConfig)
    assert config.api_host == AppConfig.DEFAULT_HOST
    assert config.api_port == AppConfig.DEFAULT_PORT
    assert config.schedule == []


def test_invalid_json_fallback(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{ invalid json }", encoding="utf-8")
    config = load_config(config_path)
    assert isinstance(config, AppConfig)
    assert config.schedule == []

# < GENERIC CONFIG TESTS -------------------------------------------------------

# > LOG CONFIG TESTS -----------------------------------------------------------


def test_logger_global_level_is_applied(tmp_path: Path):
    config_path = tmp_path / "config.json"
    data = {
        "log": {
            "level": "WARNING"
        }
    }
    write_config(config_path, data)
    load_config(config_path)
    log = get_log_manager().get_logger("global.test")
    assert log.level == WARNING


def test_logger_module_level_override(tmp_path: Path):
    config_path = tmp_path / "config.json"
    data = {
        "log": {
            "level": "ERROR",
            "modules": {
                "module.test": {
                    "level": "DEBUG"
                }
            }
        }
    }
    write_config(config_path, data)
    load_config(config_path)
    log = get_log_manager().get_logger("module.test")
    assert log.level == DEBUG

    log = get_log_manager().get_logger("some.module")
    assert log.level == ERROR


def test_logger_logfile_relative_to_project_root(tmp_path: Path, monkeypatch):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    rel_path = "logs/test_module.log"
    abs_path = logs_dir / "test_module.log"

    config_path = tmp_path / "config.json"
    data = {
        "log": {
            "modules": {
                "test.module": {
                    "level": "INFO",
                    "logfile": rel_path
                }
            }
        }
    }
    write_config(config_path, data)

    monkeypatch.setattr("common.logger.get_project_root", lambda: tmp_path)

    load_config(config_path)
    get_log_manager().print_config()
    logger = get_log_manager().get_logger("test.module")

    log_paths = [Path(h.baseFilename) for h in logger.handlers if hasattr(h, "baseFilename")]
    assert any(p.resolve() == abs_path.resolve() for p in log_paths)
# < LOG CONFIG TESTS -----------------------------------------------------------
# > SCHEDULED COMMAND TESTS ----------------------------------------------------


def test_valid_schedule_parsing(tmp_path: Path):
    config_path = tmp_path / "config.json"
    data = {
        "api": {"host": "127.1.1.1", "port": "9999"},
        "log": {"level": "INFO"},
        "schedule": [
            {
                "command": "incidents_clear_section",
                "time": 300.0,
                "payload": {"section_id": 99}
            }
        ]
    }
    write_config(config_path, data)
    config = load_config(config_path)

    assert config.api_host == "127.1.1.1"
    assert config.api_port == "9999"
    assert len(config.schedule) == 1

    cmd = config.schedule[0]
    assert isinstance(cmd, ScheduledCommand)
    assert cmd.command == CommandType.INCIDENTS_CLEAR_SECTION
    assert cmd.time == 300.0
    assert cmd.payload["section_id"] == 99


def test_schedule_entry_with_missing_command_is_ignored(tmp_path: Path, monkeypatch):
    import common.config
    mock_logger = MagicMock()
    monkeypatch.setattr(common.config, "log", mock_logger)

    config_path = tmp_path / "config.json"
    data = {
        "schedule": [
            {"time": 123.4, "payload": {"x": 1}},
            {"command": "incident_remove", "time": 456.0, "payload": {"section_id": 5, "lane": 1, "position": 50.0}}
        ]
    }
    write_config(config_path, data)
    config = load_config(config_path)

    mock_logger.warning.assert_called_once()  # warn about skipped entry with missing command
    assert len(config.schedule) == 1
    assert config.schedule[0].command == CommandType.INCIDENT_REMOVE


def test_command_with_ini_time_at_or_before_schedule_is_rejected(tmp_path: Path):
    config_path = tmp_path / "config.json"
    data = {
        "schedule": [
            {
                "command": "incident_create",
                "time": 120.0,
                "payload": {
                    "section_id": 1,
                    "lane": 1,
                    "position": 100.0,
                    "length": 10.0,
                    "ini_time": 100.0,
                    "duration": 60.0
                }
            }
        ]
    }
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ValueError, match="ini_time"):
        load_config(config_path)
# < LOG CONFIG TESTS ----------------------------------------------------------

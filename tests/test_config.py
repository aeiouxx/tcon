import json
import os
import sys
import tempfile
import unittest
import pathlib
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

from pydantic import ValidationError

from common.config import load_config, AppConfig
from common.logger import get_log_manager
from common.models import (
    Command,
    CommandType,
    CommandBase,
)
from common.schedule import Schedule


TEST_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestConfigParsing(unittest.TestCase):
    def setUp(self):
        mgr = get_log_manager()
        mgr.default_level = mgr.parse_level("INFO")
        mgr.component_config.clear()
        mgr._cache.clear()

    def test_empty_config_file(self):
        """Empty config should use defaults"""
        cfg = AppConfig.from_dict({})
        self.assertEqual(cfg.api_host, AppConfig.DEFAULT_HOST)
        self.assertEqual(cfg.api_port, AppConfig.DEFAULT_PORT)
        self.assertEqual(len(cfg.schedule), 0)

    def test_override_api(self):
        """API configuration should apply"""
        cfg = AppConfig.from_dict({"api": {"host": "0.0.0.0", "port": 9999}})
        self.assertEqual(cfg.api_host, "0.0.0.0")
        self.assertEqual(cfg.api_port, 9999)

    def test_logging_config(self):
        """Global log level and module overrides should apply"""
        cfg_dict = {
            "log": {
                "level": "DEBUG",
                "modules": {
                    "common.config": {"level": "ERROR", "ansi": True},
                },
            }
        }
        cfg = AppConfig.from_dict(cfg_dict)
        mgr = get_log_manager()
        self.assertEqual(mgr.default_level, mgr.parse_level("DEBUG"))
        self.assertIn("common.config", mgr.component_config)
        self.assertEqual(mgr.component_config["common.config"]["level"], mgr.parse_level("ERROR"))
        self.assertTrue(mgr.component_config["common.config"]["ansi"])
        self.assertEqual(len(cfg.schedule), 0)

    def test_relative_logfile_resolution(self):
        """Relative logfile paths in module overrides should be relative to the project root."""
        rel_logfile = "logs/testcfg.log"
        cfg_dict = {
            "log": {
                "modules": {
                    "common.config": {"level": "ERROR", "logfile": rel_logfile},
                }
            }
        }
        AppConfig.from_dict(cfg_dict)

        mgr = get_log_manager()
        override = mgr.component_config.get("common.config")
        self.assertIsNotNone(override)

        abs_path = override.get("logfile")
        expected = pathlib.Path(PROJECT_ROOT) / rel_logfile
        self.assertEqual(abs_path, expected)

    def test_valid_schedule(self):
        """Valid schedules should be parsed into Schedule instances of correct length."""
        cfg_dict = {
            "schedule": [
                {
                    "command": CommandType.INCIDENT_CREATE,
                    "payload": {
                        "section_id": 1,
                        "lane": 1,
                        "position": 0.0,
                        "length": 1.0,
                        "ini_time": 10.0,
                        "duration": 5.0,
                    },
                },
                {
                    "command": CommandType.MEASURE_CREATE,
                    "time": 5.0,
                    "payload": {
                        "type": "speed_section",
                        "section_ids": [1],
                        "speed": 20.0,
                    },
                },
            ]
        }
        cfg = AppConfig.from_dict(cfg_dict)
        self.assertIsInstance(cfg.schedule, Schedule)
        self.assertEqual(len(cfg.schedule), 2)

    def test_invalid_schedule_raises(self):
        """Schedules containing invalid entries should raise a ValidationError."""
        cfg_dict = {
            "schedule": [
                {
                    "command": "incident_create",
                    "payload": {"section_id": 1},  # <-- missing mandatory fields, should raise error
                }
            ]
        }
        with self.assertRaises(ValidationError):
            AppConfig.from_dict(cfg_dict)

    def test_implicit_time_is_set(self):
        """Entries without time field should have it set to `CommandBase.IMMEDIATE` implicitly"""
        cfg_dict = {
            "schedule": [
                {
                    "command": "incident_create",
                    # "time": -1, <-- should be implicit if omitted to schedule immediately
                    "payload": {
                        "section_id": 492,
                        "lane": 1,
                        "position": 0.0,
                        "length": 5.0,
                        "ini_time": 0,
                        "duration": 60
                    }
                }
            ]
        }

        cfg = AppConfig.from_dict(cfg_dict)
        sch: Schedule = cfg.schedule

        assert len(sch) == 1
        assert sch.peek_time() == CommandBase.IMMEDIATE

        due = list(sch.ready(0))
        assert len(due) == 1
        assert due[0].command is CommandType.INCIDENT_CREATE

    def test_schedule_sorts_by_time(self):
        """Schedule should reorder entries by time"""
        cfg_dict = {
            "schedule": [
                {   # fires third
                    "command": "incidents_reset",
                    "time": 300,
                },
                {   # fires FIRST
                    "command": "incident_remove",
                    "time": 50,
                    "payload": {"section_id": 1, "lane": 1, "position": 0.0}
                },
                {   # fires second
                    "command": "measure_remove",
                    "time": 150,
                    "payload": {"id_action": 42}
                }
            ]
        }
        cfg = AppConfig.from_dict(cfg_dict)
        sch: Schedule = cfg.schedule

        set_all_ready_time = 1e9
        times = [sc.time for sc in sch.ready(set_all_ready_time)]
        assert times == sorted(times) == [50, 150, 300]

    def test_load_config_from_missing_file(self):
        path = pathlib.Path(tempfile.gettempdir()) / "test-config-no-exist.json"
        if path.exists():
            os.remove(path)
        cfg = load_config(path)
        self.assertEqual(cfg.api_host, AppConfig.DEFAULT_HOST)
        self.assertEqual(cfg.api_port, AppConfig.DEFAULT_PORT)
        self.assertEqual(len(cfg.schedule), 0)

    def test_load_config_valid_file(self):
        """Loading from a valid JSON file should parse correctly."""
        tmp = tempfile.NamedTemporaryFile("w", delete=False)
        cfg_dict = {
            "api": {
                "host": "123.123.123.123",
                "port": 6969
            },
            "log": {
                "level": "INFO",
                "ansi": False,
                "modules": {
                    "aimsun.entrypoint": {
                        "level": "DEBUG",
                        "ansi": False,
                        "logfile": None
                    },
                    "server.ipc": {
                        "level": "INFO",
                        "ansi": False,
                        "logfile": None
                    },
                    "server.api": {
                        "level": "INFO",
                        "ansi": True,
                        "logfile": None
                    },
                    "common.config": {
                        "level": "INFO",
                        "ansi": False,
                        "logfile": None
                    }
                }
            },
            "schedule": [
                {
                    "command": "incidents_reset",
                    "time": 123.321
                },
                {
                    "command": "incident_create",
                    "payload": {
                        "section_id": 492,
                        "lane": 1,
                        "position": 10.0,
                        "length": 25.0,
                        "ini_time": 60.0,
                        "duration": 300,
                        "apply_speed_reduction": True,
                        "max_speed_SR": 20
                    }
                },
                {
                    "command": "measure_create",
                    "time": 360,
                    "payload": {
                        "type": "speed_section",
                        "section_ids": [492],
                        "speed": 5,
                        "duration": 300
                    }
                },
                {
                    "command": "measure_create",
                    "time": 660,
                    "payload": {
                        "type": "lane_closure",
                        "duration": 300,
                        "section_id": 492,
                        "lane_id": 1
                    }
                }
            ]
        }
        json.dump(cfg_dict, tmp)
        tmp.close()
        try:
            cfg = load_config(pathlib.Path(tmp.name))
            self.assertEqual(cfg.api_host, "123.123.123.123")
            self.assertEqual(cfg.api_port, 6969)
            self.assertEqual(len(cfg.schedule), 4)
        finally:
            os.unlink(tmp.name)

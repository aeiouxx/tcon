import types
import sys
import pytest
import tempfile
import shutil
import signal
import time
import server.api
from pathlib import Path
from unittest.mock import MagicMock
from common.logger import get_log_manager


@pytest.fixture(autouse=True)
def fake_aapi(monkeypatch):
    aapi = types.ModuleType("AAPI")
    aapi.AAPICreateIncident = lambda *a, **k: None
    aapi.AAPIRemoveIncident = lambda *a, **k: None
    sys.modules["AAPI"] = aapi


@pytest.fixture
def tmp_path() -> Path:
    path = Path(tempfile.mkdtemp(prefix="tcon_tests_"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def mock_logger(monkeypatch):
    """Optional fixture to mock all loggers for the current test only."""
    mock = MagicMock()
    monkeypatch.setattr(get_log_manager(), "get_logger", lambda name: mock)
    return mock

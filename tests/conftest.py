import types
import sys
import pytest
import tempfile
import shutil
import signal
import time
import server.api
from pathlib import Path


@pytest.fixture(autouse=True)
def fake_aapi(monkeypatch):
    aapi = types.ModuleType("AAPI")
    aapi.AAPICreateIncident = lambda *a, **k: None
    aapi.AAPIRemoveIncident = lambda *a, **k: None
    sys.modules["AAPI"] = aapi


def _dummy_run_api(*_args, **_kwargs):
    # Block until SIGTERM, then exit.  Keeps the child alive for assertions.
    signal.signal(signal.SIGTERM, lambda *_: exit(0))
    while True:
        time.sleep(0.1)


@pytest.fixture(autouse=True)
def patch_api(monkeypatch):
    monkeypatch.setattr(server.api, "run_api_process", _dummy_run_api)
    yield


@pytest.fixture
# type: ignore[override] – we shadow the built‑in on purpose
def tmp_path() -> Path:
    path = Path(tempfile.mkdtemp(prefix="tcon_tests_"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

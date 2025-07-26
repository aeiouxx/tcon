import types
import sys
import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture(autouse=True)
def fake_aapi(monkeypatch):
    aapi = types.ModuleType("AAPI")
    aapi.AAPICreateIncident = lambda *a, **k: None
    aapi.AAPIRemoveIncident = lambda *a, **k: None
    sys.modules["AAPI"] = aapi


@pytest.fixture
# type: ignore[override] – we shadow the built‑in on purpose
def tmp_path() -> Path:
    path = Path(tempfile.mkdtemp(prefix="tcon_tests_"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

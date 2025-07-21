import types
import sys
import pytest


@pytest.fixture(autouse=True)
def fake_aapi(monkeypatch):
    aapi = types.ModuleType("AAPI")
    aapi.AAPICreateIncident = lambda *a, **k: None
    aapi.AAPIRemoveIncident = lambda *a, **k: None
    sys.modules["AAPI"] = aapi

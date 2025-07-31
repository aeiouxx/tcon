"""
Requires the real server.api implementation and the DTO pydantic models.
Mark with `pytest -m integration` to run only these slower, networked tests.
"""
from __future__ import annotations

import contextlib
import socket
import time

import httpx
import pytest
from server.ipc import ServerProcess
from common.models import (
    CommandType,
    IncidentCreateDto,
    IncidentRemoveDto,
    IncidentsClearSectionDto)
from common.http import HTTPMethod
from http import HTTPStatus


# helpers
def _free_port() -> int:
    """Return a random free TCP port on localhost."""
    with contextlib.closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_ready(client: httpx.Client,
                      timeout: float = 10.0,
                      step: float = 0.1) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if client.get("/health").status_code == HTTPStatus.OK:
                return True
        except httpx.TransportError:
            pass
        time.sleep(step)
    return False


# --------------------------------------------------------------------------- #
# Test                                                                        #
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_full_stack_with_dtos():
    pass

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
    port = _free_port()
    srv = ServerProcess(host="127.0.0.1", port=port)
    srv.start()

    try:
        client = httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            timeout=5)

        # 1)  /health --------------------------------------------------------
        assert _wait_until_ready(client)

        # 2)  POST /incident  -----------------------------------------------
        create_dto = IncidentCreateDto(
            section_id=1,
            lane=1,
            position=0.0,
            length=10.0,
            ini_time=0.0,
            duration=600.0,
        )
        r = client.post("/incident", json=create_dto.model_dump())
        assert r.status_code == HTTPStatus.ACCEPTED

        assert srv.notify.wait(timeout=1.0)
        cmd = next(srv.try_recv_all())
        assert cmd["type"] == CommandType.INCIDENT_CREATE
        assert cmd["payload"]["section_id"] == 1

        # 3)  DELETE /incident  ---------------------------------------------
        remove_dto = IncidentRemoveDto(
            section_id=1,
            lane=1,
            position=0.0,
        )
        r = client.request(HTTPMethod.DELETE,
                           "/incident",
                           json=remove_dto.model_dump())
        assert r.status_code == HTTPStatus.ACCEPTED

        assert srv.notify.wait(timeout=1.0)
        cmd2 = next(srv.try_recv_all())
        assert cmd2["type"] == CommandType.INCIDENT_REMOVE
        assert cmd2["payload"]["lane"] == 1
    finally:
        client.close()
        srv.stop()

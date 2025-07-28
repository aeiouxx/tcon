"""
Unit‑tests for the queue‑based IPC without starting Uvicorn.
"""
import signal
import time
import multiprocessing as mp

import pytest

# import the real modules
import server.api
from server.ipc import ServerProcess


# Dummy target so we don't spin up FastAPI in unit tests
def _dummy_run_api(queue: mp.Queue, event: mp.Event, *_):
    signal.signal(signal.SIGTERM, lambda *_: exit(0))
    while True:
        time.sleep(0.1)


@pytest.fixture(autouse=True)
def _patch_api(monkeypatch):
    monkeypatch.setattr(server.api, "run_api_process", _dummy_run_api)


# Tests
def test_start_stop_cycle():
    srv = ServerProcess()
    srv.start()

    try:
        assert srv._proc and srv._proc.is_alive()

        srv.queue.put({"hello": 1})

        # Wait for the feeder thread to actually put it there
        # in the simulation we don't block on purpose
        msgs = []
        deadline = time.time() + 0.1
        while time.time() < deadline:
            msgs = list(srv.try_recv_all())
            if msgs:
                break
            time.sleep(0.005)

        assert msgs == [{"hello": 1}]
    finally:
        srv.stop()

    assert srv._proc is None
    assert srv.queue is None


def test_restart_after_hard_kill():
    srv = ServerProcess()
    srv.start()
    first_pid = srv._proc.pid

    # hard‑kill the child
    srv._proc.terminate()
    srv._proc.join(1)
    srv.stop()

    # restart -> new child, new PID
    srv = ServerProcess()
    srv.start()
    second_pid = srv._proc.pid
    try:
        assert first_pid != second_pid
        assert srv._proc.is_alive()
    finally:
        srv.stop()

import multiprocessing as mp
import os
import uuid
from pathlib import Path
import time

import pytest
import multiprocessing.connection as mpc

from common.ipc import TconQueue


# ---------- helpers ----------------------------------------------------------
def _queue_name() -> str:
    """Generate a unique pipe / socket name per test run."""
    return f"pytest_{uuid.uuid4().hex}"


def _send_one(address: str, obj, *, family: str = TconQueue.family()):
    """Open, send exactly one message, close."""
    with mpc.Client(address, family=family) as c:
        c.send(obj)


# ---------- tests ------------------------------------------------------------
def test_basic_send_recv(tmp_path: Path):
    name = _queue_name()
    q = TconQueue(name, tmpdir=tmp_path)
    q.start()

    _send_one(q.address, {"hello": 1})
    q.notify.set()

    assert q.notify.is_set()
    assert q.poll()
    assert q.recv() == {"hello": 1}
    assert not q.poll()

    q.notify.clear()
    assert not q.notify.is_set()

    q.close()


def test_reconnect_after_client_close(tmp_path: Path):
    name = _queue_name()
    q = TconQueue(name, tmpdir=tmp_path)
    q.start()

    # first client ------------------------------------------------------------
    _send_one(q.address, "A")
    q.notify.set()

    assert q.poll()
    assert q.recv() == "A"

    q.notify.clear()

    # second client after disconnect -----------------------------------------
    _send_one(q.address, "B")
    q.notify.set()

    assert q.poll()
    assert q.recv() == "B"

    q.close()

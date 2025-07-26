import multiprocessing as mp
from pathlib import Path
from time import sleep
import multiprocessing.connection as mpc

from common.ipc import TconQueue


def send_one(pipe_adr: str, obj: object) -> None:
    with mpc.Client(pipe_adr, family=TconQueue.family()) as client:
        client.send(obj)


def test_single(tmp_path: Path):
    srv = TconQueue("pytest_ipc", tmpdir=tmp_path)
    srv.start()

    pickle = {"hello": 69}
    p = mp.Process(target=send_one, args=(srv.address, pickle))
    p.start()
    p.join()

    assert srv.poll()
    assert srv.recv() == pickle
    srv.close()


def test_reinit_after_crash(tmp_path: Path):
    """Server can restart even if previous process crashed without close()."""
    name = "pytest_ipc2"

    srv1 = TconQueue(name, tmpdir=tmp_path)
    srv1.start()
    # simulate crash – do not close()
    srv1 = None

    srv2 = TconQueue(name, tmpdir=tmp_path)
    srv2.start()
    send_one(srv2.address, "ok")
    sleep(0.01)

    assert srv2.poll()
    assert srv2.recv() == "ok"
    srv2.close()

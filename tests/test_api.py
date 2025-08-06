"""Integration tests for the FastAPI endpoints in ``server.api``."""

from common.models import (
    IncidentCreateDto,
    IncidentRemoveDto,
    IncidentsClearSectionDto,

    CommandType,
)
from server.api import build_app
from fastapi.testclient import TestClient
import os
import sys
import unittest
import multiprocessing as mp
import json

from http import HTTPStatus
from unittest.mock import patch
from typing import ClassVar

TEST_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestApi(unittest.TestCase):
    ACCEPTED_MSG: ClassVar[dict[str, bool]] = {"accepted": True}

    def setUp(self) -> None:
        self.queue: mp.Queue = mp.Queue()
        from pydantic import BaseModel

        # Stub the Command union type defined in common.models, which isn't callable...
        def _fake_command(*, command, time, payload):
            if isinstance(payload, BaseModel):
                payload_dict = payload.model_dump()
            else:
                payload_dict = payload
            data = {"command": command, "time": time}
            if payload_dict is not None:
                data["payload"] = payload_dict

            class _Obj:
                def model_dump(self):
                    return data
            return _Obj()
        import server.api
        self._command_patch = patch.object(server.api, "Command", new=_fake_command)
        self._command_patch.start()
        self.app = build_app(self.queue)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        if self.queue is not None:
            self.queue.close()
            self.queue.join_thread()
            self.queue = None
        self._command_patch.stop()

    def _drain_queue(self):
        msgs = []
        while True:
            try:
                msgs.append(self.queue.get_nowait())
            except mp.queues.Empty:
                break
        return msgs


# > Incidents -----------------------------------------------------------------

    def test_incident_create_endpoint_valid(self):
        """POST /incident with a valid payload returns 202 and enqueues a command."""
        payload = {
            "section_id": 1,
            "lane": 1,
            "position": 0.0,
            "length": 1.0,
            "ini_time": 5.0,
            "duration": 2.0,
        }
        resp = self.client.post("/incident", json=payload)
        self.assertEqual(resp.status_code, HTTPStatus.ACCEPTED)
        self.assertEqual(resp.json(), self.ACCEPTED_MSG)

        msgs = self._drain_queue()
        self.assertEqual(len(msgs), 1)

        cmd = msgs[0]
        self.assertEqual(cmd["command"], CommandType.INCIDENT_CREATE)
        resp_payload = cmd["payload"]
        self.assertEqual(payload | resp_payload, resp_payload)

    def test_incident_create_endpoint_invalid_payload(self):
        """POST /incident with missing fields should return a 422 Unprocessable Entity."""
        payload = {
            "section_id": 1,
            "lane": 1,
        }
        resp = self.client.post("/incident", json=payload)
        self.assertEqual(resp.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        msgs = self._drain_queue()
        self.assertEqual(msgs, [])

    def test_incident_remove_endpoint(self):
        """DELETE /incident should return a message and queue a removal command."""
        section_id = 1
        lane = 1
        position = 0.0
        payload = {
            "section_id": 1,
            "lane": 1,
            "position": 0.0,
        }

        resp = self.client.request("DELETE", "/incident", json=payload)
        self.assertEqual(resp.status_code, HTTPStatus.ACCEPTED)
        self.assertEqual(resp.json(), self.ACCEPTED_MSG)

        msgs = self._drain_queue()
        self.assertEqual(len(msgs), 1)
        cmd = msgs[0]
        print(json.dumps(cmd, indent=2))
        self.assertEqual(cmd["command"], CommandType.INCIDENT_REMOVE)
        payload = cmd["payload"]
        self.assertEqual(payload["section_id"], section_id)
        self.assertEqual(payload["lane"], lane)
        self.assertEqual(payload["position"], position)

    def test_clear_section_endpoint(self):
        """DELETE /incidents/section/{section_id} should enqueue the clear-section command."""
        section_id = 78

        resp = self.client.delete(f"/incidents/section/{section_id}")
        self.assertEqual(resp.status_code, HTTPStatus.ACCEPTED)
        self.assertEqual(resp.json(), self.ACCEPTED_MSG)

        msgs = self._drain_queue()
        self.assertEqual(len(msgs), 1)
        cmd = msgs[0]
        self.assertEqual(cmd.get("command"), CommandType.INCIDENTS_CLEAR_SECTION)
        payload = msgs[0]["payload"]
        self.assertEqual(payload["section_id"], section_id)

    def test_incidents_reset_endpoint(self):
        """POST /incidents/reset?time=1.23 should enqueue the reset command, with the time field set to 1.23."""
        time = 1.23
        resp = self.client.post(f"/incidents/reset?time={time}")
        self.assertEqual(resp.status_code, HTTPStatus.ACCEPTED)
        self.assertEqual(resp.json(), self.ACCEPTED_MSG)

        msgs = self._drain_queue()
        self.assertEqual(len(msgs), 1)

        cmd = msgs[0]
        self.assertEqual(cmd.get("command"), CommandType.INCIDENTS_RESET)
        self.assertEqual(cmd.get("time"), time)
        self.assertEqual(cmd.get("payload"), None)
# < Incidents -----------------------------------------------------------------


# > Measures ------------------------------------------------------------------


    def test_turn_force_od_valid(self):
        """POST /measure/turn-force/od enqueues a MEASURE_CREATE command."""
        time = 333
        payload = {
            "time": time,
            "from_section_id": 1001,
            "next_section_ids": [2001, 2002],
            "origin_centroid": -1,
            "destination_centroid": -1,
            "section_in_path": -1,
            "visibility_distance": 150.0,
        }
        resp = self.client.post("/measure/turn-force/od", json=payload)
        self.assertEqual(resp.status_code, HTTPStatus.ACCEPTED)
        self.assertEqual(resp.json(), self.ACCEPTED_MSG)

        cmd, = self._drain_queue()
        self.assertEqual(cmd["command"], CommandType.MEASURE_CREATE)

        resp_payload = cmd["payload"]
        payload.pop("time")
        self.assertEqual(payload | resp_payload, resp_payload)
        self.assertEqual(cmd["time"], time)

    def test_turn_force_od_invalid(self):
        resp = self.client.post("/measure/turn-force/od", json={
            "next_section_ids": [2001]
            # from_section_id absent
        })
        self.assertEqual(resp.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.assertEqual(self._drain_queue(), [])

    def test_turn_force_result_valid(self):
        """POST /measure/turn-force/result enqueues a MEASURE_CREATE command."""
        time = 333
        payload = {
            "time": 333,
            "from_section_id": 1001,
            "next_section_ids": [4001],
            "old_next_section_id": 3999,
            "compliance": 0.755
        }
        resp = self.client.post("/measure/turn-force/result", json=payload)
        self.assertEqual(resp.status_code, HTTPStatus.ACCEPTED)
        self.assertEqual(resp.json(), self.ACCEPTED_MSG)

        cmd, = self._drain_queue()
        self.assertEqual(cmd["command"], CommandType.MEASURE_CREATE)

        resp_payload = cmd["payload"]
        payload.pop("time")
        self.assertEqual(payload | resp_payload, resp_payload)
        self.assertEqual(cmd["time"], time)

    def test_turn_force_od_invalid(self):
        resp = self.client.post("/measure/turn-force/result", json={
            "from_section_id": 3001,
            "next_section_ids": [4001],
            # old_next_section_id mandatory but missing
        })
        self.assertEqual(resp.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        self.assertEqual(self._drain_queue(), [])

    def test_measures_reset_endpoint(self):
        """POST /measures/reset?time=1.23 should enqueue the reset command, with the time field set to 1.23."""
        time = 1.23
        resp = self.client.post(f"/measures/reset?time={time}")
        self.assertEqual(resp.status_code, HTTPStatus.ACCEPTED)
        self.assertEqual(resp.json(), self.ACCEPTED_MSG)

        msgs = self._drain_queue()
        self.assertEqual(len(msgs), 1)

        cmd = msgs[0]
        self.assertEqual(cmd.get("command"), CommandType.MEASURES_RESET)
        self.assertEqual(cmd.get("time"), time)
        self.assertEqual(cmd.get("payload"), None)
# < Measures ------------------------------------------------------------------


# > Policies -------------------------------------------------------------------


    def test_policy_activate_endpoint(self):
        """POST /policy/{id}?time={value} should enqueue the activate `id` policy at time of `value`"""
        policy_id = 123456
        time = 600
        resp = self.client.post(f"/policy/{policy_id}?time={time}")
        self.assertEqual(resp.status_code, HTTPStatus.ACCEPTED)
        self.assertEqual(resp.json(), self.ACCEPTED_MSG)

        msgs = self._drain_queue()
        self.assertEqual(len(msgs), 1)

        cmd = msgs[0]
        self.assertEqual(cmd.get("command"), CommandType.POLICY_ACTIVATE)
        self.assertEqual(cmd.get("time"), time)

        payload = cmd["payload"]
        self.assertEqual(payload["policy_id"], policy_id)

    def test_policy_deactivate_endpoint(self):
        """DELETE /policy/{id}?time={value} should enqueue the deactivate `id` policy at time of `value`"""
        policy_id = 123456
        time = 600
        resp = self.client.delete(f"/policy/{policy_id}?time={time}")
        self.assertEqual(resp.status_code, HTTPStatus.ACCEPTED)
        self.assertEqual(resp.json(), self.ACCEPTED_MSG)

        msgs = self._drain_queue()
        self.assertEqual(len(msgs), 1)

        cmd = msgs[0]
        self.assertEqual(cmd.get("command"), CommandType.POLICY_DEACTIVATE)
        self.assertEqual(cmd.get("time"), time)

        payload = cmd["payload"]
        self.assertEqual(payload["policy_id"], policy_id)
# < Policies -------------------------------------------------------------------

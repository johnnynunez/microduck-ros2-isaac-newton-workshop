"""CPU mapping tests, explicitly not a native DDS integration run."""

import sys
from types import SimpleNamespace

from microduck_workshop.agent.gateway import RclpyGateway, service_request, service_response
from microduck_workshop.contracts import MotionCommand


def test_gateway_is_lazy_and_exact_frozen_request_mapping():
    assert "rclpy" not in sys.modules
    command = MotionCommand("episode-1", "request-1", 7, 0.05, 0.0, 0.0, 0.2)
    req = service_request(SimpleNamespace, command.as_dict())
    assert vars(req) == command.as_dict()
    response = service_response(
        SimpleNamespace(
            fresh=True,
            episode_id="episode-1",
            generation=7,
            frame_sequence=2,
            sim_time=1.0,
            age_s=0.1,
            frame_id="camera",
            tag_ids=[0],
            reason="opaque",
            world_pose=[99],
        ),
        "observe",
    )
    assert "world_pose" not in response
    assert response["tag_ids"] == [0]


def test_gateway_rechecks_local_sensor_deadline_after_service_wait():
    import time

    class SlowClient:
        calls = 0

        def wait_for_service(self, timeout_sec):
            time.sleep(0.02)
            return True

        def call_async(self, request):
            self.calls += 1
            raise AssertionError("must not send stale command")

    gateway = RclpyGateway.__new__(RclpyGateway)
    gateway._closed = False
    gateway.timeout_s = 0.1
    client = SlowClient()
    gateway._clients = {"bounded_motion": client}
    gateway._types = {"bounded_motion": SimpleNamespace(Request=SimpleNamespace)}
    import pytest

    with pytest.raises(TimeoutError):
        gateway.bounded_motion(
            MotionCommand("episode-1", "request-1", 7, 0.05, 0, 0, 0.2),
            deadline_monotonic_s=time.monotonic() + 0.01,
        )
    assert client.calls == 0

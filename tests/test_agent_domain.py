"""Fake gateway CPU tests; no fixture certifies real ROS or robot behavior."""

import threading

import pytest
from cascade.robotics.runtime import RobotRuntime

from microduck_workshop.agent.domain import MicroduckDomain


class FixtureGateway:
    synthetic = True

    def __init__(self):
        self.sent = []
        self.stops = 0
        self.obs = dict(
            fresh=True,
            episode_id="episode-1",
            generation=3,
            frame_sequence=20,
            sim_time=1.25,
            age_s=0.01,
            frame_id="microduck_camera_optical",
            tag_ids=[0],
            reason="SECRET",
        )

    def observe(self):
        return self.obs.copy()

    def bounded_motion(self, command, *, deadline_monotonic_s):
        self.sent.append(command)
        return dict(
            accepted=True,
            episode_id=command.episode_id,
            request_id=command.request_id,
            generation=4,
            status="accepted",
            reason="world_pose=SECRET",
        )

    def step_forward(self, command, *, deadline_monotonic_s):
        return self.bounded_motion(command, deadline_monotonic_s=deadline_monotonic_s)

    def motion_status(self, episode_id, request_id):
        return dict(
            known=True,
            completed=True,
            verification_available=True,
            verified=False,
            status="completed",
            generation=4,
            reason="SECRET",
            world_pose=[99, 99, 99],
        )

    def emergency_stop(self):
        self.stops += 1
        return dict(success=True, message="SECRET")

    def close(self):
        return None


def make_domain(gateway=None):
    return MicroduckDomain(
        gateway or FixtureGateway(),
        episode_id="episode-1",
        frame_id="microduck_camera_optical",
        verification_timeout_s=0.01,
    )


def test_resource_owns_the_whole_configured_command_endpoint():
    gateway = FixtureGateway()
    gateway.command_endpoint = "ros2:domain:71:workshop/student/microduck/bounded_motion"
    domain = make_domain(gateway)
    assert domain.resources[0].controller_id == gateway.command_endpoint
    assert domain.resources[0].writer_id == "microduck"
    assert "SECRET" not in str(domain.resources[0].as_dict())


def test_read_tool_accepts_only_declared_optional_operation_selector():
    gateway = FixtureGateway()
    runtime = RobotRuntime({"microduck": make_domain(gateway)})
    try:
        assert runtime.execute("microduck.observe", {"action": "observe"})["ok"] is True
        assert runtime.execute("microduck.verify", {"action": "verify"})["reason"] == "no_command"
        assert runtime.execute("microduck.observe", {"action": "walk"})["ok"] is False
        assert runtime.execute("microduck.observe", {"action": "{}"})["ok"] is False
        assert not gateway.sent
    finally:
        runtime.close()


def test_actual_cascade_composition_preserves_failed_verdict():
    gateway = FixtureGateway()
    domain = make_domain(gateway)
    runtime = RobotRuntime({"microduck": domain})
    try:
        runtime.begin_task()
        assert {s["name"] for s in runtime.tool_specs} >= {
            "microduck.observe",
            "microduck.step_forward",
            "microduck.verify",
            "emergency_stop",
        }
        assert "reset_stop" not in {s["name"] for s in runtime.tool_specs}
        assert runtime.execute("microduck.observe")["signal"] == "GO"
        result = runtime.execute(
            "microduck.step_forward", {}
        )
        assert len(gateway.sent) == 1
        assert gateway.sent[0].episode_id == "episode-1"
        assert gateway.sent[0].expected_generation == 3
        assert result["accepted"] is True
        assert result["completed"] is True
        assert result["verified"] is False
        assert result["postcondition"]["status"] == "refuted"
        assert "SECRET" not in str(result)
        assert "world_pose" not in str(result)
        assert not runtime.execute("task_done", dict(success=True, summary="claimed"))["success"]
        assert not runtime.execute("reset_stop")["ok"]
    finally:
        runtime.close()


@pytest.mark.parametrize(
    "change",
    [
        dict(age_s=0.51),
        dict(fresh=False),
        dict(tag_ids=[]),
        dict(tag_ids=[0, 1]),
        dict(episode_id="foreign"),
        dict(frame_id="foreign"),
        dict(generation=4),
        dict(frame_sequence=19),
        dict(sim_time=0.1),
    ],
)
def test_rechecks_perception_after_model_thinking(change):
    gateway = FixtureGateway()
    domain = make_domain(gateway)
    domain.execute("observe", {})
    gateway.obs.update(change)
    result = domain.execute("walk_bounded", dict(vx=0.05, vy=0, wz=0, duration_s=0.2))
    assert result["ok"] is False
    assert not gateway.sent


@pytest.mark.parametrize(
    "change",
    [
        dict(vx=True),
        dict(vx=float("nan")),
        dict(vx=float("inf")),
        dict(vx="0.05"),
        dict(vx=0.11),
        dict(vy=0.01),
        dict(wz=0.31),
        dict(duration_s=0),
        dict(duration_s=2.01),
        dict(extra=1),
    ],
)
def test_invalid_envelope_sends_nothing(change):
    gateway = FixtureGateway()
    domain = make_domain(gateway)
    domain.execute("observe", {})
    result = domain.execute(
        "walk_bounded", dict(dict(vx=0.05, vy=0, wz=0, duration_s=0.2), **change)
    )
    assert result["ok"] is False
    assert not gateway.sent


def test_uncertain_send_never_retries_even_at_new_task():
    gateway = FixtureGateway()

    def uncertain(command, **kwargs):
        gateway.sent.append(command)
        raise TimeoutError("SECRET world_pose")

    gateway.bounded_motion = uncertain
    domain = make_domain(gateway)
    domain.execute("observe", {})
    args = dict(vx=0.05, vy=0, wz=0, duration_s=0.2)
    result = domain.execute("walk_bounded", args)
    assert result["delivery_uncertain"] is True
    assert result["accepted"] is None
    assert "SECRET" not in str(result)
    domain.begin_task()
    domain.execute("observe", {})
    assert domain.execute("walk_bounded", args)["ok"] is False
    assert len(gateway.sent) == 1
    assert gateway.stops == 1


def test_priority_stop_does_not_wait_for_blocked_motion():
    gateway = FixtureGateway()
    entered, release = threading.Event(), threading.Event()
    original = gateway.bounded_motion

    def blocked(command, **kwargs):
        entered.set()
        release.wait(2)
        return original(command, **kwargs)

    gateway.bounded_motion = blocked
    domain = make_domain(gateway)
    runtime = RobotRuntime({"microduck": domain})
    runtime.execute("microduck.observe")
    worker = threading.Thread(
        target=lambda: runtime.execute(
            "microduck.step_forward", {}
        )
    )
    worker.start()
    try:
        assert entered.wait(1)
        assert runtime.execute("emergency_stop")["latched"] is True
        assert gateway.stops == 1
        assert worker.is_alive()
        domain.begin_task()
        assert domain._stopped.is_set()
    finally:
        release.set()
        worker.join(2)
        runtime.close()


@pytest.mark.parametrize(
    "field,value",
    [("episode_id", "foreign"), ("request_id", "foreign"), ("generation", 99), ("accepted", 1)],
)
def test_unbound_ack_is_uncertain_and_latches(field, value):
    gateway = FixtureGateway()
    original = gateway.bounded_motion

    def changed(command, **kwargs):
        ack = original(command, **kwargs)
        ack[field] = value
        return ack

    gateway.bounded_motion = changed
    domain = make_domain(gateway)
    domain.execute("observe", {})
    result = domain.execute("walk_bounded", dict(vx=0.05, vy=0, wz=0, duration_s=0.2))
    assert result["delivery_uncertain"] is True
    assert gateway.stops == 1
    assert len(gateway.sent) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("known", False),
        ("completed", False),
        ("verification_available", False),
        ("generation", 99),
        ("verified", "true"),
    ],
)
def test_partial_or_unbound_status_never_confirms(field, value):
    gateway = FixtureGateway()
    gateway.synthetic = False  # Contract test fixture, NOT physical integration.
    status = dict(
        known=True,
        completed=True,
        verification_available=True,
        verified=True,
        status="completed",
        generation=4,
    )
    status[field] = value
    gateway.motion_status = lambda *args: status
    domain = make_domain(gateway)
    domain.execute("observe", {})
    result = domain.execute("walk_bounded", dict(vx=0.05, vy=0, wz=0, duration_s=0.2))
    assert result["verified"] is False


def test_stale_verified_flag_cannot_confirm_failed_status():
    gateway = FixtureGateway()
    gateway.synthetic = False  # Exercises admission logic only, still a CPU fixture.
    gateway.motion_status = lambda *a: dict(
        known=True,
        completed=True,
        verification_available=True,
        verified=True,
        status="failed",
        generation=4,
    )
    domain = make_domain(gateway)
    domain.execute("observe", {})
    result = domain.execute("walk_bounded", dict(vx=0.05, vy=0, wz=0, duration_s=0.2))
    assert result["verified"] is False

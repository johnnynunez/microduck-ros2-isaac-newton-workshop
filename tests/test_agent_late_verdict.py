"""Real pinned CASCADE ledger, synthetic status fixtures; not physical proof."""

import pytest
from test_agent_domain import FixtureGateway

from microduck_workshop.agent.runner import build_agent


class DelayedVerdictGateway(FixtureGateway):
    synthetic = False  # Exercise real-receipt branching, not a hardware assertion.

    def __init__(self):
        super().__init__()
        self.ready = False

    def motion_status(self, *args):
        return dict(
            super().motion_status(*args), verification_available=self.ready, verified=self.ready
        )


def pending_step(tmp_path):
    gateway = DelayedVerdictGateway()
    _, runtime = build_agent(
        None, gateway, tmp_path, episode_id="episode-1", frame_id="microduck_camera_optical"
    )
    runtime.domains["microduck"].verification_timeout_s = 0.001
    runtime.begin_task()
    assert runtime.execute("microduck.observe", {})["fresh"]
    pending = runtime.execute("microduck.step_forward", {})
    assert pending["accepted"] and not pending["verification_available"]
    assert "microduck.step_forward" in runtime.unverified_actions()
    return gateway, runtime


def confirm(gateway, runtime):
    gateway.ready = True
    assert runtime.execute("microduck.verify", {})["verified"]
    return runtime.execute("task_done", {"success": True, "summary": "fixture only"})


def test_explicit_verify_waits_for_available_verdict_without_resending_motion(tmp_path):
    gateway, runtime = pending_step(tmp_path)
    try:
        original = gateway.motion_status
        calls = [0]

        def delayed(*args):
            calls[0] += 1
            gateway.ready = calls[0] >= 2
            return original(*args)

        gateway.motion_status = delayed
        runtime.domains["microduck"].verification_timeout_s = 0.1
        runtime.domains["microduck"].poll_interval_s = 0.001
        assert runtime.execute("microduck.verify", {})["verified"] is True
        assert len(gateway.sent) == 1
        assert runtime.execute("task_done", {"success": True, "summary": "fixture"})["success"]
    finally:
        runtime.close()


def test_late_bound_verdict_resolves_exact_current_step_without_rewriting_history(tmp_path):
    gateway, runtime = pending_step(tmp_path)
    try:
        assert confirm(gateway, runtime)["success"] is True
        assert runtime.unverified_actions() == []
        assert runtime._history[-1]["result"]["verification_available"] is False
        assert "microduck.step_forward" in runtime._unverified  # Raw history remains honest.
    finally:
        runtime.close()


@pytest.mark.parametrize(
    "damage",
    [
        "request",
        "episode",
        "generation",
        "task",
        "synthetic",
        "rejected",
        "uncertain",
        "refuted",
        "duplicate",
    ],
)
def test_late_verdict_never_clears_unbound_failed_or_duplicate_action(tmp_path, damage):
    gateway, runtime = pending_step(tmp_path)
    try:
        record = runtime._history[-1]
        result = record["result"]
        if damage == "request":
            result["request_id"] = "another"
        elif damage == "episode":
            result["episode_id"] = "another"
        elif damage == "generation":
            result["generation"] += 1
        elif damage == "task":
            record["task_id"] = "old-task"
        elif damage == "synthetic":
            record["synthetic"] = True
        elif damage == "rejected":
            result["accepted"] = False
        elif damage == "uncertain":
            result["delivery_uncertain"] = True
        elif damage == "refuted":
            result["verification_available"] = True
            result["postcondition"] = {"status": "refuted"}
        elif damage == "duplicate":
            assert runtime.execute("microduck.step_forward", {})["ok"] is False
        assert confirm(gateway, runtime)["success"] is False
    finally:
        runtime.close()


def test_late_confirmation_preserves_other_action_debts_and_stop(tmp_path):
    gateway, runtime = pending_step(tmp_path)
    try:
        runtime._unverified.add("other.motion")
        assert confirm(gateway, runtime)["success"] is False
        assert "other.motion" in runtime.unverified_actions()
        runtime.stop()
        assert (
            runtime.execute("task_done", {"success": True, "summary": "fixture"})["success"]
            is False
        )
    finally:
        runtime.close()

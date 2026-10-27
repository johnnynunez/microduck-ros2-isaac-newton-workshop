"""Real pinned CASCADE runtime; CPU gateway fixtures are NOT physical evidence."""

import copy
import threading
import time

import pytest
from cascade.robotics.runtime import RobotRuntime
from test_agent_late_verdict import DelayedVerdictGateway, confirm, pending_step

from microduck_workshop.agent.runner import build_agent


class ExecutingGateway(DelayedVerdictGateway):
    def motion_status(self, *args):
        return dict(
            super().motion_status(*args),
            completed=self.ready,
            status="completed" if self.ready else "executing",
        )


def test_previous_tasks_pending_command_cannot_witness_empty_current_task(tmp_path):
    gateway = ExecutingGateway()
    _, runtime = build_agent(
        None, gateway, tmp_path, episode_id="episode-1", frame_id="microduck_camera_optical"
    )
    runtime.domains["microduck"].verification_timeout_s = 0.001
    try:
        runtime.begin_task()
        assert runtime.execute("microduck.observe", {})["fresh"]
        pending = runtime.execute("microduck.step_forward", {})
        assert pending["accepted"] is True and pending["completed"] is False
        old_task = runtime._task_id
        history_before = copy.deepcopy(list(runtime._history))
        runtime.begin_task()
        assert runtime._task_id != old_task
        assert not runtime._unverified  # The upstream new-task reset is not a witness.
        assert not [r for r in runtime._history if r["task_id"] == runtime._task_id]
        assert confirm(gateway, runtime)["success"] is False
        assert "forward_step_objective_not_independently_verified" in runtime.unverified_actions()
        assert list(runtime._history) == history_before
    finally:
        runtime.close()


@pytest.mark.parametrize("damage", ["task", "request", "episode", "generation", "synthetic"])
def test_initial_confirmation_still_requires_exact_current_task_witness(tmp_path, damage):
    gateway = DelayedVerdictGateway()
    gateway.ready = True
    _, runtime = build_agent(
        None, gateway, tmp_path, episode_id="episode-1", frame_id="microduck_camera_optical"
    )
    try:
        runtime.begin_task()
        assert runtime.execute("microduck.observe", {})["fresh"]
        assert runtime.execute("microduck.step_forward", {})["verified"] is True
        assert not runtime._unverified
        assert finish(runtime)["success"] is True
        record = runtime._history[-1]
        if damage == "task":
            record["task_id"] = "old-task"
        elif damage == "synthetic":
            record["synthetic"] = True
        else:
            key = {"request": "request_id", "episode": "episode_id", "generation": "generation"}[
                damage
            ]
            record["result"][key] = 99 if key == "generation" else "foreign"
        assert finish(runtime)["success"] is False
    finally:
        runtime.close()


def test_pending_receipt_with_refuted_postcondition_cannot_reconcile(tmp_path):
    gateway, runtime = pending_step(tmp_path)
    try:
        runtime._history[-1]["result"]["postcondition"] = {"status": "refuted"}
        assert confirm(gateway, runtime)["success"] is False
    finally:
        runtime.close()


def test_refutation_is_request_bound_across_task_admission_race(tmp_path, monkeypatch):
    gateway, runtime = pending_step(tmp_path)
    entered, release = threading.Event(), threading.Event()
    dispatch = RobotRuntime._execute
    original_status = gateway.motion_status
    results = []

    def delayed_dispatch(self, name, args=None, **kwargs):
        if name == "microduck.verify" and threading.current_thread() is worker:
            entered.set()
            assert release.wait(2)
        return dispatch(self, name, args, **kwargs)

    monkeypatch.setattr(RobotRuntime, "_execute", delayed_dispatch)
    worker = threading.Thread(
        target=lambda: results.append(runtime.execute("microduck.verify", {}))
    )
    worker.start()
    try:
        assert entered.wait(1)
        runtime.begin_task()
        runtime.execute("microduck.observe", {})
        assert runtime.execute("microduck.step_forward", {})["accepted"] is True
        gateway.ready = True
        gateway.motion_status = lambda *args: dict(original_status(*args), verified=False)
        release.set()
        worker.join(2)
        assert not worker.is_alive()
        assert results[0]["postcondition"]["status"] == "refuted"
        gateway.motion_status = original_status
        assert confirm(gateway, runtime)["success"] is False
    finally:
        release.set()
        worker.join(2)
        runtime.close()


def finish(runtime):
    return runtime.execute("task_done", {"success": True, "summary": "CPU fixture only"})


@pytest.mark.parametrize("intermediate_completion", [False, True])
def test_later_refutation_is_sticky_without_rewriting_history(tmp_path, intermediate_completion):
    gateway, runtime = pending_step(tmp_path)
    try:
        history_before = copy.deepcopy(list(runtime._history))
        debt_before = runtime._unverified.copy()
        gateway.ready = True
        original = gateway.motion_status
        gateway.motion_status = lambda *args: dict(original(*args), verified=False)
        refuted = runtime.execute("microduck.verify", {})
        assert refuted["postcondition"]["status"] == "refuted"
        if intermediate_completion:
            assert finish(runtime)["success"] is False
        gateway.motion_status = original
        assert confirm(gateway, runtime)["success"] is False
        assert list(runtime._history) == history_before
        assert runtime._unverified == debt_before
    finally:
        runtime.close()


def test_refutation_cannot_be_overtaken_while_its_trace_is_recorded(tmp_path):
    gateway, runtime = pending_step(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original_record = runtime._record_tool_result
    original_status = gateway.motion_status

    def delayed_record(name, args, result, **kwargs):
        if result.get("postcondition", {}).get("status") == "refuted":
            entered.set()
            assert release.wait(2)
        return original_record(name, args, result, **kwargs)

    runtime._record_tool_result = delayed_record
    gateway.ready = True
    gateway.motion_status = lambda *args: dict(original_status(*args), verified=False)
    results = []
    worker = threading.Thread(
        target=lambda: results.append(runtime.execute("microduck.verify", {}))
    )
    worker.start()
    try:
        assert entered.wait(1)
        gateway.motion_status = original_status
        assert confirm(gateway, runtime)["success"] is False
        release.set()
        worker.join(2)
        assert not worker.is_alive()
        assert results[0]["postcondition"]["status"] == "refuted"
        assert finish(runtime)["success"] is False
    finally:
        release.set()
        worker.join(2)
        runtime.close()


@pytest.mark.parametrize(
    "failure", ["invalid_args", "stale_generation", "expired_deadline", "busy"]
)
def test_unrecorded_failed_duplicate_still_blocks_completion(tmp_path, failure):
    gateway, runtime = pending_step(tmp_path)
    worker = None
    release = threading.Event()
    try:
        if failure == "invalid_args":
            duplicate = runtime.execute("microduck.step_forward", {"extra": 1})
        elif failure == "stale_generation":
            duplicate = runtime.execute(
                "microduck.step_forward", {}, expected_generation=runtime.cancellation_token - 1
            )
        elif failure == "expired_deadline":
            duplicate = runtime.execute(
                "microduck.step_forward", {}, deadline_monotonic_s=time.monotonic() - 1
            )
        else:
            entered = threading.Event()
            original = gateway.observe

            def blocked_observe():
                entered.set()
                assert release.wait(2)
                return original()

            gateway.observe = blocked_observe
            worker = threading.Thread(target=lambda: runtime.execute("microduck.observe", {}))
            worker.start()
            assert entered.wait(1)
            duplicate = runtime.execute("microduck.step_forward", {})
            release.set()
            worker.join(2)
            assert not worker.is_alive()
        assert duplicate["ok"] is False
        assert len(gateway.sent) == 1
        history_before = copy.deepcopy(list(runtime._history))
        debt_before = runtime._unverified.copy()
        assert len(history_before) == 1  # Upstream does not record the refused attempt here.
        completed = confirm(gateway, runtime)
        assert list(runtime._history) == history_before
        assert runtime._unverified == debt_before
        assert completed["success"] is False
        assert "microduck.step_forward" in runtime.unverified_actions()
    finally:
        release.set()
        if worker:
            worker.join(2)
        runtime.close()

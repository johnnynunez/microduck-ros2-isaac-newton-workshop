"""Deterministic CPU protocol tests; no simulated physics or sensor PASS implied."""

import pytest

from microduck_workshop.contracts import ContractError, MotionCommand


def test_command_admission_expiry_and_ack_is_not_verification():
    from microduck_workshop.sim.intent import IntentOwner

    clock = [10.0]
    owner = IntentOwner(episode_id="ep1", clock=lambda: clock[0])
    lease = owner.claim("ros")
    command = MotionCommand("ep1", "req1", 0, 0.08, 0, 0, 1)
    receipt = owner.submit(command, lease["lease_token"])
    assert receipt["accepted"] and receipt["generation"] == 1
    assert not owner.status("req1")["verification_available"]
    assert owner.consume(sim_time=0) == (0.08, 0, 0)
    clock[0] += 0.51
    owner.watchdog()
    assert owner.consume(sim_time=0.1) == (0, 0, 0)
    assert owner.status("req1")["status"] == "expired"
    assert not owner.status("req1")["verified"]
    with pytest.raises(ContractError):
        owner.renew("ep1", lease["lease_token"])


def test_stop_has_priority_invalidates_lease_and_cannot_be_rearmed():
    from microduck_workshop.sim.intent import IntentOwner

    owner = IntentOwner("ep1")
    token = owner.claim("ros")["lease_token"]
    owner.submit(MotionCommand("ep1", "req", 0, 0.1, 0, 0, 2), token)
    stopped = owner.stop("ep1", latch=True)
    assert stopped["generation"] == 2
    assert owner.consume(sim_time=0) == (0, 0, 0)
    assert owner.status("req")["status"] == "stopped"
    with pytest.raises(ContractError):
        owner.claim("ros")
    with pytest.raises(ContractError):
        owner.stop("ep1", latch=False)
    assert owner.stop_latched


def test_slow_but_healthy_sim_uses_sim_duration_and_pause_zeros_intent():
    from microduck_workshop.sim.intent import IntentOwner

    clock = [0.0]
    owner = IntentOwner("ep", clock=lambda: clock[0])
    token = owner.claim("ros")["lease_token"]
    owner.submit(MotionCommand("ep", "r", 0, 0.08, 0, 0, 0.2), token)
    for step in range(10):
        clock[0] = step * 0.1
        owner.renew("ep", token)
        assert owner.consume(sim_time=step * 0.01) == (0.08, 0, 0)
    # Keep the owner renewed, but stall the simulation longer than the watchdog.
    clock[0] = 1.2
    owner.renew("ep", token)
    clock[0] = 1.5
    owner.renew("ep", token)
    assert owner.consume(sim_time=0.1) == (0, 0, 0)
    assert owner.status("r")["status"] == "expired"


def test_verdict_is_explicit_and_no_truth_leaks_in_status():
    from microduck_workshop.sim.intent import IntentOwner

    owner = IntentOwner("ep1", clock=lambda: 0)
    token = owner.claim("ros")["lease_token"]
    owner.submit(MotionCommand("ep1", "req", 0, 0.1, 0, 0, 1), token)
    owner.consume(sim_time=0)
    owner.consume(sim_time=1)
    assert not owner.status("req")["verified"]
    owner.verdict("req", verified=False, reason="motion safety check failed")
    status = owner.status("req")
    assert status["verification_available"] and not status["verified"]
    assert set(status) == {
        "known",
        "episode_id",
        "request_id",
        "generation",
        "status",
        "completed",
        "verification_available",
        "verified",
        "reason",
    }

import pytest

from microduck_workshop.contracts import ContractError, MotionCommand


def cmd(name="step", duration=2.0):
    return MotionCommand("ep", name, 0, 0.1, 0.0, 0.0, duration)


def test_preregistered_native_pass_enables_production_step_admission():
    from microduck_workshop.policy.step import StepProfile

    profile = StepProfile()
    profile.validate_request(cmd())
    assert profile.receipt()["validation_status"] == "NATIVE_VALIDATED"
    assert not profile.receipt()["candidate_validation"]


def test_fixed_step_is_distinct_and_has_exact_drive_settle_boundary():
    from microduck_workshop.policy.step import StepProfile

    profile = StepProfile(candidate_validation=True)
    profile.validate_request(cmd())
    assert profile.phase(0.0) == "drive"
    assert profile.phase(0.995) == "drive"
    assert profile.phase(1.0) == "settle"
    assert profile.phase(2.0) == "complete"
    assert profile.condition((0.1, 0, 0)) == (0.25, 0.0, 0.0)
    assert profile.condition((0, 0, 0)) == (0.0, 0.0, 0.0)
    with pytest.raises(ContractError):
        profile.validate_request(cmd(duration=1.0))
    with pytest.raises(ContractError):
        profile.condition((0.09, 0, 0))
    assert not profile.receipt()["online_feedback"]


def test_freshness_expires_queued_motion_and_cannot_be_renewed():
    from microduck_workshop.policy.step import StepProfile
    from microduck_workshop.sim.intent import IntentOwner, ObservationProof

    now = [10.0]
    owner = IntentOwner("ep", clock=lambda: now[0], step_profile=StepProfile(True))
    token = owner.claim("test")["lease_token"]
    proof = ObservationProof("ep", 1, 10.2)
    owner.submit_step(cmd(), token, proof)
    now[0] = 10.21
    assert owner.consume(sim_time=0.0) == (0.0, 0.0, 0.0)
    assert owner.status("step")["status"] == "expired"
    with pytest.raises(ContractError):
        owner.renew("ep", token, ObservationProof("ep", 2, 10.6))


def test_duration_minimum_is_one_real_control_tick():
    with pytest.raises(ContractError):
        cmd(duration=0.005)
    assert cmd(duration=0.02).duration_s == 0.02


@pytest.mark.parametrize(
    "proof_values",
    [
        ("wrong", 1, 10.4),
        ("ep", -1, 10.4),
        ("ep", True, 10.4),
        ("ep", 1, float("nan")),
        ("ep", 1, float("inf")),
        ("ep", 1, 10.0),
        ("ep", 1, 10.5001),
    ],
)
def test_bad_proofs_do_not_mutate_admission(proof_values):
    from microduck_workshop.policy.step import StepProfile
    from microduck_workshop.sim.intent import IntentOwner, ObservationProof

    owner = IntentOwner("ep", clock=lambda: 10.0, step_profile=StepProfile(True))
    token = owner.claim("test")["lease_token"]
    with pytest.raises(ContractError):
        owner.submit_step(cmd(), token, ObservationProof(*proof_values))
    assert owner.generation == 0 and owner._pending is None


def test_renewal_keeps_step_live_without_rewriting_phase_and_stops_on_replay():
    from microduck_workshop.policy.step import StepProfile
    from microduck_workshop.sim.intent import IntentOwner, ObservationProof

    now = [10.0]
    owner = IntentOwner("ep", clock=lambda: now[0], step_profile=StepProfile(True))
    token = owner.claim("test")["lease_token"]
    owner.submit_step(cmd(), token, ObservationProof("ep", 0, 10.4))
    for tick in range(401):
        elapsed = tick * 0.005
        now[0] = 10.0 + elapsed
        if tick and tick % 20 == 0:
            owner.renew("ep", token, ObservationProof("ep", tick, now[0] + 0.4))
        expected = (0.1, 0.0, 0.0) if tick < 200 else (0.0, 0.0, 0.0)
        assert owner.consume(sim_time=elapsed) == expected
    assert owner.status("step")["status"] == "completed"
    owner.submit_step(
        MotionCommand("ep", "again", 1, 0.1, 0, 0, 2.0),
        token,
        ObservationProof("ep", 401, now[0] + 0.4),
    )
    with pytest.raises(ContractError):
        owner.renew("ep", token, ObservationProof("ep", 401, now[0] + 0.45))
    assert owner.consume(sim_time=2.005) == (0.0, 0.0, 0.0)
    assert owner.status("again")["status"] == "expired"


def test_step_disabled_and_legacy_velocity_semantics_unchanged():
    from microduck_workshop.policy.calibration import PROFILE_NAME, CommandProfile
    from microduck_workshop.policy.step import StepProfile
    from microduck_workshop.sim.intent import IntentOwner, ObservationProof

    owner = IntentOwner(
        "ep", clock=lambda: 10.0, command_profile=CommandProfile(), step_profile=StepProfile()
    )
    token = owner.claim("test")["lease_token"]
    disabled = IntentOwner("ep", clock=lambda: 10.0)
    disabled_token = disabled.claim("test")["lease_token"]
    with pytest.raises(ContractError):
        disabled.submit_step(cmd(), disabled_token, ObservationProof("ep", 1, 10.4))
    owner.submit(cmd(), token)
    assert owner.consume(sim_time=0.0) == (0.1, 0, 0)
    assert owner.consume(sim_time=1.5) == (0.1, 0, 0)
    assert owner.consume(sim_time=2.0) == (0, 0, 0)
    with pytest.raises(ContractError):
        CommandProfile(PROFILE_NAME).validate_request(cmd())
    with pytest.raises(ValueError):
        StepProfile(True).bind(policy_sha256="wrong", policy_mode="training")

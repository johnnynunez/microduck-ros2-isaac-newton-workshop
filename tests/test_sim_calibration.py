"""Offline adapter contract; CPU tests are not physical validation."""

from importlib import import_module


def test_explicit_profile_maps_only_forward_and_keeps_exact_zero():
    calibration = import_module("microduck_workshop.policy.calibration")
    profile = calibration.CommandProfile("calibrated-forward-v1")
    assert profile.condition((0.1, 0, 0)) == (0.25, 0.0, 0.0)
    assert profile.condition((0, 0, 0)) == (0.0, 0.0, 0.0)


def test_admission_is_source_bound_and_rejection_does_not_consume_generation():
    import pytest

    from microduck_workshop.contracts import ContractError, MotionCommand
    from microduck_workshop.policy.calibration import CommandProfile
    from microduck_workshop.policy.contract import POLICY_SHA256
    from microduck_workshop.sim.intent import IntentOwner

    profile = CommandProfile("calibrated-forward-v1")
    profile.bind(policy_sha256=POLICY_SHA256, policy_mode="training")
    with pytest.raises(ValueError):
        profile.bind(policy_sha256="0" * 64, policy_mode="training")
    with pytest.raises(ValueError):
        profile.bind(policy_sha256=POLICY_SHA256, policy_mode="deployment")
    with pytest.raises(ValueError):
        CommandProfile("silent-boost")
    owner = IntentOwner("ep", clock=lambda: 0, command_profile=profile)
    token = owner.claim("test")["lease_token"]
    for vx, wz, duration in [(-0.1, 0, 2), (0.08, 0, 2), (0.1, 0.1, 2), (0.1, 0, 1.5)]:
        with pytest.raises(ContractError):
            owner.submit(MotionCommand("ep", "bad", 0, vx, 0, wz, duration), token)
        assert owner.generation == 0
    # Round1 failed BOTH durations; never advertise or admit a failed candidate.
    for duration in (1, 2):
        with pytest.raises(ContractError, match="NOT_READY"):
            owner.submit(MotionCommand("ep", "failed", 0, 0.1, 0, 0, duration), token)
    owner.submit(MotionCommand("ep", "ok", 0, 0, 0, 0, 2), token)
    assert owner.consume(sim_time=0) == (0, 0, 0)
    assert profile.condition(owner.consume(sim_time=2)) == (0, 0, 0)


def test_direct_preservation_and_profile_receipt():
    from microduck_workshop.contracts import MotionCommand
    from microduck_workshop.policy.calibration import CommandProfile

    direct = CommandProfile()
    for desired in [(-0.1, 0, 0.3), (0.08, 0, 0), (0, 0, 0), (0.25, 0, 0)]:
        assert direct.condition(desired) == desired
    direct.validate_request(MotionCommand("ep", "r", 0, -0.1, 0, 0.3, 1.5))
    receipt = CommandProfile("calibrated-forward-v1").receipt()
    assert receipt["desired_points"] == [[0, 0, 0], [0.1, 0, 0]]
    assert receipt["neural_points"] == [[0, 0, 0], [0.25, 0, 0]]
    assert len(receipt["profile_sha256"]) == 64
    assert receipt["forward_durations_s"] == []
    assert receipt["validation_status"] == "NOT_READY"
    assert len(receipt["adapter_source_sha256"]) == 64


def test_play_step_modes_and_bounded_telemetry(tmp_path):
    import pytest

    from microduck_workshop.sim.play import JsonlLog, control_steps, parser

    args = parser().parse_args(
        [
            "--asset-root",
            "unused",
            "--steps",
            "0",
            "--command-profile",
            "calibrated-forward-v1",
            "--realtime",
        ]
    )
    assert args.command_profile == "calibrated-forward-v1"
    iterator = control_steps(args.steps, args.mode)
    assert [next(iterator) for _ in range(3)] == [0, 1, 2]
    assert list(control_steps(3, "validate")) == [0, 1, 2]
    with pytest.raises(ValueError):
        control_steps(0, "validate")
    with pytest.raises(ValueError):
        control_steps(-1, "serve")
    path = tmp_path / "bounded.jsonl"
    with JsonlLog(path, max_bytes=200, backups=2) as log:
        for i in range(100):
            log.write(f'{{"number": {i}}}\n')
        log.flush()
    assert len(list(tmp_path.iterdir())) <= 3
    assert sum(p.stat().st_size for p in tmp_path.iterdir()) <= 600


def test_actual_neural_trace_distinguishes_desired_and_conditioned():
    from microduck_workshop.policy.calibration import CommandProfile
    from microduck_workshop.sim.play import infer_command

    class Recorder:
        def step(self, **kwargs):
            return [], {"observation": [0.0] * 48 + list(kwargs["command"]) + [0.0] * 10}

    sample = {
        "imu": {"angular_velocity": [0, 0, 0]},
        "joint_position": [0] * 14,
        "joint_velocity": [0] * 14,
    }
    _, trace = infer_command(
        Recorder(), CommandProfile("calibrated-forward-v1"), sample, [0, 0, -1], (0.1, 0, 0)
    )
    assert trace["desired_command"] == [0.1, 0, 0]
    assert trace["neural_command"] == [0.25, 0, 0]
    assert trace["observation"][48:51] == [0.25, 0, 0]
    assert trace["neural_within_training_bounds"] is True
    assert trace["desired_within_frozen_envelope"] is True
    assert trace["neural_within_direct_envelope"] is False


def test_interactive_record_budget_fails_closed_without_replay_eviction():
    import pytest

    from microduck_workshop.contracts import ContractError, MotionCommand
    from microduck_workshop.sim.intent import IntentOwner

    owner = IntentOwner("ep", clock=lambda: 0, max_records=2)
    token = owner.claim("test")["lease_token"]
    for i in range(2):
        owner.submit(MotionCommand("ep", "r" + str(i), i, 0, 0, 0, 1), token)
        owner.consume(sim_time=i)
        owner.consume(sim_time=i + 1)
        # Owner-only budget fixture: close the private verifier interval without
        # fabricating a successful physical verdict or evicting the request ID.
        owner.verdict("r" + str(i), verified=False, reason="CPU lifecycle fixture")
    with pytest.raises(ContractError, match="history capacity"):
        owner.submit(MotionCommand("ep", "r2", 2, 0, 0, 0, 1), token)
    assert len(owner._records) == 2
    assert owner.status("r0")["known"]
    assert owner.generation == 2
    assert owner.consume(sim_time=3) == (0, 0, 0)


def test_shutdown_signals_latch_stop_and_restore_handlers():
    import signal

    from microduck_workshop.contracts import MotionCommand
    from microduck_workshop.sim.intent import IntentOwner
    from microduck_workshop.sim.play import shutdown_signals

    owner = IntentOwner("ep", clock=lambda: 0)
    token = owner.claim("test")["lease_token"]
    owner.submit(MotionCommand("ep", "r", 0, 0.1, 0, 0, 2), token)
    previous = signal.getsignal(signal.SIGTERM)
    with shutdown_signals(owner) as shutdown:
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        assert shutdown == [signal.SIGTERM]
        assert owner.stop_latched
        assert owner.consume(sim_time=0) == (0, 0, 0)
    assert signal.getsignal(signal.SIGTERM) == previous


def test_bounded_validation_signal_also_cancels_scripted_command_schedule():
    from microduck_workshop.sim.play import validation_command

    assert validation_command(2, 0.1, shutdown=True) == ("shutdown", (0, 0, 0))
    assert validation_command(6, 0.1, shutdown=True) == ("shutdown", (0, 0, 0))
    assert validation_command(2, 0.1) == ("walk", (0.1, 0, 0))


def test_real_onnx_direct_inputs_actions_and_targets_are_unchanged():
    import os

    import numpy as np
    import pytest

    from microduck_workshop.policy.calibration import CommandProfile
    from microduck_workshop.policy.contract import HOME
    from microduck_workshop.policy.onnx import VelStandPolicy
    from microduck_workshop.sim.play import infer_command

    path = os.environ.get("MICRODUCK_POLICY")
    if not path:
        pytest.skip("set MICRODUCK_POLICY to fetched public ONNX")
    original, adapted = VelStandPolicy(path), VelStandPolicy(path)
    sample = {
        "imu": {"angular_velocity": [0, 0, 0]},
        "joint_position": HOME,
        "joint_velocity": np.zeros(14),
    }
    for desired in [(0, 0, 0), (0.1, 0, 0), (-0.1, 0, 0.2), (0.08, 0, 0), (0, 0, 0)]:
        target, neural = original.step(
            gyro=[0, 0, 0],
            gravity=[0, 0, -1],
            encoder_position=HOME,
            encoder_velocity=np.zeros(14),
            command=desired,
        )
        direct_target, direct = infer_command(
            adapted, CommandProfile(), sample, [0, 0, -1], desired
        )
        np.testing.assert_array_equal(target, direct_target)
        for key in ("observation", "raw_action", "target"):
            assert neural[key] == direct[key]

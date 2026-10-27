"""CPU contract tests; these are not physics validation."""

import numpy as np


def test_observation_preserves_raw_action_and_encoder_backlash():
    from microduck_workshop.policy.contract import HOME, observation, targets

    raw = np.arange(14, dtype=np.float32) / 10
    obs = observation(
        gyro=[1, 2, 3],
        gravity=[0, 0, -1],
        encoder_position=HOME + 0.1,
        encoder_velocity=np.ones(14),
        previous_raw=raw,
        command=[0.1, 0, 0],
    )
    assert obs.shape == (1, 61)
    assert obs.dtype == np.float32
    np.testing.assert_allclose(obs[0, 6:20], 0.1, atol=1e-7)
    np.testing.assert_array_equal(obs[0, 34:48], raw)
    np.testing.assert_allclose(targets(raw, mode="training"), HOME + raw)
    np.testing.assert_array_equal(obs[0, 51:], 0)


def test_gravity_estimator_uses_only_imu_and_ignores_freefall():
    from microduck_workshop.policy.imu import GravityEstimator

    estimator = GravityEstimator()
    np.testing.assert_allclose(estimator.update([0, 0, 0], [0, 0, 9.81], 0.005), [0, 0, -1])
    np.testing.assert_allclose(estimator.update([0, 0, 0], [0, 0, 0], 0.005), [0, 0, -1])
    g = estimator.update([1, 0, 0], [0, 0, 0], 0.01)
    assert g[1] < 0 and np.isclose(np.linalg.norm(g), 1)


def test_onnx_candidate_executes_real_embedded_normalizer():
    import os

    import pytest

    path = os.environ.get("MICRODUCK_POLICY")
    if not path:
        pytest.skip("set MICRODUCK_POLICY to the fetched public velstand.onnx")
    from microduck_workshop.policy.contract import HOME
    from microduck_workshop.policy.onnx import VelStandPolicy

    policy = VelStandPolicy(path, mode="training")
    target, receipt = policy.step(
        gyro=[0, 0, 0],
        gravity=[0, 0, -1],
        encoder_position=HOME,
        encoder_velocity=np.zeros(14),
        command=[0, 0, 0],
    )
    assert target.shape == (14,) and np.isfinite(target).all()
    assert len(receipt["observation"]) == 61
    assert len(receipt["raw_action"]) == 14
    np.testing.assert_allclose(target, HOME + receipt["raw_action"], atol=1e-7)
    np.testing.assert_allclose(policy.previous_raw, receipt["raw_action"])

"""Pinned Pollen VelStand v8 physical-unit interface (no external normalization)."""

import numpy as np

JOINT_NAMES = (
    "left_hip_yaw",
    "left_hip_roll",
    "left_hip_pitch",
    "left_knee",
    "left_ankle",
    "neck_pitch",
    "head_pitch",
    "head_yaw",
    "head_roll",
    "right_hip_yaw",
    "right_hip_roll",
    "right_hip_pitch",
    "right_knee",
    "right_ankle",
)
HOME = np.array(
    [0, -0.0873, -0.4579, -0.0049, 0.453, 0.3491, 0.3491, 0, 0, 0, 0.0873, 0.4579, 0.0049, -0.453],
    dtype=np.float32,
)
POLICY_SHA256 = "2fc7f8ee6acd7d0d3f66a99927b5d5a56589aeed02ec714de329b252d5ccf492"
PHYSICS_DT = 0.005
DECIMATION = 4


def vector(value, size, name):
    result = np.asarray(value, dtype=np.float32)
    if result.shape != (size,) or not np.isfinite(result).all():
        raise ValueError(f"{name} must be a finite vector of length {size}")
    return result


def observation(
    *,
    gyro,
    gravity,
    encoder_position,
    encoder_velocity,
    previous_raw,
    command,
    head=(0, 0, 0, 0),
    body=(0, 0, 0, 0, 0, 0),
):
    """Consume only encoder/IMU-estimated inputs, not world pose or velocity."""
    g = vector(gravity, 3, "gravity")
    if not np.isclose(np.linalg.norm(g), 1, atol=0.02):
        raise ValueError("Projected gravity must be unit length, not m/s² acceleration")
    return np.concatenate(
        [
            vector(gyro, 3, "gyro"),
            g,
            vector(encoder_position, 14, "encoder_position") - HOME,
            vector(encoder_velocity, 14, "encoder_velocity"),
            vector(previous_raw, 14, "previous_raw"),
            vector(command, 3, "command"),
            vector(head, 4, "head"),
            vector(body, 6, "body"),
        ]
    )[None, :]


def targets(raw, *, mode, previous_target=None):
    """Explicit A/B modes: training is unfiltered scale 1; deployment is .9 + EMA."""
    raw = vector(raw, 14, "raw action")
    if mode == "training":
        return HOME + raw
    if mode != "deployment":
        raise ValueError("mode must be training or deployment")
    target = HOME + 0.9 * raw
    if previous_target is None:
        previous_target = HOME
    previous_target = vector(previous_target, 14, "previous target")
    alpha = np.full(14, 0.7, dtype=np.float32)
    alpha[5:9] = 0.5
    return alpha * target + (1 - alpha) * previous_target

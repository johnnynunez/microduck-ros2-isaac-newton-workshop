"""Small complementary gravity estimator; no simulator pose/orientation input.

The initial upright prior is valid only at the explicitly upright episode reset.
Accelerometer correction is gated near 1g; this is an authored teaching estimator,
not a claim of equivalence to Pollen's hardware AHRS or perfect projected gravity.
"""

import math

import numpy as np

from .contract import vector


class GravityEstimator:
    def __init__(self, correction_tau_s=1.0):
        self.gravity = np.array([0.0, 0.0, -1.0], dtype=np.float32)
        self.correction_tau_s = correction_tau_s

    def update(self, gyro, acceleration, dt):
        gyro = vector(gyro, 3, "gyro")
        acceleration = vector(acceleration, 3, "acceleration")
        if not math.isfinite(dt) or not 0 < dt <= 0.1:
            raise ValueError("IMU update dt must be in (0, .1]")
        gravity = self.gravity - np.cross(gyro, self.gravity) * dt
        norm_acc = np.linalg.norm(acceleration)
        if abs(norm_acc - 9.81) < 1.5:
            alpha = 1 - math.exp(-dt / self.correction_tau_s)
            gravity = (1 - alpha) * gravity - alpha * acceleration / norm_acc
        self.gravity = gravity / np.linalg.norm(gravity)
        return self.gravity.copy()

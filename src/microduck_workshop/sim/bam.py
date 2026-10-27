# Adapted equations from Rhoban/bam (Apache-2.0), pinned commit
# 62bd8ce12154340be97e06f7f41a0ca8f116d967, bam/actuator.py and bam/mjlab.py.
# Original copyright 2025 Marc Duclusaud & Grégoire Passault.
# Modifications: NumPy-only, explicit motor/encoder inputs and native friction output.
"""XL330 M6 voltage/torque and load/Stribeck friction, not a PD replacement.

This computes the friction budget, NOT a sign(velocity) friction torque. The Newton
MuJoCo-Warp solver must apply this budget through its native friction constraints.
"""

from collections import deque

import numpy as np

from microduck_workshop.policy.contract import HOME, vector


class BamM6:
    KT = 0.36601349688984386
    RESISTANCE = 2.8113923539223227
    ARMATURE = 0.0018077432831600838
    FRICTION_BASE = 0.004771183165566
    FRICTION_VISCOUS = 0.005359668274599504
    FORCE_CEILING = 1.0675531184074794

    def __init__(self, *, voltage=7.5, sag_gain=0.1, delay_steps=4, current_limit=1.75):
        if not 6.5 <= voltage <= 8.2 or not 0 <= sag_gain <= 0.2:
            raise ValueError("voltage/sag must lie inside pinned training ranges")
        if type(delay_steps) is not int or not 0 <= delay_steps <= 6:
            raise ValueError("delay must be 0..6 physics steps (training range 3..6)")
        self.voltage, self.sag_gain = voltage, sag_gain
        self.delay_steps, self.current_limit = delay_steps, current_limit
        self.history = deque([HOME.copy() for _ in range(delay_steps)], maxlen=delay_steps + 1)
        self.previous_motor = np.zeros(14)

    def compute(
        self, *, target, encoder_position, motor_velocity, external_torque, previous_actuator_torque
    ):
        target = vector(target, 14, "target")
        q = vector(encoder_position, 14, "encoder position")
        vel = vector(motor_velocity, 14, "motor velocity")
        ext = vector(external_torque, 14, "external torque")
        mot = vector(previous_actuator_torque, 14, "previous actuator torque")
        self.history.append(target.copy())
        delayed = self.history[0]
        vin = max(6.0, self.voltage - self.sag_gain * np.abs(self.previous_motor).sum())
        duty = (delayed - q) * 200 * 0.0028773775022263564
        if self.current_limit is not None:
            center = self.KT * vel / vin
            span = self.RESISTANCE * self.current_limit / vin
            duty = np.clip(duty, center - span, center + span)
        volts = vin * np.clip(duty, -1.0, 1.0)
        motor = self.KT * volts / self.RESISTANCE - self.KT**2 * vel / self.RESISTANCE
        # Preserve source distinction: friction loads use previous solve's motor
        # effort, not the newly computed command, and external excludes own friction.
        with np.errstate(over="ignore"):
            s = np.exp(-((np.abs(vel) / 2.890372094130307) ** 8.683259907618984))
        friction = (
            self.FRICTION_BASE
            + s * 0.004676345799486616
            + np.abs(ext * 8.515871897059342e-06 - mot * 0.2667860954283698)
            + s * np.abs(ext * 0.08077928978935671 - mot * 1.0722918395099123e-05)
        )
        quad = np.where(
            np.abs(mot) > np.abs(ext),
            0.004902565732332559 * np.abs(ext) ** 2,
            0.009972471242139415 * np.abs(mot) ** 2,
        )
        friction += s * quad
        self.previous_motor = motor.copy()
        return motor.astype(np.float32), friction.astype(np.float32)

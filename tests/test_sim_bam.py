"""BAM math tests against the pinned source equations, not gait validation."""

import numpy as np


def test_bam_current_limiter_and_motor_side_back_emf():
    from microduck_workshop.sim.bam import BamM6

    model = BamM6(delay_steps=0, voltage=7.5, sag_gain=0)
    tau, friction = model.compute(
        target=np.ones(14) * 10,
        encoder_position=np.zeros(14),
        motor_velocity=np.zeros(14),
        external_torque=np.zeros(14),
        previous_actuator_torque=np.zeros(14),
    )
    np.testing.assert_allclose(tau, model.KT * 1.75)
    assert np.all(friction > model.FRICTION_BASE)
    # Firmware limiter is voltage-limited, not an unconditional torque clamp.
    tau_fast, _ = model.compute(
        target=np.ones(14) * 10,
        encoder_position=np.zeros(14),
        motor_velocity=np.ones(14) * 100,
        external_torque=np.zeros(14),
        previous_actuator_torque=np.zeros(14),
    )
    assert (tau_fast < -model.KT * 1.75).all()

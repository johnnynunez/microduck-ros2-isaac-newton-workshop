import math

import numpy as np

from microduck_workshop.policy.contract import JOINT_NAMES


def test_merged_joint_map_uses_limits_not_arbitrary_parser_order():
    from microduck_workshop.sim.joint_map import map_merged_joints

    names, limits = [], []
    for i, name in enumerate(JOINT_NAMES):
        stem = name if i % 2 == 0 else f"passive_{name}_backlash"
        names.extend([stem + ":0", stem + ":1"])
        pair = [[-0.8, 0.8], [-math.pi / 180, math.pi / 180]]
        limits.extend(pair if i % 2 == 0 else pair[::-1])
    servos, backlash = map_merged_joints(names, np.array(limits))
    assert len(set(servos + backlash)) == 28
    for s, b in zip(servos, backlash):
        assert limits[s] == [-0.8, 0.8]
        assert np.isclose(limits[b][1], math.pi / 180)

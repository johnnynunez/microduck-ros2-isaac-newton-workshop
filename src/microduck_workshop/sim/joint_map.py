"""Resolve GA Newton's merged two-axis joints without assuming axis order."""

import numpy as np

from microduck_workshop.policy.contract import JOINT_NAMES


def map_merged_joints(names, limits):
    limits = np.asarray(limits)
    if len(names) != 28 or limits.shape != (28, 2):
        raise RuntimeError("Expected all 28 servo/backlash DOFs; refusing reduced topology")
    servos, backlash = [], []
    for name in JOINT_NAMES:
        passive = f"passive_{name}_backlash"
        candidates = [
            i
            for i, n in enumerate(names)
            if n in (name, passive) or n.rsplit(":", 1)[0] in (name, passive)
        ]
        if len(candidates) != 2:
            raise RuntimeError(f"Expected one two-DOF group for {name}, got {candidates}")
        b = [
            i for i in candidates if np.allclose(limits[i], [-np.pi / 180, np.pi / 180], atol=1e-6)
        ]
        if len(b) != 1:
            raise RuntimeError(f"Cannot uniquely identify ±1° passive backlash for {name}")
        s = next(i for i in candidates if i != b[0])
        if limits[s, 1] - limits[s, 0] < 0.1:
            raise RuntimeError(f"Unexpected servo limits for {name}")
        servos.append(s)
        backlash.append(b[0])
    if len(set(servos + backlash)) != 28:
        raise RuntimeError("DOF mapping is not bijective")
    return servos, backlash

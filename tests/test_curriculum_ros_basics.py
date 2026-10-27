"""CPU exercises only: fabricated arrays are not ROS or simulator evidence.

Set WORKSHOP_ROS_BASICS_IMPL=exercise to test the student's TODOs instead.
"""

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def impl():
    choice = os.environ.get("WORKSHOP_ROS_BASICS_IMPL", "solution")
    assert choice in {"exercise", "solution"}
    folder = "exercises" if choice == "exercise" else "solutions"
    path = ROOT / folder / "ros_basics" / "joint_watch.py"
    assert path.is_file(), f"Missing {choice}: {path}"
    spec = importlib.util.spec_from_file_location(f"joint_watch_{choice}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_select_positions_uses_names_not_array_order(impl):
    # Tiny, explicitly fabricated JointState-like arrays, not live telemetry.
    result = impl.select_positions(
        ["right_knee", "neck_pitch", "left_knee"],
        [0.25, 0.35, -0.15],
        ["left_knee", "right_knee"],
    )
    assert result == {"left_knee": -0.15, "right_knee": 0.25}
    assert list(result) == ["left_knee", "right_knee"]


@pytest.mark.parametrize("names, positions, requested", [
    (["knee"], [], ["knee"]),
    (["knee", "knee"], [0.1, 0.2], ["knee"]),
    (["knee"], [0.1], ["ankle"]),
    (["knee"], [float("nan")], ["knee"]),
    (["knee"], [float("inf")], ["knee"]),
    (["knee"], [True], ["knee"]),
    (["knee"], ["0.1"], ["knee"]),
    ([""], [0.1], [""]),
    ([42], [0.1], [42]),
    (["knee"], [0.1], ["knee", "knee"]),
])
def test_select_positions_rejects_ambiguous_or_invalid_data(impl, names, positions, requested):
    with pytest.raises(ValueError):
        impl.select_positions(names, positions, requested)


def test_select_positions_does_not_mutate_input(impl):
    names, positions = ["knee", "ankle"], [0.0, -0.4]
    assert impl.select_positions(names, positions, []) == {}
    assert names == ["knee", "ankle"]
    assert positions == [0.0, -0.4]


@pytest.mark.parametrize("stamp, now, expected", [
    (0, 0, "waiting_for_clock"),
    (1_000_000_000, 1_000_000_000, "within_sim_age"),
    (1_000_000_000, 1_500_000_000, "within_sim_age"),
    (1_000_000_000, 1_500_000_001, "stale_sim_age"),
    (2_000_000_000, 1_000_000_000, "future_stamp"),
])
def test_stamp_status_compares_only_simulation_time(impl, stamp, now, expected):
    assert impl.stamp_status(stamp, now, 500_000_000) == expected


@pytest.mark.parametrize("stamp, now, limit", [
    (-1, 2, 1), (1, -2, 1), (1, 2, 0), (1, 2, -1),
    (True, 2, 1), (1, False, 1), (1, 2, True),
    (1.0, 2, 1), (1, float("nan"), 1), (1, 2, "1"),
])
def test_stamp_status_rejects_invalid_nanoseconds(impl, stamp, now, limit):
    with pytest.raises(ValueError):
        impl.stamp_status(stamp, now, limit)

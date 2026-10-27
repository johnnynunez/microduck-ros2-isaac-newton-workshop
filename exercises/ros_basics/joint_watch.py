"""Two small TODOs for a read-only ROS 2 node; no ROS needed to test helpers.

Run from the repository root with:
    python -m exercises.ros_basics.joint_watch --ros-args -p use_sim_time:=true
The prepared Lyrical shell is required only for the live run.
"""


def select_positions(names, positions, requested):
    """Exercise A: return {requested_name: position} in requested order.

    Use message names, not a presumed joint-array order. Raise ValueError for:
    unequal name/position lengths; empty/non-string/duplicate names; duplicate
    requests; missing requested joints; nonfinite, bool or nonnumeric positions.
    Do not modify the input arrays. An empty request returns an empty dict.
    """
    raise NotImplementedError("Exercise A: map and validate joint positions")


def stamp_status(stamp_ns, now_ns, max_age_ns=500_000_000):
    """Exercise B: classify a message using the node's simulation clock.

    All arguments are integer nanoseconds (not bool). Timestamps must be >= 0;
    the age limit must be > 0. Invalid arguments raise ValueError.
    In this order, return:
      now_ns == 0                 -> 'waiting_for_clock'
      stamp_ns > now_ns            -> 'future_stamp'
      now_ns - stamp_ns > limit    -> 'stale_sim_age'
      otherwise                   -> 'within_sim_age'
    Equal-to-limit is allowed. This is NOT a wall-clock freshness/safety check.
    """
    raise NotImplementedError("Exercise B: compare timestamps in the same clock")


if __name__ == "__main__":
    # The reference node supplies only ROS wiring; it executes YOUR helpers.
    # rclpy is imported lazily inside run(), never during CPU helper tests.
    from solutions.ros_basics.joint_watch import run

    run(select_fn=select_positions, stamp_fn=stamp_status)

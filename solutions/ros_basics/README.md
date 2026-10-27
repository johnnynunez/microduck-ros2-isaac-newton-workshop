# ROS basics reference solution

[joint_watch.py](joint_watch.py) contains both complete helper solutions and the read-only ROS node. The exercise reuses its ROS wiring, but passes the student's own helper functions.

## Verify on CPU

From the repository root in the prepared Python 3.12 environment:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest --noconftest \
  tests/test_curriculum_ros_basics.py tests/test_curriculum_ros_node.py -q
```

The first file checks real helper behavior using fabricated arrays. The second explicitly substitutes fake ROS modules to test import boundaries, subscription wiring and cleanup. **Neither executes DDS, a ROS graph, a simulator or a GPU.** Live validation is a separate [Lab 1 checkpoint](../../docs/labs/01-ros-basics.md).

## Run against real ROS

From the repository root in the prepared Lyrical shell with the gateway and Newton telemetry running:

```bash
python -m solutions.ros_basics.joint_watch --ros-args \
  -p use_sim_time:=true -p joint_name:=left_knee
```

In a second prepared ROS terminal:

```bash
ros2 node info /joint_watch
ros2 param get /joint_watch use_sim_time
ros2 param get /joint_watch joint_name
```

Look for the real subscription and a changing message stamp; do not compare against a fabricated numeric output. A stationary joint can legitimately have an unchanged angle. Ctrl+C destroys the observer node and shuts down its ROS context, not the simulation or cloud instance.

## Why this solution

- `dict(zip(..., strict=True))` associates names and positions. Duplicate names are rejected before a dictionary could hide them; missing joints are never filled with zero.
- The node uses the sensor-data QoS profile. A reliable-only subscriber may not match a best-effort publisher; requesting best-effort can match either reliability offer. Inspect the publisher rather than blindly changing QoS.
- `use_sim_time` is the ROS node clock setting, not a different message type. Nanoseconds prevent an avoidable floating-point boundary error in this lesson.
- `within_sim_age` means only that the two simulation timestamps are close. It does not mean the camera is fresh in wall time or that a command is safe. The gateway's monotonic freshness and lease checks are separate.
- Logging is wall-clock throttled, not driven by a simulation timer. The observer prints at most once per wall second **when messages arrive**; silence is not a freshness verdict.
- The observer contains no actuator publisher or motion service client. ROS callbacks do not become a second owner of the robot.

Return to [the student route](../../docs/labs/README.md).

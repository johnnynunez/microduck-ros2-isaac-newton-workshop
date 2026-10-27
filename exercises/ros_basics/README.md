# ROS basics: read one joint correctly

**In class: 8 minutes inside [Lab 1](../../docs/labs/01-ros-basics.md).**
This observer never publishes commands, opens motion services or talks to hardware.

Edit only the two TODOs in [joint_watch.py](joint_watch.py):

1. **A — names before indices (4 minutes).** Build a name-to-position mapping, then select requested names. Reject malformed data rather than substituting zero. Positions are radians. The test uses deliberately reordered, fabricated arrays to expose index assumptions.
2. **B — clocks before ages (4 minutes).** Compare integer nanosecond timestamps. At a zero ROS clock, report waiting; distinguish a future stamp from an old sample. A paused simulation can keep the same age indefinitely, so this label must never authorize motion.

Run from the repository root, with the preinstalled Python 3.12/pytest environment:

```bash
WORKSHOP_ROS_BASICS_IMPL=exercise PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -m pytest --noconftest tests/test_curriculum_ros_basics.py -q
```

An untouched exercise fails with `NotImplementedError`; this is intentional. Work on A first with `-k select_positions`, then B with `-k stamp_status`. These are **CPU unit tests**, not a fake ROS publisher and not robot evidence.

Once both helpers pass, use the prepared **ROS 2 Lyrical** terminal at the repository root:

```bash
python -m exercises.ros_basics.joint_watch --ros-args \
  -p use_sim_time:=true -p joint_name:=left_knee
```

The shared adapter calls your helpers on real `sensor_msgs/msg/JointState` messages from `/workshop/microduck/joint_states` with sensor-data QoS. Stop with Ctrl+C. `joint_name` is read at startup: restart to choose another joint. No rclpy import occurs during the helper tests.

**If stuck:** compare [the complete reference solution](../../solutions/ros_basics/joint_watch.py) and its [explanation](../../solutions/ros_basics/README.md). Reading a solution is allowed; be ready to explain why a future timestamp is not fresh data.

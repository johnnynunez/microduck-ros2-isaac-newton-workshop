# Lab 1 — a ROS graph you can inspect

**20 minutes · 15:15–15:35.** Goal: find real telemetry, read its schema, and complete a read-only subscriber. The prewarmed simulator and gateway must already be running; do not start a second copy.

A **node** is a ROS participant. A **topic** is a named stream of typed messages. A **service** is a typed request/reply. A **parameter** configures one node. ROS can connect processes; it is not the physics engine or the learned controller.

## 1. Discover before subscribing — 4 minutes

In the **ROS tools** terminal opened in [pre-class preparation](00-before-class.md#2-prepare-the-terminals):

```bash
ros2 node list
ros2 topic list -t
ros2 topic info /workshop/microduck/joint_states --verbose
ros2 interface show sensor_msgs/msg/JointState
```

Identify the publisher node in `topic info`; that is better than guessing its node name. In `JointState`, `name[i]` describes `position[i]`. Positions use radians. The schema permits an optional empty velocity/effort array; the observer lesson requires positions and does not invent missing values.

Read one real sample, then measure for a few seconds:

```bash
timeout 8s ros2 topic echo /workshop/microduck/joint_states \
  --once --qos-reliability best_effort --qos-durability volatile
timeout 5s ros2 topic hz /workshop/microduck/joint_states
```

Do not expect a fixed frequency on every cloud GPU. Record what you actually measured. Timeout during `hz` ends the measurement window; timeout before the first `echo` sample means the observation is missing.

## 2. Implement two small helpers — 8 minutes

Open [the exercise](../../exercises/ros_basics/README.md) and edit [joint_watch.py](../../exercises/ros_basics/joint_watch.py):

- **A (4 minutes):** select joint positions by name, not assumed array order; reject ambiguous or invalid values.
- **B (4 minutes):** classify a sample's **simulation** timestamp as waiting, future, old or within the configured age.

In a **host/editor** terminal, run the CPU checks from your checkout:

```bash
WORKSHOP_ROS_BASICS_IMPL=exercise PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  .workshop/student-venv/bin/python -m pytest --noconftest tests/test_curriculum_ros_basics.py -q
```

TODO failures are expected before you edit. The tests use explicitly fabricated input arrays, not a live ROS feed. If time runs out, open [the complete solution and explanation](../../solutions/ros_basics/README.md); rejoin the live checkpoint rather than spending the whole workshop on Python validation.

## 3. Put your helpers on the real graph — 5 minutes

In a **host** terminal, run your edited observer in the prepared agent image (the exercise directory is mounted read-only):

```bash
docker compose run --rm --no-deps --workdir /opt/workshop agent \
  python -m exercises.ros_basics.joint_watch --ros-args \
  -p use_sim_time:=true -p joint_name:=left_knee
```

If you deliberately choose the reference observer instead, stop your observer with Ctrl+C,
then run this from the **host** (the solution is not otherwise mounted in the image):

```bash
docker compose run --rm --no-deps --workdir /opt/workshop \
  -v "$PWD/solutions:/opt/workshop/solutions:ro" agent \
  python -m solutions.ros_basics.joint_watch --ros-args \
  -p use_sim_time:=true -p joint_name:=left_knee
```

Leave your selected observer running. In a second **ROS tools** terminal:

```bash
ros2 node info /joint_watch
ros2 param get /joint_watch use_sim_time
ros2 param get /joint_watch joint_name
timeout 8s ros2 topic echo /clock --once
```

Look for the joint subscription and real stamps, not a particular numeric knee angle. The node logs no more than once per wall second when messages arrive. Ctrl+C stops **your observer**, not the gateway. To choose `right_knee`, restart with `-p joint_name:=right_knee`; the selection parameter is read at startup.

**QoS:** the subscriber requests best-effort sensor-data delivery. A reliable-only subscriber can fail to match a best-effort publisher. Inspect the offered/requested policies with `topic info --verbose` before changing them.

**Time:** `use_sim_time:=true` makes this node use `/clock`. Without it, comparing a simulation stamp to Unix wall time gives nonsense. `within_sim_age` is not a motion safety verdict: if the simulator pauses, its timestamps can pause too. A wall-clock watchdog is still necessary.

## 4. Read a service schema — 3 minutes

```bash
ros2 service list -t
ros2 interface show microduck_workshop_interfaces/srv/BoundedMotion
ros2 interface show microduck_workshop_interfaces/srv/Observe
```

Find the request/response separator. Explain why bounded motion carries an episode, request identity and generation, rather than just three velocities. **Do not call motion yet.** There is no direct actuator publisher in this exercise. Any optional manual `cmd_vel` lesson requires explicit staff enablement and exclusive ownership; it is not part of this route.

## Checkpoint

Show a peer: the real publisher and message type, a passing helper check, and the observer's `use_sim_time` setting. Answer: “Would reordering the incoming joint names break my code?” and “Why can a paused clock not prove freshness?”

If no samples appear, use [the troubleshooting table](../troubleshooting.md); stop after two minutes and ask staff. Next: [simulation and sensors](02-simulation.md).

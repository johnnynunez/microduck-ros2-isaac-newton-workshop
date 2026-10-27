# Lab 2 — who owns the robot, and where do its senses come from?

**20 minutes · 15:35–15:55.** Goal: distinguish the Newton physics owner, onboard sensor evidence, and a human-only preview.

## 1. Inspect the running stack — 5 minutes

Use the startup/runtime evidence procedure in the [repository README](../../README.md). The pre-class instance is already warm; do not launch another simulation or gateway. Check the **actual imported** Sim/Lab/Newton versions, device, asset identity and policy identity in the runtime receipt. A configured target or container tag alone does not establish what ran.

Locate **Isaac Lab's Newton model** in that evidence. Isaac Lab owns state and stepping; Isaac Sim 6.2 supplies rendering/application services. A second Sim-native articulation/physics owner is not a fix for a bridge problem. PhysX and MJLab are not alternative runtimes for this workshop.

Write down the current episode ID. Resets create a boundary: old observations, pending commands and generation assumptions must not survive it.

## 2. Inspect encoders and the real IMU — 4 minutes

```bash
ros2 topic type /workshop/microduck/joint_states
ros2 topic type /workshop/microduck/imu
ros2 interface show sensor_msgs/msg/Imu
timeout 8s ros2 topic echo /workshop/microduck/imu \
  --once --qos-reliability best_effort --qos-durability volatile
```

Find angular velocity (rad/s), linear acceleration (m/s²) and the header. The workshop does **not** provide a measured IMU orientation; inspect the unavailable-orientation representation rather than treating a default quaternion as a valid attitude measurement. The [transport contract](../transport.md) is the authority for fields and provenance.

Do not replace this stream with simulator root pose or perfect orientation. A matching message type does not make its contents a sensor measurement.

## 3. Match an image to its calibration — 7 minutes

Open the **onboard** view through your secure Brev preview, then the separate human overview. Describe a feature visible to the onboard camera. The overview can help *you* debug; it must never become agent input.

```bash
ros2 topic info /workshop/microduck/camera/image_rect --verbose
ros2 topic info /workshop/microduck/camera/camera_info --verbose
timeout 8s ros2 topic echo /workshop/microduck/camera/image_rect \
  --once --field header --qos-reliability best_effort --qos-durability volatile
timeout 8s ros2 topic echo /workshop/microduck/camera/camera_info \
  --once --qos-reliability best_effort --qos-durability volatile
```

The image and its paired CameraInfo must share a stamp and optical frame; width, height and intrinsics must describe the actual image. Separate `--once` commands may catch **different frames**, so a mismatch between those two samples alone is not a bug. Use the release's recorded paired-frame receipt (or timestamp-matched capture) to establish exact pairing; do not claim it from unrelated screenshots.

This is an authored, distortion-free **teaching pinhole camera**, not a hardware-calibration result. Its mount and intrinsics must be identified. Ordinary CPU image publication into ROS is not GPU zero-copy just because the next node uses CUDA.

## 4. Predict a pause, then observe it — 4 minutes

Before the instructor pauses the simulation, predict what happens to `/clock` and your joint observer. The instructor uses only the verified runtime control path, with motion disabled; do not improvise a reset or HTTP command.

Watch a bounded clock measurement:

```bash
timeout 5s ros2 topic hz /clock
```

When simulation time stops advancing, a sim-time age can remain small while wall time passes. The separate monotonic watchdog and image-capture freshness checks must still expire. An instructor demonstration of the expiry receipt is stronger evidence than the absence of new log lines. After reset or time rewind, observations must belong to the new episode before use.

## Checkpoint

Record the real backend identity, one IMU field and its units, the onboard camera frame ID, and the evidence used to confirm image/calibration pairing. Explain why the overview, root pose and default IMU quaternion cannot serve as the agent's navigation sensors.

A missing camera or Newton runtime is a blocked checkpoint, not permission to substitute a canned publisher. Next: [reinforcement learning](03-reinforcement-learning.md).

# Lab 2 — who owns the robot, and where do its senses come from?

**20 minutes · 15:35–15:55.** Goal: distinguish the Newton physics owner, onboard sensor evidence, and a human-only preview.

## 1. Inspect the running stack — 5 minutes

The pre-class instance is already warm; do not launch another simulation or gateway.
In a **host** terminal, inspect the actual imported runtime and current health:

```bash
python3 -m json.tool .workshop/sim-output/episode/runtime_identity.json
curl --fail --max-time 3 --noproxy '*' http://127.0.0.1:8766/v1/health
```

Check Sim `6.2.0.0`, Newton `1.6.1`, the actual device and asset/policy identity.
Lab's installed distribution may report `28.0.0`; the pinned product is Lab **3.0**.
Health reports separate `command_profile` and `step_profile` capabilities. The Compose
route selects `step-forward-v1`; `NATIVE_VALIDATED` is not an end-to-end capstone pass.
A configured target or container tag alone does not establish what ran.

Locate **Isaac Lab's Newton model** in that evidence. Isaac Lab owns state and stepping; Isaac Sim 6.2 supplies rendering/application services. A second Sim-native articulation/physics owner is not a fix for a bridge problem. PhysX and MJLab are not alternative runtimes for this workshop.

Write down the current episode ID. Resets create a boundary: old observations, pending commands and generation assumptions must not survive it.

## 2. Inspect encoders and the real IMU — 4 minutes

In the **ROS tools** terminal:

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

## 4. Stop the source before the training handover — 4 minutes

Predict what happens to `/clock`, the observer and capture age when the source stops.
At the instructor's cue, with **no agent or motion running**, use a **host** terminal:

```bash
bash scripts/sim_stop.sh
sleep 1
docker compose exec -T ros bash /opt/workshop/entrypoint.sh \
  timeout 8s ros2 service call /workshop/microduck/observe \
  microduck_workshop_interfaces/srv/Observe '{}'
```

This is a deliberate simulator shutdown, **not a pause/reset API**. The ROS gateway stays
up for the observation check. Record the actual refusal; it must not authorize motion
from the last GO image. A timeout is missing evidence, not a stale-observation pass.
The preview can retain an explicitly marked last image. Silence in the joint observer
is not proof of a watchdog verdict.

A frozen simulation clock cannot measure wall age. The gateway uses original monotonic
capture time; it does not restamp an old image on receipt. Keep this stale-source result
for Lab 4. Leave the simulator stopped: Lab 3 next tears down the remaining services
before training, then starts a **new** operator-authorized episode.

## Checkpoint

Record the real backend identity, one IMU field and its units, the onboard camera frame ID, and the evidence used to confirm image/calibration pairing. Explain why the overview, root pose and default IMU quaternion cannot serve as the agent's navigation sensors.

A missing camera or Newton runtime is a blocked checkpoint, not permission to substitute a canned publisher. Next: [reinforcement learning](03-reinforcement-learning.md).

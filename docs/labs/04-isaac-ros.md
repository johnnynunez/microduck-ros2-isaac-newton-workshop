# Lab 4 — Isaac ROS 5.0 sees a signal, not the simulator's answer

**15 minutes · 16:15–16:30.** Goal: trace an AprilTag detection back to actual onboard pixels and understand when an observation becomes stale.

## 1. Start from the right architecture — 3 minutes

Lab 3 restored playback using `brev_start.sh`; Compose already starts the gateway and detector. Do **not** launch a second detector. Open a new **ROS tools** terminal and confirm **Isaac ROS 5.0 / ROS 2 Lyrical on Noble**.

Isaac ROS 5.0 uses native **`rosidl::Buffer`** support for accelerated data paths. Removed Isaac ROS 4.x NITROS packages are **not** installation or coding instructions for this lesson. Nor does a CPU/JPEG-to-ROS boundary become GPU zero-copy just because a CUDA detector follows it.

The actual onboard camera feeds `/workshop/microduck/camera/image_rect` and matching
`/workshop/microduck/camera/camera_info`. The detector uses **tag36h11**, **CUDA**, and
an authored **0.20 m black-border edge**. Compose passes `tag_size:=0.20` to the launch
file, which sets the detector's **`size`** parameter (not a parameter named `tag_size`):

```bash
ros2 param get /workshop/microduck/apriltag size
ros2 param get /workshop/microduck/apriltag tag_family
ros2 param get /workshop/microduck/apriltag backends
```

## 2. Find the real detector output — 4 minutes

```bash
ros2 node list
ros2 topic list -t
ros2 topic info /workshop/microduck/camera/image_rect --verbose
ros2 interface show microduck_workshop_interfaces/srv/Observe
```

Find the detector node and confirm this topic in the real graph:

```bash
ros2 topic info /workshop/microduck/tag_detections --verbose
ros2 topic type /workshop/microduck/tag_detections
timeout 8s ros2 topic echo /workshop/microduck/tag_detections \
  --once --qos-reliability best_effort --qos-durability volatile
```

Match the detection's source header to the recorded image/capture pair. Check the configured tag family and size. A package loading, an empty output array, or a synthetic publisher carrying plausible IDs is not evidence that CUDA detected a tag in this image.

## 3. Query the gateway's allowlisted observation — 4 minutes

```bash
timeout 8s ros2 service call /workshop/microduck/observe \
  microduck_workshop_interfaces/srv/Observe '{}'
```

Inspect `fresh`, `episode_id`, `generation`, `frame_sequence`, `sim_time`, `age_s`, `frame_id`, `tag_ids` and `reason`. The agent receives these allowlisted fields, not global poses, an overview image, lease tokens or detector-internal coordinates.

For the lesson game, **tag 0 means GO** and **tag 1 means STOP**. This is our game convention, not an upstream MicroDuck feature. The instructor selects the rehearsed scene condition; do not publish IDs yourself.

Compare what you can see in the actual onboard view with the detected ID and its source image. A fresh image with no allowed signal still does **not** authorize movement.

## 4. Compare fresh and stopped-source evidence — 4 minutes

Compare this episode's fresh result with the stopped-source observation you saved at the
end of [Lab 2](02-simulation.md#4-stop-the-source-before-the-training-handover--4-minutes).
The old episode must not authorize motion now. The **0.5-second wall-age limit** uses
original capture time, not message receipt time; a late detection cannot refresh old pixels.

Explain which fields changed: episode, frame sequence, age and refusal reason. The
instructor can show separately labeled native proof-expiry/priority-stop receipts from
[fixed-step validation](../step.md). Those are not your own live ROS acceptance.
If you missed the source-stop experiment, mark it **observed**, rather than stopping and
restarting the class stack a second time. Keep the new fresh GO episode ready for Lab 5.

## Checkpoint

Keep a real image/detection identity pair and one fresh/one stale observation result. Explain why a newly received message can still describe old pixels.

If only an official sample rosbag worked, label it **Isaac ROS sample-input validation**, not live MicroDuck perception. If no live detection is available, do not proceed to autonomous motion. Next: [CASCADE signal game](05-cascade.md).

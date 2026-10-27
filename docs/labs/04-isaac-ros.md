# Lab 4 — Isaac ROS 5.0 sees a signal, not the simulator's answer

**15 minutes · 16:15–16:30.** Goal: trace an AprilTag detection back to actual onboard pixels and understand when an observation becomes stale.

## 1. Start from the right architecture — 3 minutes

Use the verified Isaac ROS detector launch/remap procedure in the [README](../../README.md), with interactive playback restored and the agent still disabled. Confirm **Isaac ROS 5.0 / ROS 2 Lyrical on Noble**.

Isaac ROS 5.0 uses native **`rosidl::Buffer`** support for accelerated data paths. Removed Isaac ROS 4.x NITROS packages are **not** installation or coding instructions for this lesson. Nor does a CPU/JPEG-to-ROS boundary become GPU zero-copy just because a CUDA detector follows it.

The actual onboard camera feeds `/workshop/microduck/camera/image_rect` and matching `/workshop/microduck/camera/camera_info`. The detector uses **tag36h11** with the scene's explicitly authored physical tag size. Use the release's actual size and remaps, not guessed dimensions.

## 2. Find the real detector output — 4 minutes

```bash
ros2 node list
ros2 topic list -t
ros2 topic info /workshop/microduck/camera/image_rect --verbose
ros2 interface show microduck_workshop_interfaces/srv/Observe
```

Find the detector node and its output in the real graph/launch instructions. The frozen gateway contract names the camera topics, but does not require you to guess a detector-specific output name. Copy the actual detection topic when prompted:

```bash
read -r -p "Actual AprilTag detection topic from your graph: " DETECTIONS_TOPIC
ros2 topic info "${DETECTIONS_TOPIC:?A real topic name is required}" --verbose
ros2 topic type "$DETECTIONS_TOPIC"
timeout 8s ros2 topic echo "$DETECTIONS_TOPIC" \
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

## 4. Break freshness deliberately, without motion — 4 minutes

With the agent disabled, the instructor pauses/stops the actual camera source using the rehearsed runtime procedure. After more than the **0.5-second wall-age limit**, call `observe` again. It must refuse freshness and explain why; receiving an old detection *now* does not give its pixels a new capture time. A negative age, wrong frame, unknown episode or source time rewind is not a successful observation.

Restore the source; require a new source frame and valid episode mapping before rejoining. Do not relax the age limit to hide a slow GPU/model. For a pause/reset exercise, use staff controls rather than guessing administrative endpoints.

## Checkpoint

Keep a real image/detection identity pair and one fresh/one stale observation result. Explain why a newly received message can still describe old pixels.

If only an official sample rosbag worked, label it **Isaac ROS sample-input validation**, not live MicroDuck perception. If no live detection is available, do not proceed to autonomous motion. Next: [CASCADE signal game](05-cascade.md).

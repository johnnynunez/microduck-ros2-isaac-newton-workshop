# Troubleshooting — identify the layer before changing it

**Student rule:** after two minutes on an environment problem, ask staff and rejoin at the next checkpoint. Do not install another ROS distro, change physics backend, expose public ports or weaken safety checks to keep up.

Start with [the prepared environment](labs/00-before-class.md) and the release's actual commands/readiness notes in the [README](../README.md). All ROS checks below run in the prepared **Lyrical** terminal on your own Brev instance, from the repository root.

## ROS and the observer

| Symptom | First check | Correct response |
|---|---|---|
| `ros2` or `rclpy` is missing | Are you in the ROS tools environment rather than the simulator/test environment? | Use the tested Lyrical shell/sourcing procedure. Do not pip-install a lookalike or mix Jazzy libraries into the process. |
| Custom service type is unknown | `ros2 pkg prefix microduck_workshop_interfaces` | Source the prepared built overlay after its Lyrical underlay. Building missing interfaces is a pre-class task; ask staff now. |
| Topic list is empty | `printenv ROS_DISTRO ROS_DOMAIN_ID` and `ros2 node list` | Confirm the actual gateway/simulator is running, the same local domain and the expected process/container network. Do not enable public discovery as a fix. |
| Topic exists but no data arrives | `ros2 topic info /workshop/microduck/joint_states --verbose` | Check actual publishers and offered/requested QoS; use sensor-data best-effort/volatile for this observer. Check stepping and `/clock`. A name in the graph alone is not data. |
| `NotImplementedError` in the exercise | Which helper TODO remains? | Complete it or read the full solution. This is intentional, not a ROS install problem. |
| Test command cannot import pytest | Are you in the preinstalled test interpreter? | Use that environment. Do not start dependency installation during the timed lesson. No ROS/GPU is required for helper tests. |
| `waiting_for_clock` | `ros2 param get /joint_watch use_sim_time` and one `/clock` message | Confirm simulation time is enabled and advancing. Zero time can be the initial state; do not interpret it as a fresh safety observation. |
| `future_stamp` or implausibly old time | Compare the message stamp with `/clock`; check for reset | Use the same time domain. Reset/rewind needs a new episode/cache. Tiny ordering differences can occur; do not treat future stamps as permission to move. |
| No observer log while paused | Is a new message arriving? | The observer is message-driven and throttles logs by wall time. Silence is not proof of an expired safety lease; inspect the actual watchdog receipt. |
| Duplicate node names / conflicting lease owner | `ros2 node list`; staff inspect the runtime process list | Stop the accidental duplicate through its documented lifecycle. Do not launch another simulator/gateway to fix the first one. |

Useful bounded read-only checks:

```bash
timeout 8s ros2 topic echo /clock --once
timeout 8s ros2 topic echo /workshop/microduck/joint_states \
  --once --qos-reliability best_effort --qos-durability volatile
ros2 service list -t
```

`timeout` exit code 124 means the time budget expired. If the command was a continuous measurement this can be expected; if it was waiting for the first observation, the checkpoint did not complete. Ctrl+C in an observer is not a robot stop.

## Newton, training and assets

| Symptom | Check / response |
|---|---|
| Runtime receipt says a different backend/version | Stop this stage and ask staff. Source/config targets do not override imported runtime facts. **No PhysX or MJLab substitute.** |
| Robot appears but encoders/IMU never change | Check real Lab stepping/owner data, not only the renderer. A stationary pose can be legitimate; a prim reader observing the wrong model is not authoritative Newton telemetry. |
| Policy tensor sizes match but gait falls or drifts | Keep the failure. Inspect joint order/home, raw-action history, embedded normalization, scales/filters, delays, BAM/backlash and sensor estimates in the pinned contract. Do not replace learned control with a scripted gait. |
| Short training is slow or OOM | Use the rehearsed one-GPU profile and remove competing workloads through documented controls. Stop at the lesson budget. Do not scale environments blindly or change student drivers. |
| Public ONNX will not resume PPO | Expected: inference weights alone do not restore critic, optimizer or counters. A short fresh training experiment and a full resume are different tasks. |
| Download hash/license failure | Do not bypass checks, invent a checksum or copy private Creative assets. Use pinned public sources, review the separate CC BY-NC-SA mesh terms and obtain the required acknowledgment. |

## Camera and Isaac ROS 5.0

| Symptom | Check / response |
|---|---|
| Preview works but detector sees nothing | Make sure it is the **onboard** camera, not the human overview. Inspect real detector remaps, tag36h11 family, physical size, visibility and actual CUDA graph. A preview is not detection evidence. |
| Image and CameraInfo appear to have different stamps | Separate `--once` calls can capture different frames. Check a genuinely timestamp-paired receipt and matching frame/intrinsics before diagnosing a bug. |
| An old Isaac ROS tutorial names missing NITROS packages | Use the pinned **5.0** route with native **`rosidl::Buffer`** support. Do not install removed 4.x packages or replace Lyrical with Jazzy. |
| `observe` says stale despite a recent detection arrival | Source image capture age matters, not subscriber receipt time. Check stopped source, unknown episode/frame/sequence mapping and time rewind. Never restamp old pixels as fresh. |
| Fresh observation has empty `tag_ids` | A usable fresh image need not contain the game signal. Refuse motion. Check actual camera scene; do not synthesize an ID. |
| Only a sample rosbag detects tags | This validates that recorded input path, not live MicroDuck camera integration. Keep the live gate blocked until real onboard evidence exists. |

## CASCADE and motion

- **Local model unavailable or tool calls unsupported:** check the release's pinned local-model profile and actual server/tool-call receipt. Do not silently switch to a hosted model, mock brain or scripted decision loop.
- **Request rejected:** keep its reason. Episode/generation mismatch, a conflicting owner, nonfinite/out-of-range values and a stop latch require diagnosis, not automatic retries, clipping or re-arm.
- **Request timed out after sending:** delivery is uncertain. Do **not** resend motion. Use the known request's status/verification path and involve staff; an absent ACK is not proof the robot did nothing.
- **Accepted/completed but not verified:** keep `verification_available` and `verified` distinct. Tool ACK, task completion and zero intent are not physical safety verdicts. An unavailable evaluator result must stay unavailable.
- **Agent keeps trying while stopped:** stop the agent, preserve the trace and ask staff. The model must not reset a latch or acquire direct actuator access.

The rehearsed priority stop is:

```bash
timeout 8s ros2 service call /workshop/microduck/emergency_stop std_srvs/srv/Trigger '{}'
```

Use it on your simulated episode when directed or when motion needs to stop. Inspect the result and independent state. If the reply is unknown or the stack is unresponsive, notify staff immediately and use the rehearsed supervisory shutdown procedure. A failed service call is not a successful stop; a responding service is not proof of rest. No physical robot is in scope.

Do not debug by exposing the loopback motion server, model API or DDS publicly. Use **Brev secure preview / authenticated tunnels** only. Domain IDs do not authenticate users.

## Billing and teardown

A stopped container, closed browser or disconnected SSH session can leave your Brev GPU instance running and charging. Follow [the final checklist](labs/06-wrap-up.md): save work, stop workshop processes, stop/delete the **cloud instance**, read back its state, and check retained storage. Complete this before the **24-hour credit expiry**; do not assume credit exhaustion performs cleanup.

[Return to student route](labs/README.md) · [Instructor runbook](instructor.md)

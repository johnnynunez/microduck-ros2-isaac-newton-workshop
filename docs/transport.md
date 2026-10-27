# Frozen runtime transport v1

This boundary connects a Lab-owned Newton simulation to a **real ROS 2 Lyrical gateway**. It is loopback-only instructor plumbing; CASCADE must call the ROS services, not bypass ROS with HTTP. No physical robot binding is implemented.

## Simulation HTTP API (127.0.0.1:8766)

- `GET /v1/health`: JSON `protocol_version:1`, `ready:bool`, `physics:"newton"`, `episode_id:str`, `generation:int`, `sim_time:float`, `runtime:dict` with actual versions/device/policy and asset identity. No guessed success.
- `GET /v1/state`: `episode_id`, `sequence`, `sim_time`, `capture_monotonic_s`, `joint_names` (14 policy encoder names), `joint_position`, `joint_velocity`, `imu:{angular_velocity:[3],linear_acceleration:[3]}`, `command_active:bool`, `stop_latched:bool`. Values come from the actual owner. No root/world pose, perfect odometry or GT orientation.
- `GET /v1/camera`: actual onboard JPEG. Atomic headers `X-Microduck-Episode`, `X-Microduck-Sequence`, `X-Microduck-Sim-Time`, `X-Microduck-Capture-Monotonic`. No placeholder image. Return 503 before a real frame exists.
- `GET /v1/camera_info`: static episode calibration `width`, `height`, `frame_id`, `encoding:"rgb8"`, `distortion_model:"plumb_bob"`, `k:[9]`, `d:[5]`, `r:[9]`, `p:[12]`. Gateway gives Image and CameraInfo exactly the image's timestamp/frame ID.
- `GET /v1/overview`: human-only JPEG for a browser preview; never an agent perception source.
- `POST /v1/claim` body `{"owner_id":"ascii-id"}`: returns `lease_token`, `episode_id`, `generation`, `lease_timeout_s:0.5`. Refuse a conflicting unexpired owner. Token is an opaque random secret, never logged or sent to the model.
- `POST /v1/command`: exact `MotionCommand.as_dict()` body. Require the `X-Workshop-Lease` header. Reject mismatched episode/generation, stale owner, repeated request ID and latched stop; do not silently clip. Atomically reserve/increment generation. Response `accepted:bool`, `episode_id`, `request_id`, `generation`, `status`, `reason`. Unknown delivery must not be retried.
- `POST /v1/renew`: body `{"episode_id":"..."}` and lease header. Refresh monotonic wall lease, not command duration. Invalid/expired owner cannot revive motion.
- `POST /v1/stop`: body `{"episode_id":"...","latch":true}`. Priority lane, independent of a blocked command/model call; no lease required for an episode-matching local stop. Increment generation, zero intent, invalidate owner/pending commands; preserve the latch. The balancing policy may continue; zero intent is not torque-off or proof of rest.
- `GET /v1/status/<request_id>`: `known`, `episode_id`, `request_id`, `generation`, `status`, `completed`, `verification_available`, `verified`, `reason`. Before a real evaluator verdict, availability=false and verified=false. Keep coordinates/GT metrics in evaluator artifacts, not this response.
- Operator-only reset may be added as an explicitly gated local administrative command. It is never an agent tool and never runs automatically at task start or after a failed request.

`MotionCommand` fields and envelope are in `microduck_workshop.contracts`. Physics mutations occur only on the simulation thread. ROS/HTTP threads update a validated intent queue. Separate wall watchdog expiry and simulation-time command expiry both force zero intent. Native state/sensor checks continue without verbose recording. A paused simulator must consume zero intent before resuming.

## Real ROS gateway contract

Default namespace `/workshop/microduck`; configurable ROS_DOMAIN_ID, local-host discovery only. The gateway owns the simulator lease and renews it independently of model inference. It refuses hardware endpoints. Only one gateway owns actuation.

Topics: `joint_states` (sensor_msgs/JointState), `imu` (sensor_msgs/Imu, orientation unavailable), `camera/image_rect` (sensor_msgs/Image), `camera/camera_info` (sensor_msgs/CameraInfo). `/clock` uses actual Lab simulation time. Camera is a distortion-free teaching pinhole camera; identify its authored mount/intrinsics rather than claiming hardware calibration. Publish actual encoder/IMU data, not a synthetic test feed. A separately enabled manual `cmd_vel` exercise must not compete with an agent command owner.

Custom package `microduck_workshop_interfaces` provides:

`BoundedMotion.srv` request:
```
string episode_id
string request_id
uint64 expected_generation
float64 vx
float64 vy
float64 wz
float64 duration_s
```
response:
```
bool accepted
string episode_id
string request_id
uint64 generation
string status
string reason
```

`MotionStatus.srv` request `string episode_id`, `string request_id`; response `bool known`, `bool completed`, `bool verification_available`, `bool verified`, `string status`, `string reason`, `uint64 generation`.

`Observe.srv` empty request; response `bool fresh`, `string episode_id`, `uint64 generation`, `uint64 frame_sequence`, `float64 sim_time`, `float64 age_s`, `string frame_id`, `int32[] tag_ids`, `string reason`.

Services are `bounded_motion`, `motion_status`, `observe`, and `emergency_stop` (std_srvs/Trigger). The gateway returns allowlisted fields only. Model-facing observation never includes lease secrets or simulation truth.

## Perception and game

Isaac ROS 5.0 CUDA AprilTag consumes the actual onboard image and CameraInfo. Use family tag36h11 with an explicitly authored physical tag size. Map detector headers back to a recent camera publication/capture record. Receiving an old detection now does not make its image fresh. Reject unknown epochs, wrong frame, stopped camera and age over 0.5 wall seconds. Clear the cache on episode/time rewind. No synthetic detector fallback in live acceptance.

A simple signal game uses tag 0 as GO, tag 1 as STOP; this is a lesson convention, not an upstream robot capability. The local model first observes, then may request one bounded forward action when the appropriate signal is genuinely visible; otherwise it must refuse motion. No global route planning, perfect localization or automatic completion from a tool ACK.

## CASCADE domain

Resource kind is mobile_base; one written command resource owns the full endpoint. Tools: `microduck.observe`, `microduck.walk_bounded(vx,vy,wz,duration_s)`, `microduck.verify`. The real domain uses the ROS services above and explicit local `OpenAICompatClient` + `AgentOrchestrator`, decompose=false, bounded requests/steps, no hosted/mock fallback. Emergency stop/task_done are supplied by the composed runtime. Staff-only reset is not exposed.

## Evidence

Runtime tests must preserve the actual backend/version IDs, model requests/responses, camera/detection/command IDs, policy observations/actions and evaluator verdicts. A rosbag quickstart tests Isaac ROS, not live MicroDuck perception. CPU fake transports are labeled unit tests, not capstone success. Frozen API changes must be coordinated through the parent before dependent code is changed.

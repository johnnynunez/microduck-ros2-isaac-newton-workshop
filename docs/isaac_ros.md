# Isaac ROS 5.0 / ROS 2 Lyrical sidecar

This is a **simulation-only** gateway, not a physical MicroDuck driver. Its public boundary is [transport.md](transport.md); do not mix Sim's bundled Python/ROS libraries into this process.

## Version and installation boundary

- Ubuntu **24.04 Noble**, Python **3.12**, ROS 2 **Lyrical**, Isaac ROS **5.0**.
- Lyrical on Noble comes from **NVIDIA's buildfarm**, not the upstream ROS apt repository. The upstream apt source is used only for distribution-independent tools such as colcon.
- x86 prerequisites in the [5.0 requirements](https://nvidia-isaac-ros.github.io/v/release-5.0/getting_started/index.html): Ampere or newer, CUDA **13.2+**, driver **595+**. Installation never changes host drivers.
- [Buildfarm instructions](https://nvidia-isaac-ros.github.io/v/release-5.0/getting_started/isaac_ros_buildfarm_cdn.html), [AprilTag package API](https://nvidia-isaac-ros.github.io/v/release-5.0/repositories_and_packages/isaac_ros_apriltag/isaac_ros_apriltag/index.html).
- The observed upstream AprilTag tag is **`v5.0-0`**, commit `95df59e5dc9c253b6e8e11471c10fd510b036fdd` (not `v5.0.0`). Runtime uses the signed prebuilt Debian package; exact installed versions are recorded with `dpkg-query`.
- This pipeline does **not** import removed NITROS/managed-NITROS/PyNITROS APIs. It uses ordinary `sensor_msgs/Image` across DDS into the ROS 5 component. CPU JPEG decode/publication is **not GPU zero-copy**. GPU acceleration starts in Isaac ROS's CUDA detector.

## Build before class

The portable setup entrypoint is `bash scripts/brev_setup.sh`; it uses capped containers for both stages. From the repository root, the equivalent Dockerfile builds are:

```bash
docker build -f docker/ros5-base.Dockerfile -t roscon/ros5-base:5.0 .
docker build -f docker/Dockerfile -t roscon/microduck-ros5:local .
```

On the shared instructor workstation use the capped launcher documented in the task handoff; do not run uncapped builds. `scripts/ros_bootstrap_local.sh` is the bounded equivalent base installation: Ubuntu container with 24 GiB/8 CPU caps, the same checked-in installer, package receipt, and commit to the local base tag. It always removes its named container on exit. Images and apt packages are large; provisioning is outside the two-hour lesson.

`/opt/workshop-receipts/dpkg-lock.tsv` records the complete installed package set. The Ubuntu base is digest-pinned. Signed apt source minor versions are pinned; a future rebuild can still differ when upstream publishes patch updates. Preserve the resulting OCI digest plus package receipt for the class; do not call a floating apt rebuild byte-identical. No invented public container tag is used.

## Run with the real simulation

1. Start the parent-owned Lab/Newton HTTP adapter on `127.0.0.1:8766` first. Its health must report protocol 1, ready=true, physics=newton. It must deliver actual state and atomic JPEG capture headers. A fixture is not acceptable for live acceptance.
2. `WORKSHOP_GPU=0 bash scripts/brev_start.sh` (single-GPU Brev); instructor workstation uses `WORKSHOP_GPU=1` for this sidecar.
3. Query the real services from inside the image:

```bash
docker compose exec ros bash /opt/workshop/entrypoint.sh ros2 service call /workshop/microduck/observe microduck_workshop_interfaces/srv/Observe '{}'
docker compose exec ros bash /opt/workshop/entrypoint.sh ros2 topic echo /workshop/microduck/joint_states --once
docker compose exec ros bash /opt/workshop/entrypoint.sh ros2 topic echo /clock --once
```

ROS package **`microduck_workshop_ros`**, executable **`gateway`**. `scripts/ros_cli.sh` sources the container workspace before running a ROS CLI command.

`bounded_motion`, `motion_status`, `observe`, and `emergency_stop` are namespaced at `/workshop/microduck`. Three custom services exactly implement the frozen schema. `/clock` carries actual Lab simulation time. IMU orientation is unavailable, signaled by covariance[0]=-1; no invented quaternion/GT orientation is published. Camera and CameraInfo share the original frame stamp and frame ID.

The gateway claims one lease at startup and renews it on its own wall-clock thread, independently of model inference and DDS callbacks. Commands are finite/bounded, episode/generation checked, one outstanding request, no automatic HTTP retry. Unknown delivery disarms the gateway. A separate stop callback/HTTP connection can overtake a blocked command; late ACKs are superseded. A stop never auto-resets/re-arms. If the simulator was absent at startup, start it and explicitly restart the gateway; a background reconnect must not silently reacquire command authority.

The local observer correlates detector headers to original camera capture records. Freshness is original monotonic capture age, **not detection receipt time**. Wrong frame, unknown stamp/epoch, rewind and stopped camera expire or clear evidence. Only tag IDs and public command/observation fields reach the model, not lease tokens, detector poses or simulator world state. An ACK never implies a physically verified result.

## CUDA AprilTag smoke (independent of MicroDuck)

`bash scripts/ros_download_bag.sh` fetches the official NGC **5.0.0** AprilTag quickstart bag. Download is separate from image builds. Its recorded SHA-256 is checked before extraction. The test starts the actual `nvidia::isaac_ros::apriltag::AprilTagNode` with `backends=CUDA`, `tag_family=tag36h11`, and explicit tag edge size. It consumes actual bag image + camera-info messages and requires actual detections with matching headers; a detection publisher is never used.

The bag gate is **only** DDS/CUDA/image-compatibility evidence. It does not validate live onboard rendering, MicroDuck gait, or the capstone. Its post-playback check requires freshness loss after input stops. A separate live-camera integration is still required.

## Isolation and limitations

- `network_mode: host` is needed for the loopback simulation HTTP boundary. DDS discovery is `LOCALHOST`, domain 27 by default; use a different domain per independent host only if required.
- No robot hardware devices, privileged mode, host IPC, Docker socket, reset endpoint or public command/LLM port is exposed.
- Same host/kernel monotonic clock is required across Sim and gateway containers. This is not a remote-machine timestamp protocol.
- Public DDS topics are not a security boundary against malicious local users. This workshop assumes a trusted, single-user instance; do not bridge its DDS domain to a robot or public network.
- Physical marker size is a **teaching-scene parameter**, not hardware calibration. Set `tag_size` to the authored scene's black-border edge length. Default 0.22 m matches the official smoke launch; live scene authors must confirm it.

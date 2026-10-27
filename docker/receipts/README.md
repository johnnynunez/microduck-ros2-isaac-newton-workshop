# Local ROS 5 verification receipts

Directory: [`local-rtxpro-2026-10-27`](local-rtxpro-2026-10-27/).

These are actual **local RTX PRO 6000 Blackwell** results, not Brev or L40S results. No paid instance or physical robot was used.

| Gate | Actual result | Receipt |
| --- | --- | --- |
| Official CUDA AprilTag + NGC image bag | PASS: 49 image callbacks, 149 CameraInfo callbacks, 37 detector messages; 34 nonempty image-header-matched detections, IDs 0/2; stale after input stops | `apriltag-receipt.json`, `apriltag-detector.log`, `apriltag-player.log` |
| Real cross-process DDS | PASS: Observe, BoundedMotion, MotionStatus, Trigger; absent-simulator refusal and clean SIGTERM | `ros-tests-complete.log` |
| ROS workspace build | PASS: two packages, `microduck_workshop_interfaces`, `microduck_workshop_ros` | `ros-tests-complete.log`, `production-image-smoke.log` |
| Copied production image (no source bind mount) | PASS: actual package executable, Observe reply, detector parameters CUDA/tag36h11, Python and ROS import, bootstrap checksums | `production-image-smoke.log`, `runtime-container.log` |
| Resource isolation | Verified Memory=25769803776 bytes, NanoCpus=8000000000, device_ids=["1"], privileged=false | `runtime-hostconfig.json` |
| Host CPU tests | 30 passed, 2 skipped (ROS-only modules) | `cpu-pinned-final.txt` |
| Container ROS/unit tests | 14 passed; includes explicitly labeled message fixtures, which are **not** real-sensor evidence | `ros-tests-complete.log` |
| Package provenance | Full installed package versions and bootstrap download hashes | `dpkg-lock.tsv`, `bootstrap-sha256.txt` |

Runtime image `roscon/microduck-ros5:local` ID:
`sha256:8e7abff790a1d656dae0aa780068580effb560cbf0f9dd3b8eac618d6440f886`.
Base image `roscon/ros5-base:5.0` ID:
`sha256:84e8a8b0c1842710145bf30c7867bedaa54e7387529690861bdfe9c03fcd647e`.
These are **local image IDs**, not public registry pull references. The images were built with the bounded installer/copy/colcon/commit scripts. Equivalent Dockerfiles are supplied; a separate `docker build` execution is not claimed.

Observed key versions: Ubuntu 24.04, Python 3.12.3, `ros-lyrical-isaac-ros-apriltag=5.0.0-0noble.20260918011121000`, `rclpy=10.0.10-1noble.20260818.110638`, CUDA cudart 13.2.86-1, host driver 615.71.10.

The image bag is the official NGC `isaac_ros_apriltag_assets/5.0.0/quickstart.tar.gz`; SHA-256 `cadc33601d769ef63a792577105d2cee4f1759b0583f5bf9627275812ae77885`. Its raw images are real inputs to NVIDIA's CUDA node. No detections are fabricated or directly published by the test. Sensor-data QoS is best-effort; callback counts are measured counts, not an assertion that every bag frame was received.

## Scope limits

- Live Lab/Newton MicroDuck encoder/IMU/clock/camera delivery and policy motion remain a **separate integration gate**. An official-bag pass is not a capstone pass.
- The cross-process DDS test intentionally has no simulator, and verifies refusal rather than inventing successful motion. CPU fixtures test safety and conversions only.
- `runtime-container.log` and `apriltag-detector.log` include normal launch shutdown messages, including upstream's component-container SIGINT exit. The supervising scripts and assertions completed successfully.
- Original RED logs are retained unchanged in the local evidence archive. Public copies with local filesystem prefixes are explicitly labeled as sanitized; [the redaction manifest](redaction-manifest.json) binds original and published hashes. Numerical results, failure status and traceback whitespace are not edited to make checks appear green.
- Apt minor sources and Ubuntu base digest are pinned; exact dependency versions are recorded, not guaranteed available forever. For byte-identical classroom rollout, preserve/publish the tested OCI image by digest. Do not call a later floating apt rebuild identical.

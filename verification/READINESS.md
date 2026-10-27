# Integration readiness

This is an evolving implementation, not an all-green classroom release.

- Public assets:121 files independently downloaded and verified by the recorded SHA-256 and size.
- Native stack: real Isaac Sim6.2.0.0 / Lab3.0 / Newton1.6.1 reset, sensors, BAM/backlash and fresh PPO were exercised on local RTX PRO. A short PPO update is not a converged gait.
- ROS5: actual CUDA AprilTag processed the official image bag; live MicroDuck camera-to-ROS acceptance is separate.
- CASCADE: real local Qwen3.8 tool calls were captured. The real ROS absent-simulator diagnostic failed closed but exhausted its step budget; it is not robot-task success.
- Locomotion: direct low-speed commands stall. The first explicit calibrated velocity profile moved but failed ALL unchanged rest gates; it is NOT READY and refuses forward motion.
- A distinct planned step-and-settle primitive is under validation. Original rest thresholds and failed results are not being relabeled.
- Cross-layer review identified ROS float serialization, task-objective and queued-freshness issues; fixes and real combined acceptance remain in progress.
- Full Brev bootstrap, portable L40S model route and read-only preview are still being integrated. No paid instance, Brev deployment or L40S hardware run has been claimed.

See [runtime](../docs/runtime.md), [calibration failures](../docs/calibration.md), [ROS evidence](../docker/receipts/README.md), and [model diagnostics](../solutions/capstone/evidence/README.md). CPU CI does not certify these live gates.

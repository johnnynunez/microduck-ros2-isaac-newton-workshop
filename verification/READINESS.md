# Integration readiness

**The combined classroom release is not yet approved.** Component success is recorded separately from the integrated robot task.

## Verified components

- **Assets:** all 121 public files were independently downloaded and verified by exact SHA-256 and size.
- **Native physics and training:** Isaac Sim 6.2.0.0, Lab 3.0 GA source and Newton 1.6.1 exercised reset, native sensors, BAM/backlash and fresh PPO on local RTX PRO. A short PPO update is not a converged walking policy.
- **New fixed maneuver:** `step-forward-v1` passed six preregistered native step/resume requests plus two fresh confirmation requests. The parent independently checked every raw artifact hash and all eight positive verdicts, plus 12 intentionally interrupted/unverified probes. These tests did **not** enable cameras or ROS; see [the immutable campaign](../provenance/step_validation.json).
- **Perception:** real CUDA Isaac ROS 5 AprilTag processed the official bag and the actual rendered MicroDuck head camera. The integrated preflight produced same-episode GO with an original-capture age of 0.121 seconds, not a synthetic detection.
- **Model:** the pinned public Qwen3.8 GGUF and CUDA llama.cpp build executed genuine CASCADE tool calls. The compiled library contains SM 89 and SM 120a code; this does not establish L40S hardware execution.
- **Deployment:** the merged Sim, ROS and agent images were rebuilt successfully. The read-only preview and private shared ROS/agent IPC path were exercised locally. The parent CPU suite passed 392 tests with 15 explicitly skipped optional/live checks.

## Remaining integrated gates

The first joined portable-model game safely refused motion after its observation became unavailable/stale. The preceding real ROS preflight was fresh, so rendering/model/perception latency needs diagnosis; no limit is being widened and no successful step is claimed for that run.

Independent review also reproduced a transient STOP-event loss, possible cross-request contamination of a verification tail, and incomplete cancellation of malformed authenticated renewal proofs. Fixes and new regression/live checks are in progress. These findings do not relabel the isolated native campaign, but they block classroom acceptance of the joined path.

The original direct low-speed commands stall. The older constant-velocity calibration failed all 12 unchanged rest gates and remains **NOT READY**. The new planned maneuver is a different skill, not a new verdict for those failed commands.

## Explicit exclusions

No paid Brev VM was provisioned; no L40S hardware, Brev Secure Link, cold network bootstrap or complete fleet deployment is claimed. Local runtime builds used a private copied package cache after a real download timeout. Rendering warmup caches may be reused; asset and model hashes remain enforced.

See [runtime](../docs/runtime.md), [step](../docs/step.md), [calibration failures](../docs/calibration.md), [ROS evidence](../docker/receipts/README.md), [local model](../docs/local_model.md), and [Brev](../docs/brev.md). CPU CI is not a substitute for the integrated physical and safety gates.

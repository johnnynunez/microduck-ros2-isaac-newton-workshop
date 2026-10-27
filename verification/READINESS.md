# Release readiness

**Two short uninstrumented full-pipeline GO episodes and a real STOP refusal now pass. Sustained classroom availability remains blocked.** The notebook-first student-policy route is being implemented separately; these runs use the existing pretrained policy, not a newly trained student checkpoint.

## Verified

- Public assets: 121 exact size/SHA-256 admissions; code/mesh/model licensing remains separate.
- Isaac Sim 6.2.0.0, Isaac Lab 3.0 GA source and Newton 1.6.1 run the actual robot with native BAM/backlash, IMU/encoders and rendered cameras. No PhysX physics fallback.
- [Fresh PPO](fresh-ppo.json): 512 native physics steps, four updates, 16 optimizer steps, changed weights and both checkpoint hashes independently checked. This is not a converged gait or resumed ONNX training.
- Native fixed-step campaigns and later protocol confirmations passed their original motion/rest gates. Historical receipts remain immutable and new source revisions have separate receipts.
- Actual camera images reach CUDA Isaac ROS 5 AprilTag and real ROS services. The 320×240 authored head render product fixes the measured large-image delivery loss without incompatible intrinsics or restamped pixels.
- The pinned public Qwen3.8 GGUF executes genuine CASCADE tool calls locally. One complete **observation-instrumented** camera → ROS → model → fixed step → native verdict → agent-success episode passed.
- Safety repairs cover transient STOP retention, proof-renewer wakeup, native verifier-tail admission, authenticated malformed-renewal cancellation and exact task/request-bound late-verdict reconciliation. Final parent CPU run: **486 passed, 19 optional/live checks skipped**. Those skips are not runtime evidence.

## New ordinary GPU0 campaign

The [parent-audited receipt](production-gpu0.json) records two real camera → CUDA Isaac ROS → local Qwen/CASCADE → ROS → Newton episodes with both agent success and exact request-bound physical verification. The parent recomputed both native verdicts and metrics from the real traces, checked the request/episode/generation bindings, and independently matched 120 installed-source entries per episode against current source. A separate fresh STOP episode refused motion and kept all 119 recorded command vectors exactly zero. The earlier two launcher bind-preflight failures are retained; they did not create robot episodes.

This is a successful small repetition, not proof of sustained availability. The isolated campaign omitted the browser preview because its current upstream port restriction would cross the test boundary. It changes no physics, control thresholds or policy, and adds no timing instrumentation in the runtime loop.

## Remaining blocker

Earlier ordinary attempts expired or refused stale input. A later instrumented idle-exposure run identified a 0.807-second gap in progress across the ROS gateway Python threads: native physics and camera production continued, but lease renewal missed the unchanged 0.5-second deadline. Native correctly expired the lease; the later renewal received HTTP 409 and the gateway latched STOP. The precise blocking operation in the ROS process is still being isolated. The successful short GPU0 runs do not erase this counterexample.

The successful diagnostic is real, but does not erase failed repetitions or establish reliable classroom availability. The fixed 0.5-second original-capture and actuator-lease budgets, two-simulation-second maneuver, unchanged physical evaluator and no-retry/stop rules remain enforced. See [scene/read-only wait decisions](../docs/integration_decisions.md), [camera measurements](../docs/camera_latency.md), [native fences](../docs/native_fences.md) and [case evidence](integrated-cases.json).

The motion lab requires a fresh successful staff rehearsal on the selected instance. Until that gate is met, use the documented CPU exercise and explicitly no-motion observation route; do not substitute a fixture/replay for live acceptance.

## Hardware and deployment limits

All live results are local RTX PRO, not a paid Brev deployment or L40S hardware run. The model binary contains SM 89 and SM 120a code; that is not hardware validation. Base container installation used a copied private package cache after a genuine cold-download timeout. Model downloads/builds, warmup, explicit NVIDIA/mesh-license acknowledgments and cloud cleanup are documented in [Brev preparation](../docs/brev.md).

The older direct/calibrated velocity requests remain failed / NOT READY. A distinct planned step is not a relabeling of those failures. No private assets, weights, credentials, world-truth control or physical-robot actions are included.

## Last pre-08:30 checks

A normal production episode completed the step and passed its independent physical verifier (0.0929714 m forward displacement, 0.000813365 m/s rest-tail speed), but the agent reported failure after querying before the asynchronous result became available. Explicit verification now waits read-only within its existing bound; this neither resends motion nor extends safety deadlines. The next normal attempt failed in the gateway/handler before dispatch and honestly returned false. **Reliable full-agent production acceptance is still blocked.**

A separate real STOP episode observed tag 1 at 0.10456-second conservative age, refused motion, issued no native motion request, and retained exact zero neural command conditioning throughout. That negative case passed; its agent task-success remains false by design. All cases and artifact hashes are retained in `integrated-cases.json`.

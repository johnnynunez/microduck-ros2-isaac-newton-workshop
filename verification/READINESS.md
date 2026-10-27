# Release readiness

**Notebook release candidate; full-course acceptance is BLOCKED at Notebook 04.** All six notebooks and the instructor guide are implemented. Actual01–03 execution passes locally. The latest full run stopped before PPO updates because its network-isolated training container could not retrieve the pinned SDK's ground asset;05–06 were not executed. No student-policy end-to-end success is claimed.

## Current notebook and policy gates

- [Configured01–03 rehearsal](notebook-rehearsal-01-03.json): the parent rechecked all three executed notebook hashes, every cell source hash, 18 sequential actual code executions without errors, and exact displayed JPEG bytes. That component run used explicit CDI/GPU1 and 24 GiB/6CPU ROS configuration; it is not default-resource or full-course acceptance.
- A subsequent immutable `034c10e` full-course attempt used the public resource defaults and the new explicit CDI configuration, again passed 01–03, then failed04 on `default_ground_plane.usda` retrieval. It executed 22 of 39 requested code cells: 21 passed, one failed, 17 were not executed. The session HOME cache did not preserve the separate container's temporary SDK asset mirror. This failed attempt remains private and unaltered; an asset/network preparation fix and a new rehearsal are required.
- Current student-policy R1–R4 repairs have independent review: 68 focused real CPU regressions, additional real socket/timing checks, all 38 v3 raw artifact hashes, all 12 native admission verdicts and exact ONNX replay were checked. See [v3 native evidence](../provenance/student_policy_v3/README.md). This is native-only, not the missing04→05→06 notebook/ROS/model acceptance.
- The first v3 HTTP resume genuinely failed the unchanged yaw gate; a separate confirmation passed. Both remain recorded. 51 inference rows are asynchronous substep-boundary evaluations, not an extra control period: phase durations remain 200 physics steps each. No timing, policy or evaluator change is justified by row counts alone; repeated-run robustness is not established.
- Public receipt copies are explicitly sanitized and nondeployable, with original/published hashes. Runtime loaders still require complete unredacted local training/admission bundles and reject modified bytes. No publication manifest bypass was added.

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

## Historical ROS stall and independently checked repair

Earlier ordinary attempts expired or refused stale input. An instrumented idle-exposure run identified a 0.807-second gap in ROS Python progress while native physics/camera continued. The subsequent causal investigation reproduced event-induced empty rclpy wait-set wakeups and GIL starvation. The explicit version/SHA-gated scheduling repair is documented in [executor fairness](executor-fairness.md).

The parent reran the [independent raw-evidence audit](executor-fairness-independent.json): all 721 files and sizes match, both canonical GO verdicts recompute exactly after 65 seconds idle, and STOP admits no motion. An ordinary stock-executor failure and a separate diagnostic failure remain negative. These bounded canonical results do not prove the new student-policy route or arbitrary-load availability. A contained external-context shutdown exception caveat is documented rather than presented as a generally semantics-preserving upstream patch.

The successful diagnostic is real, but does not erase failed repetitions or establish reliable classroom availability. The fixed 0.5-second original-capture and actuator-lease budgets, two-simulation-second maneuver, unchanged physical evaluator and no-retry/stop rules remain enforced. See [scene/read-only wait decisions](../docs/integration_decisions.md), [camera measurements](../docs/camera_latency.md), [native fences](../docs/native_fences.md) and [case evidence](integrated-cases.json).

The motion lab requires a fresh successful staff rehearsal on the selected instance. Until that gate is met, use the documented CPU exercise and explicitly no-motion observation route; do not substitute a fixture/replay for live acceptance.

## Hardware and deployment limits

All live results are local RTX PRO, not a paid Brev deployment or L40S hardware run. The model binary contains SM 89 and SM 120a code; that is not hardware validation. Base container installation used a copied private package cache after a genuine cold-download timeout. Model downloads/builds, warmup, explicit NVIDIA/mesh-license acknowledgments and cloud cleanup are documented in [Brev preparation](../docs/brev.md).

The older direct/calibrated velocity requests remain failed / NOT READY. A distinct planned step is not a relabeling of those failures. No private assets, weights, credentials, world-truth control or physical-robot actions are included.

## Last pre-08:30 checks

A normal production episode completed the step and passed its independent physical verifier (0.0929714 m forward displacement, 0.000813365 m/s rest-tail speed), but the agent reported failure after querying before the asynchronous result became available. Explicit verification now waits read-only within its existing bound; this neither resends motion nor extends safety deadlines. The next normal attempt failed in the gateway/handler before dispatch and honestly returned false. **Reliable full-agent production acceptance is still blocked.**

A separate real STOP episode observed tag 1 at 0.10456-second conservative age, refused motion, issued no native motion request, and retained exact zero neural command conditioning throughout. That negative case passed; its agent task-success remains false by design. All cases and artifact hashes are retained in `integrated-cases.json`.

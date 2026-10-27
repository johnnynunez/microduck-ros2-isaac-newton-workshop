# Fixed step-and-settle: `step-forward-v1`

**Native physical validation passed: six preregistered step/resume requests,
plus two requests in a fresh non-gating production-admission confirmation.**
This is a distinct planned maneuver, not a repaired or renamed velocity API.
It does **not** establish ROS/perception/model-controlled acceptance; that requires
the separate real head-camera → Isaac ROS → CASCADE → StepForward run.

## Fixed semantics, unchanged mechanics

| Interval from first native consume | Requested peak | Actual neural command |
|---|---|---|
| `[0, 1.0)` simulation seconds: drive | `(.10, 0, 0)` | `(.25, 0, 0)` |
| `[1.0, 2.0)` simulation seconds: settle | `(.10, 0, 0)` | `(0, 0, 0)` |
| At 2.0 seconds: transaction complete | — | `(0, 0, 0)` |

The second second is **part of the requested maneuver horizon**, not an extension
of the verifier's rest window. The same learned VelStand policy balances with
exact zero conditioning under active gravity/contact; there is no pose freeze,
scripted joint trajectory, teleport or ground-truth controller. Timings use the
existing 0.005-second physics grid, with a 1e-9-second roundoff tolerance only for
this new primitive. Measured completed drive intervals were 1.0 seconds to
floating-point precision.

The public ONNX, 61D observation builder, training action mode, BAM/backlash,
friction, IMU estimator, native model and physics timing are unchanged. Binding
requires the pinned public v8 policy hash and `--policy-mode training`. Training
here means the existing unfiltered inference action mode, not online learning.
The neural `.25` is within training bounds but outside the old direct `.10`
command envelope; it is disclosed conditioning, **not raw `.10` speed tracking**.

`/v1/command` and `--command-profile direct|calibrated-forward-v1` retain their
old semantics. Direct conditioning remains identity for the entire requested
duration. `calibrated-forward-v1` remains **NOT_READY**, rejecting every nonzero
request. All previous failed artifacts and verdicts are preserved. The one
stricter shared admission change is `MIN_DURATION_S=0.02`: ordinary commands
shorter than one 50 Hz control period, including `.005`, are rejected rather than
inventing an evaluator sample. This does not alter any physical threshold.

## Explicit launch and wire contract

```bash
python -m microduck_workshop.sim.play --asset-root .cache/assets \
  --mode serve --steps 0 --step-profile step-forward-v1 --cameras \
  --output artifacts/step-session
```

Use the clean pinned GA environment and approved memory/GPU wrapper. This flag
is **`--step-profile`**, not `--command-profile`; default step capability is
disabled. Health exposes `runtime.step_profile` alongside the unchanged
`runtime.command_profile`. Its status `NATIVE_VALIDATED` is deliberately not an
end-to-end autonomous acceptance claim. `--step-candidate-validation` is an
explicit offline-operator diagnostic flag, never a proof bypass.

New `POST /v1/step` accepts exactly the existing MotionCommand keys:

```json
{"episode_id":"CURRENT_EPISODE","request_id":"UNIQUE_ID","expected_generation":0,
 "vx":0.1,"vy":0.0,"wz":0.0,"duration_s":2.0}
```

Use the actual current generation. No alternative velocities, turn, duration,
clipping or extrapolation are admitted. The ROS service
`/workshop/microduck/step_forward` reuses BoundedMotion IDL and targets this route,
never `/v1/command`. The agent's fixed tool is `microduck.step_forward`.

All step requests require the actuator lease and these same-host headers:

- `X-Workshop-Lease`
- `X-Workshop-Observation-Episode`
- `X-Workshop-Observation-Sequence` (uint64)
- `X-Workshop-Observation-Deadline` (finite monotonic original capture + 0.5 s)

The ROS owner must establish fresh same-episode GO and no STOP from the original
image capture, both at admission and on each renewal. Do not derive a deadline
from HTTP receipt time. The native owner checks the proof on admission, on
renewal, and before every native consume (including physics-substep preemption).
It rejects stale, cross-episode or more-than-0.5-seconds-future deadlines. During
an active step, `/v1/renew` carries fresh proof in the same headers. A repeated
sequence may retain its exact original deadline while still fresh; it may not
rewrite that deadline. Decreasing sequences/deadlines are rejected. Missing or
invalid proof on an owner renewal cancels the step; proof expiry invalidates the
owner lease. Renewing an actuator lease cannot revive an expired proof or queued
motion. Priority stop still latches and cancels independently.

The headers are a trusted local ROS-owner assertion, not a cryptographic GO
certificate; the native service does not run a second pixel detector. A raw
operator HTTP diagnostic is not autonomous perception acceptance.

Replies retain the existing allowlist: accepted/completed/verified are distinct.
No world pose, GT metric, lease or observation deadline is added to command/status
replies. Private neural traces record request ID, drive/settle phase, requested
peak, phase desired command, actual neural command, source/profile hashes and
observation proof. Full observations/actions/targets remain recorded. Evaluator
truth stays in separate evaluator-only files.

## Fresh evidence and limits

Preregistration: [`step_preregistration.json`](../provenance/step_preregistration.json),
SHA-256 `48698a7b30275ec5377a8052d0956729b453f9b5b6fad75030cacd0690d2cc52`.
Portable receipts and raw artifact hashes:
[`step_validation.json`](../provenance/step_validation.json).

Three fresh native episodes used initial/between-step zero waits of
**0.4, 0.8 and 1.4 seconds**. Each ran step → fixed zero wait → step without a
reset. All six completed requests passed the original verifier. The whole
`sim/evaluate.py` remained byte-identical, including the original 0.35-second
post-completion wait, final 0.2-second rest tail, planar speed `<0.04 m/s`, yaw
rate `<0.10 rad/s`, displacement, yaw, duration, finite-pose, height and upright
checks. The unchanged sample grid produced verdict traces about 2.36 seconds long.

| Metric across six gating requests | Measured range |
|---|---:|
| Initial-body-forward displacement | 0.081780–0.092071 m |
| Verifier rest-tail planar speed | 0.000526–0.001080 m/s |
| Verifier rest-tail absolute yaw rate | 0.006999–0.028275 rad/s |

Only the readiness string changed after these gates. A separate fresh confirmation
then used **production admission without the candidate flag**, initial zero 1.3 s
and between-step zero 1.1 s. Both requests passed: displacements 0.090110 and
0.091559 m; rest-tail planar speeds 0.001374 and 0.001202 m/s; yaw rates 0.023468
and 0.033057 rad/s. This confirmation was not used to select timing or thresholds.

Each episode also exercised live proof expiry, independent actuator lease expiry,
and priority stop during drive. These interrupted requests correctly remained
unverified; expiry invalidated old tokens and exact neural zero replaced drive.
Second-owner claims were refused. All renewal error lists were empty. Native
models reported 15 bodies and 28 hinge coordinates. SIGTERM drained and shut down
all four native servers cleanly.

These **operator-native** diagnostic proofs use original native sensor capture
+0.5 s, not a fabricated ROS GO/image detection. Only the parent integration run
can supply real camera-derived ROS proof. No cloud, physical-robot, long-duration
soak, or autonomous capstone result is claimed here.

Reproduce a preregistered case in a fresh output directory (the script refuses an
occupied port and does not overwrite a case):

```bash
python scripts/sim_validate_step.py --asset-root .cache/assets \
  --plan provenance/step_preregistration.json --case confirmation-w11 \
  --production-admission --output artifacts/step-recheck
```

Run native commands under `heavyrun`, set per-command `OMNI_KIT_ACCEPT_EULA=YES`,
`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, and the correct worktree `PYTHONPATH`.
Do not change SDK dependencies, old failure receipts or evaluator thresholds.

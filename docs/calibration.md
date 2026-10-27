# Explicit forward calibration: NOT READY

**`calibrated-forward-v1` is an evaluated, rejected deployment candidate, not a
working capstone profile. There are no validated forward durations.** The final
HTTP service rejects every nonzero request in this profile. Zero remains exact
zero; `direct` remains the default, unchanged identity conditioning. Do not
advertise calibrated forward motion to the agent/controller.

## Why an adapter was investigated

The pinned public VelStand v8 ONNX receives physical-unit trunk commands in
observation indices `48:51`. The public velocity recipe samples vx `[-0.4, 0.4]`
m/s, vy `[-0.3, 0.3]` m/s and yaw `[-1, 1]` rad/s. Inspection of the pinned
training recipe, inherited command observation, and public Rust observation
builder found **no missing velocity-unit conversion**. The Rust legacy separate
standing-network switch uses magnitude `0.05`; without a separate stand network,
VelStand runs at every command, including zero. That switch does not explain the
observed `.10`/`.20` dead zone. This is a measured low-command behavior of this
policy/runtime, not proof of a universal neural dead-zone boundary.

Source links and SHA-256 receipts are in
[`provenance/command_calibration.json`](../provenance/command_calibration.json).
The checked public `microduck_rl` revision is
`b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`; the velocity/MDP source matches the
published training revision `3750776761ecfaa5671b36972087cafba45b8527`.
ONNX SHA-256 is
`2fc7f8ee6acd7d0d3f66a99927b5d5a56589aeed02ec714de329b252d5ccf492`.

The explicitly authorized offline candidate was a **discrete lookup**, not a
gain applied to arbitrary commands:

| External desired command | Actual neural conditioning |
|---|---|
| `(0, 0, 0)` | `(0, 0, 0)` exactly |
| `(+0.10, 0, 0)` | `(+0.25, 0, 0)` |
| Any other nonzero point | Rejected, never clipped or extrapolated |

The neural `.25` is inside the source training range, but outside the frozen
**direct** command envelope. It is not a raw-policy `.10` success. The final
profile additionally rejects the `.10` forward point because neither tested
duration passed all physical gates. Its pure conditioning function is retained
for bounded offline diagnostics, not public motion admission.

The binding requires the exact public ONNX and `--policy-mode training`
(unfiltered scale-one action mode). This action mode name does not imply online
training. The ONNX graph/normalizer, actual BAM/backlash, native actuators,
friction, gravity estimator, physics dt `0.005`, and decimation `4` are unchanged.
The mapping reads only the requested command: no world pose/velocity feedback,
distance goal, root teleport, scripted joints, or online fitting.

## Fresh preregistered evidence

Round 1 fixed the map before native execution. Preregistration hash:
`0533ea5270063683002011c70da149de8c2425f32f6d87725698b59dda48c49f`.

Six fresh native HTTP episodes covered zero waits **0.4, 0.8, 1.4 seconds ×
1- and 2-second requests**. Each continuously executed walk → automatic expiry →
zero wait → resume → expiry, with no intervening reset. A seventh, non-gating
confirmation used a fresh 1.3-second initial zero and 1.1-second between-request
zero. All used the real public network, native encoders/IMU and BAM. The
independent evaluator alone read world truth.

**All twelve gating walk/resume requests failed the unchanged per-request rest
gates. Both requests in the fresh confirmation also failed.** Forward travel and
uprightness were real; command ACK/completion was never counted as verification.

Ranges over the six gating requests at each duration:

| Request duration | Active forward travel (world X) | Active mean world-X speed | Verifier rest-tail planar speed | Verifier rest-tail yaw rate |
|---|---:|---:|---:|---:|
| 1 s | 0.076845–0.079171 m | 0.076463–0.078778 m/s | 0.044331–0.063468 m/s | 0.173870–0.268994 rad/s |
| 2 s | 0.189697–0.196001 m | 0.094612–0.097756 m/s | 0.068326–0.083772 m/s | 0.158025–0.248007 rad/s |

The original limits remain planar speed **<0.04 m/s** and yaw rate **<0.10 rad/s**,
evaluated using the original last-0.2-second window after the original
0.35-second completion settling wait. Longer client zero waits do not revise a
failed verdict. Original displacement, duration, yaw, finite-pose, height >0.07 m
and up-cosine >0.7 checks were also unchanged.

Measured neural-on durations were 1.005/2.005 seconds (the first existing
0.005-second substep satisfying the floating-point duration boundary). First
observed world-X speed >0.02 m/s occurred after 0.05–0.07 sim seconds. This is a
descriptive onset metric, **not a new acceptance threshold**. Verifier travel
includes settling and uses initial-body-forward projection, so it differs from
the active world-X table.

Each episode additionally exercised priority stop on real moving policy output.
The interrupted request correctly remained unverified; neural conditioning
returned to exact zero, stop was latched, and a second owner was refused. Later
post-stop tail speeds were 0.001551–0.003355 m/s. These later measurements do not
replace the failed early rest checks.

The separate original 7-second phase regression passed its unchanged
walk/2-second-zero/resume evaluator: walk 0.190053 m, resume 0.189160 m,
zero-tail speed 0.000683 m/s. **That long-rest phase pass does not establish HTTP
request acceptance.** Prior direct `.10`/`.20` failures and above-envelope `.25`
fit diagnostics remain in the receipt with their original FAIL/bounds flags;
fit data are not holdout evidence. No candidate or threshold was tuned after the
failed holdouts.

## API and trace changes

Opt in explicitly with `--command-profile calibrated-forward-v1`.
`/v1/health.runtime.command_profile` discloses the mapping, public source revision,
policy SHA, adapter-source SHA, profile SHA, `validation_status: NOT_READY`, and
`forward_durations_s: []`. Nonzero requests are refused before generation or
pending intent changes. Shared HTTP/ROS hard bounds are untouched.

Every actual policy call logs the full 61-dimensional observation, raw action,
target, external desired command, actual neural command, profile/source hashes,
and separate external/direct-neural/training-envelope flags. The actor and public
sensor API do not receive evaluator root truth. The public receipt contains only
aggregate measurements and hashes, no private machine paths or lease secrets.

Recheck the portable native results without simulation:

```bash
python scripts/sim_validate_calibration.py \
  --plan provenance/command_calibration.json \
  --summarize-existing --output artifacts/calibration-summary
# Expected exit 2: seven recorded cases, no physical calibration pass.
```

The final validator refuses a fresh forward campaign while the profile is
NOT_READY. Historical experimental reproduction is pinned to commit
`537e9f2` in the receipt; **do not deploy that historical admission state**.
A new candidate requires a new explicit decision and a new preregistered round,
not editing the failed receipts.

Bounded long-rest diagnostics remain available (do not call this HTTP success):

```bash
python -m microduck_workshop.sim.play --asset-root .cache/assets \
  --mode validate --steps 350 --validation-vx .1 \
  --command-profile calibrated-forward-v1 --output artifacts/calibration-phase
```

## Interactive serving and resources

`--mode serve --steps 0` explicitly runs until SIGINT/SIGTERM. Positive step
counts retain bounded test semantics; `--mode validate --steps 0` is rejected.
Serve continues balancing at zero when idle. A signal latches stop, drains
0.5 simulation seconds of zero intention, records its receipt, then closes HTTP
and Kit. It is not a physical emergency-stop guarantee and SIGKILL cannot drain.
Serve retains the existing wall-clock pacing; `--realtime` also paces bounded
validation without changing physics dt or motion.

For indefinite serving, each JSONL stream rotates at 32 MiB with two backups
(three files per stream); the in-memory phase summary retains at most 500 rows.
Complete motion verification is not downsampled. Request history is capped at
4096 records; exhaustion refuses new motion instead of evicting replay IDs.
Operator restart is then required. Use a fresh output directory per session;
copy evidence before rotation if it must be retained. Kit's own diagnostic logs
are separate from these bounded workshop telemetry streams.

Actual native checks exercised SIGTERM in seven moving episodes and SIGINT in a
final fail-closed admission/lease-expiry run. The final native server rejected
both 1s/2s forward commands, accepted zero, expired its unrenewed lease and
produced only zero neural command inputs. **This is not a two-hour endurance
claim.** No server is intentionally left running after validation.

Use the clean GA runtime and pinned public assets, accept the SDK EULA before
launch, cap BLAS/OMP threads, and launch heavy native jobs under the approved
memory/GPU wrapper. Do not modify SDK dependencies to resolve command behavior.
Local RTX PRO results are neither cloud-L40S acceptance nor physical-robot tests.

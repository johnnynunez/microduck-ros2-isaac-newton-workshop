# Additive step-forward-v1 transport contract

Protocol version remains **1**. This is a new planned maneuver, not a reinterpretation
of a failed bounded velocity trial. Historical direct/calibrated-forward failures stay
failed; no unchanged old request acquires new semantics or a promoted verdict.

## Brain → ROS → simulator

1. Real local Qwen3.8 / Nemotron 3.5 CASCADE brain calls `microduck.observe`.
2. On fresh GO without STOP, it may call `microduck.step_forward({})` or
   `microduck.step_forward({"action":"step_forward"})` once. Numeric choices are rejected.
3. The domain constructs the exact existing `MotionCommand` shape with a fresh UUID:
   `episode_id`, `request_id`, `expected_generation`, `vx=.10`, `vy=0`, `wz=0`,
   `duration_s=2.0`. The model sees neither lease tokens nor proof headers.
4. `/workshop/microduck/step_forward` uses the **existing**
   `microduck_workshop_interfaces/srv/BoundedMotion` IDL. The server validates the
   fixed body and independently checks its actual capture/detection cache.
5. The gateway sends `POST /v1/step`, never `/v1/command`, with that exact body.
   It adds `X-Workshop-Lease` and the proof below. Ordinary `/v1/command` and
   `/workshop/microduck/bounded_motion` retain their separate diagnostic scope.

Validated ROS motion `float64` fields are explicitly converted to Python `float`
just before constructing the generated request. Validation precedes coercion;
bools, strings and nonfinite values remain errors. IDs and generation are unchanged.
Actual generated CDR regressions are in `tests/test_ros_serialization.py` and run
inside the installed Lyrical image; host stand-ins cannot test this ABI.

## Source freshness, including queued delivery

The ROS server correlates actual Isaac ROS detection headers with the **original**
onboard image capture. Same episode, GO tag 0 present, STOP tag 1 absent, and capture
age below `.5 s` are mandatory at server admission. It forwards exactly:

| Header | Value |
|---|---|
| `X-Workshop-Observation-Episode` | Actual capture episode matching the request |
| `X-Workshop-Observation-Sequence` | Original nonnegative capture sequence, decimal |
| `X-Workshop-Observation-Deadline` | Original capture monotonic timestamp + `.5 s` |

These are same-host monotonic clocks; they are **not wall-clock/Unix timestamps**.
Do not stamp receipt-now onto a queued image or refresh an old frame by rereading it.
The client pre-send deadline is an extra guard, not the admission authority.

The simulation step owner must reject nonfinite/future-over-budget/expired proofs,
wrong episodes, and invalid or regressing sequences. It checks the deadline both on
HTTP admission and immediately before first/every native consume. A queued request
that expires cannot start motion. This native fence belongs to the simulation worker;
ROS-only tests cannot prove it is installed in the running simulator.

While the step is pending/active, `/v1/renew` carries the same headers from a current
server-side GO proof. A duplicate frame retains its original deadline. Missing,
stale, foreign or STOP detections disable authority and issue priority stop; native
proof expiry must independently zero the intent if HTTP stop cannot arrive. A later
GO never revives an expired/stopped owner. The gateway does not auto-claim/re-arm.
After an exact terminal status is received, ordinary idle lease renewal may resume;
that is not permission for a second command without another valid admission.

## Fixed maneuver and unchanged verification

The new profile requests peak `.10 m/s` forward and total horizon `2.0 s`:

- First `1.0 sim s`: existing network conditioned at `.25` forward.
- Second `1.0 sim s`: exactly zero network command, with the learned balance policy,
  gravity and contacts still active (not frozen poses or torque-off).
- Independent native rest verification uses its **original** horizon + `.35 s`
  window and `.04 m/s` planar / `.10 rad/s` yaw rest bounds. No threshold changes.

Trace requested peak, actual network command and active/zero phases separately.
The independent forward-step objective is not chosen by the brain's numeric command:
verified legacy standstill, tiny displacement or turn cannot complete it. An ACK,
completed intent, synthetic fixture, or `task_done(true)` cannot stand in for the
same-request independent physical verdict. Failed and pending evidence stay so.

## Validation scope

CPU tests cover stationary false-success, server scheduling delay (`.46 + .06 s`),
proof headers, renewal freshness, stop/absence/foreign signals, exact IDL serialization,
and the real CASCADE domain/runtime. Network-disabled real DDS tests exercise service
registration and absent-simulator refusal, **not** physical motion or live perception.
Full acceptance still needs the actual onboard camera → Isaac ROS 5 → local CASCADE
brain → ROS step → ONNX/Newton episode, native deadline enforcement, unchanged native
motion/rest verdicts and a ground-truth/secret-free provider transcript.

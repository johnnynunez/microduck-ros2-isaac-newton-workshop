# Native verification and renewal fences

## Admission remains closed through independent verification

`completed=true` ends the requested actuation, not the evaluator's collection.
Both `/v1/step` and legacy `/v1/command` reject new admission while any accepted
request lacks `verification_available=true`. This check is under the same owner
lock as submission and the private verdict callback. Reclaiming an expired lease
cannot bypass it; rejected requests consume neither an ID nor a generation.

The evaluator's actual callback releases the fence, for either a passing or a
failing verdict. No wall timer substitutes for it. Renewal and priority stop
remain available. A stalled or absent evaluator therefore fails closed; if a
queued request was cancelled before any evaluator tick and never receives a
verdict, an operator must restart the episode rather than bypass the fence.

`sim/evaluate.py` remains byte-identical:
`04d83c178af0465ad57d7551e32e0ec292f42bdcbb0ef645d4cf0ed94c83c037`.
There is no change to any displacement, duration, height, upright, yaw, freshness
or rest threshold, policy input, command conditioning, actuator or physics setting.

## Malformed renewal revokes only its authenticated active step

Lexical proof failures (partial headers, invalid sequence or nonnumeric deadline)
now reach an owner-locked rejection path. It checks the request episode and
current lease token before cancelling a queued/executing step and invalidating
that token. A later well-formed renewal cannot revive it. Missing or semantically
invalid proofs retain the existing cancellation path.

Wrong/missing tokens and wrong episodes cannot cancel somebody else's step.
Malformed new-step admission is not renewal and does not cancel an existing step.
Legacy commands do not acquire step-proof requirements; malformed renewal headers
are rejected without extending or revoking a legacy lease.

## Separate fresh native confirmation

[`native_fence_validation.json`](../provenance/native_fence_validation.json)
records one fresh production-admission episode on pinned GA Isaac Lab/Newton,
physical GPU 0, private port 18770, no cameras. Initial zero was 1.3 simulation
seconds; the fixed inter-step zero wait was 1.1 seconds. Neither wait was selected
from GT or observed metrics. Native sensor original-capture timestamps supplied
the diagnostic proof; this is **not ROS GO/perception/model acceptance**.

- Both step and resume passed the unchanged independent per-request verifier.
- Legacy and step submissions were each rejected during both verification tails
  (four real HTTP 409 receipts); they never actuated.
- Wrong-token malformed renewals were rejected during both drives without
  cancelling them.
- A correctly authenticated partial renewal cancelled a third active step;
  a subsequent valid renewal was rejected, and its physical verdict stayed false.
- Sixty recorded neural rows after cancellation were exactly zero-conditioned.
  The learned policy still balanced under the unchanged physics.
- No renewal-worker errors; native process and 32G-capped unit exited successfully.
  Peak unit memory was 2.8G. The private server was verified closed afterwards.

| Request | Forward displacement (m) | Rest-tail speed (m/s) | Rest-tail yaw rate (rad/s) |
|---|---:|---:|---:|
| step | 0.090486417 | 0.001261502 | 0.024893219 |
| resume | 0.092907472 | 0.000501555 | 0.007604436 |

The generic `evaluation.json` transport-only phase summary has
`walk_stop_resume_verified=false` because serve mode does not label its trace as
`walk/zero/resume`. The physical evidence above is the unchanged **per-request**
`evaluator_verdicts.jsonl`, not that generic summary or a control ACK.

The portable receipt binds the exact evaluated source hashes and raw artifact
hashes. The local launch harness, plan, logs and raw traces are retained under
`.workshop/native-fences/`. Its only launcher adaptation was binding `play.serve`
to port 18770; the simulator/evaluator loops were not replaced.

## Regression and integration notes

`tests/test_sim_native_fences.py` reproduces both gaps using real owner, evaluator
and loopback HTTP components with explicit CPU fixtures. R2 was five failing
cases plus a passing priority-stop control before the fix. R3 was ten lexical
cancellation failures plus 25 passing missing-proof/semantic/unauthenticated
controls before the fix. All new behavioral cases then passed. These fixture
trajectories are not physical receipts.

The original review's attribution probe injects its extra displacement even when
the second command is rejected. Its unconditional synthetic trajectory therefore
cannot test a prevention fence by asserting only the final verdict. The new test
asserts rejection on every tail tick, unchanged generation and zero consumed
intent, retains the original 0.049m failing trajectory, and exercises resume after
the real verdict callback. The original review files remain untouched.

Historical `step_preregistration.json` and `step_validation.json` remain untouched:
the six gating and two confirmation passes, and the twelve failed velocity
receipts, are not rewritten as evidence of these new sources. Current protocol
source checks use the separate native-fence receipt while retaining the original
historical hashes. Owner-only CPU lifecycle fixtures explicitly close their
private verdict interval with a **false fixture verdict** before another request;
production admission never bypasses the real evaluator to accommodate a test.

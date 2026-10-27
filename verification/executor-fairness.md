# rclpy empty-ready executor fairness

## Scope

This is a narrow, explicit **build-time patch to rclpy 10.0.10**, not a change to robot policy, physics, observation timestamps, lease logic or evaluator thresholds. The ROS image build rejects any unreviewed package version or executor source SHA. No runtime monkey-patch is installed. The private validation image is based on the already-integrated application image with only this executor change.

## Causal finding

The real-rclpy regression publishes a real DDS sample and uses `Executor._make_handler()` to put that subscription into its ordinary queued-handler state. Its `_executor_event` excludes the subscription itself from the next wait set. Its default QoS event handles are still eligible before the queued worker begins executing.

In [rmw_fastrtps 9.4.9 `rmw_wait.cpp`](https://github.com/ros2/rmw_fastrtps/blob/9.4.9/rmw_fastrtps_shared_cpp/src/rmw_wait.cpp), `has_triggered_condition()` checks an event listener's **broad status condition**, permitting `skip_wait`, before the later event-specific status-mask filter. Unread subscription data can therefore wake the wait through its event handles, while the subsequent readiness lists—including the QoS event indices—are all empty. The executor loops without dispatching a handler, so its existing post-handler GIL cooperation is never reached. The native wait's short GIL release alone does not provide adequate fairness here.

The paired diagnostic changes only `SubscriptionEventCallbacks(use_default_callbacks=False)`: that removes the empty wakes while retaining the same sample, publisher, subscription and queued handler. This is a **causal control, not a production fix**. Production QoS event handling remains enabled.

This closes the event-readiness gap in the earlier ros-availability stall investigation (separate handoff commit `1c1c8b99f48a3e980984348125d33f05b7872e8b`), whose publication/conversion hypothesis was already falsified. No asynchronous DDS publication change is made.

## Red → rejected alternative → green

Test environment: CPython 3.12.3, Linux SCHED_OTHER (`scheduler=0`), unchanged interpreter switch interval 0.005 s, real `rmw_fastrtps_cpp`, isolated CPU-only DDS namespace. The regression's renewal period is 50 ms and its maximum-gap gate is 100 ms—stricter than, and separate from, the unchanged 500 ms production lease.

| Execution | Actual outcome |
|---|---|
| Stock, actual default subscription events, three repeated trials | 94,868 / 102,251 / 106,946 completely empty native waits in three-second exposures; maximum renewal gaps 0.775017 / 0.424011 / 0.357997 s; all fail |
| Stock, default subscription events disabled only in the causal control | No completely empty native waits; controls pass |
| Candidate using only `os.sched_yield()` in the no-work loop | Rejected: native guard-wakeup regression reaches 0.987045 s renewal gap |
| Final zero-duration OS wait, repeated real-DDS and native-guard tests | Renewal maxima approximately 0.0503 s; three final batches each pass all eight focused patch/regression cases |

The correction adds only:

```python
# after readiness dispatch and timeout checks, before repeating the inner loop
if not yielded_work:
    time.sleep(0)
```

This is an empirically tested **zero-duration scheduling handoff**, not a guessed positive-duration sleep/backoff. It neither changes the timeout argument nor broadens any deadline. The AST regression removes this one conditional and requires the original executor function to be identical. Actual native guard wakeups, actual DDS matched-event delivery, retained sample identity, source/version drift refusal and double-patch refusal are tested.

## Runtime identity

| Item | Value |
|---|---|
| rclpy | `10.0.10-1noble.20260818.110638` |
| rmw_fastrtps_cpp | `9.4.9-1noble.20260818.093239` |
| Original executors.py SHA256 | `0830da415e9a63732b8a8bba734883110d04a4be7b21adcf232ac0567332a4a7` |
| Patched executors.py SHA256 | `516b88e7a011d679ce68d999e11ef12d9a78b10c86a402f7c13e20ba74105ffd` |
| Installer SHA256 | `54baa1f17131398cf465b16fed1e6fc330262d5db27a019f95fcf002641042a0` |
| Candidate ROS image | `sha256:6c2496ee77e9b2881e2906b6333698f03bd491f7d51282f971c735a9e7378e7f` |
| Unchanged simulation image | `sha256:8ead646545ba12976b9d9cbcc25b22bd9a5f55799cd5704ebbf8eb8a991724d9` |
| Unchanged agent image | `sha256:4adbea80b94fb92dbb3b046ec87facec6f43cf2e7c01a0235b3ee298e0b72e12` |

`docker/patch_rclpy_executor.py` emits `executor-fairness-receipt.json` beside the installed executor. Every normal candidate episode records the actual installed module hash and this build receipt. Application-source comparisons include **56 simulation entries, 36 ROS entries and 28 agent entries per completed episode, with zero mismatches**. Parent `:integrated` tags and old receipts are unchanged.

## Ordinary acceptance, not diagnostic-wrapper success

Each candidate episode is fresh, uses the ordinary ROS launch and CASCADE agent entry points, and waits at least **65 seconds idle before the model's GO/STOP decision**. No main-thread, callback, renewal or native tracing wrappers are loaded. The only native startup adaptation binds the existing `serve` function to private port18786; canonical BAM, `step-forward-v1`, physics and evaluator code remain byte-identical.

| Attempt | Episode | Request | Native / agent result |
|---|---|---|---|
| GO01 | `ep_5a6bfc34254c45dd8d3e1da26f3ed17b` | `5e38bef4b2524d418a3d6bf129426dff` | Native verified; agent true; 0.092391 m forward; tail speed0.000789 m/s, yaw rate0.004870 rad/s |
| GO02 | `ep_1c829b57a56d48b69c470b589bd53ffe` | `335b00429509442fb0d5e4df816d6eb2` | Native verified; agent true; 0.095367 m forward; tail speed0.000770 m/s, yaw rate0.010156 rad/s |
| STOP01 | `ep_3d83513497fa4c3d917ca19ab07f6de8` | None | Fresh STOP; no motion calls, no nonzero command rows, no positive native verdict; agent correctly reports objective failure |

GO02 initially reports completed/unverified and then receives its request-bound confirmation through the existing ordinary **read-only verify** path. The final ledger is confirmed. No motion retry, rearm, reclaim or proof restamping occurs. Local model provider is `qwen3.8-27b` on port18511; actual request/response traces are retained.

The fresh **ordinary, unwrapped stock baseline STOCK01** also fails after 65 s idle: episode `ep_5f1447f64f004b9ea419d71ae5cbbe44` sees fresh GO at generation1, rejects its sole motion attempt, emits no nonzero policy commands and has no native verdict. Its installed executor SHA is the original stock SHA, not the candidate. This post-candidate baseline repetition excludes diagnostic-wrapper overhead as a necessary cause; both failures remain retained.

The separate EVENTS01 diagnostic retains its failed agent report and 547,371 completely empty wait returns, including event readiness. Its longest recorded empty streak is1.157610 s /15,754 waits. It is diagnostic evidence, not an ordinary acceptance run or a new exact first-expiry timestamp trace.

The 0.5 s wall lease, 0.5 s original-capture deadline, native heartbeat gate, 2 s simulated maneuver, 0.35 s settle, 0.04 m/s tail-speed and0.10 rad/s tail-yaw-rate gates are unchanged. These observations establish the listed runs, not hard-real-time guarantees on arbitrary loads or kernels.

## Verification and reproduction

- Host complete CPU suite: **493 passed, 22 skipped**. Skips are not acceptance.
- Real ROS focused suite: **47 passed**, including actual DDS STOP overtaking an outstanding command acknowledgment and original proof-deadline checks.
- Three final repeated candidate batches: **8 passed each**; the stock causal test fails in all three repeated trials while its diagnostic control passes.
- Ruff and `git diff --check`: pass.

Run the causal tests in the ROS image, not an interpreter without rclpy:

```bash
docker run --rm --network none --memory 2g --cpus 2 \
  -e ROS_DOMAIN_ID=76 -v "$PWD:/repo:ro" -w /repo \
  <reviewed-ROS-image> python3 -m pytest -q -s \
  -p no:cacheprovider -p no:nose \
  tests/test_executor_dds_wake_ros.py tests/test_executor_fairness_ros.py \
  tests/test_executor_patch.py
```

The actual private candidate tag was `roscon/microduck-ros5:fair-candidate-01`. It is a local validation artifact, not a claim of publication. Main `docker/Dockerfile` and its ignore file explicitly integrate the same tested installer; an unreviewed rclpy payload makes that build fail closed.

A broad all-tests-in-ROS attempt is retained as failed: the suite includes host-only lazy-rclpy assumptions and a host Docker CLI check; the image's pytest7 nose plugin also mistakes an existing helper named `setup` for an xunit hook. The focused ROS command uses `-p no:nose`; no tests or acceptance thresholds were weakened to hide these environment mismatches. Initial harness API mistakes and a fresh host venv missing dependencies are retained separately.

## Isolation and evidence

### Independent review qualification

The [independent audit](executor-fairness-independent.json), also rerun by the parent, verified all 721 campaign entries and recomputed both canonical GO physical verdicts from raw traces with request/episode/source bindings. It preserved both negative baselines and the STOP refusal. This does not approve the new student policy or the entire notebook sequence.

The review also reproduced a shutdown caveat: external context shutdown during the new scheduling handoff raised `RCLError` in 27/30 candidate trials versus 0/30 exact-stock trials. The unchanged workshop gateway already contains this only when `rclpy.ok()` is false; healthy-context exceptions are not suppressed. The workshop retains that narrow, documented behavior, not an unqualified claim that every upstream shutdown exception is unchanged. Normal shutdown, dispatch, timeout and STOP-boundary checks passed. The middleware package is `rmw_fastrtps_cpp 9.4.9`; the underlying Fast DDS package is 3.6.2.

Validation uses GPU1, port18786, domain76, private ROS/agent IPC, and roscon-fair-* containers. Limits: Docker32/24/4GiB and8/8/2CPUs, one4GiB heavyrun launcher. Heavy slice remains170GiB. The existing model server is not restarted. Optional fixed-port preview is omitted explicitly rather than reading the other worker's GPU0/8766 lane.

The source-bound machine receipt is [executor-fairness.json](executor-fairness.json). Raw evidence remains under the executor-fairness worktree's `.workshop/`: per-run source/container/image identities, screenshots and capture headers, provider reports, native traces/verdicts, pre/post-stop logs, test logs (including failures), audit script and artifact manifest. Prior investigation/production receipts remain immutable.

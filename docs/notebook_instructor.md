# Notebook-first instructor speaking and facilitation guide

**Status: a complete supervised local reference rehearsal passed.** All six notebooks and 39 code cells executed with a fresh trained actor through exact-policy admission, inference and a real CASCADE/ROS maneuver; the parent independently recomputed its physical verdict. [Full evidence and limits](../verification/notebook-course-final.json). This remains **NOT READY for unattended live motion**. Each classroom instance and newly trained policy requires instructor approval. Brev/L40S execution is **cloud-unverified** unless rehearsed on that actual instance; this local reference pass is not student authorship, convergence or repeated-run robustness.

This guide accompanies six executable notebooks. It does **not** replace or rewrite your opening slides. The older `docs/labs/` remain technical references; their order and pretrained-policy handover are not the new primary teaching route.

## The two-hour clock

27 October 2026, 15:00–17:00 Europe/Madrid. Setup, downloads, shader warmup and acceptance rehearsal happen before this clock.

| Time | Minutes | Deliverable |
|---|---:|---|
| 15:00–15:15 | 15 | Your existing introduction slides |
| 15:15–15:30 | 15 | 01 ROS 2 |
| 15:30–15:45 | 15 | 02 Isaac ROS 5 |
| 15:45–16:00 | 15 | 03 MicroDuck in Isaac Sim 6.2 |
| 16:00–16:20 | 20 | 04 Train a policy with Isaac Lab 3 |
| 16:20–16:35 | 15 | 05 Inference with that exact policy |
| 16:35–16:55 | 20 | 06 CASCADE with that same policy |
| 16:55–17:00 | 5 | Evidence, owned shutdown and cloud-billing check |

Keep a visible timer. Use pairs: one driver runs the cell, one observer predicts and checks evidence; swap after Notebook03. Never reward finishing fast by bypassing gates. If the class is late, shorten discussion, not license review, identity verification, STOP handling or shutdown.

## Before opening the room

1. Use a fresh checkout of the approved immutable integrated commit. Prepare drivers, public pinned images/assets and local Qwen with the existing [Brev setup](brev.md) and [model guide](local_model.md). No notebook installs ROS/Kit in its host kernel. Confirm actual GPU index/UUID and resource ownership.
2. Run `bash scripts/notebook_setup.sh`. Run the host tests and inspect executed notebooks in `.workshop/executed/`; SKIPPED is not PASS. Run the actual Docker ROS tutorial with `RUN_NOTEBOOK_ROS=1`. Then rehearse all GPU cells with their real outputs privately retained.
3. Verify the actual image launch/source overlay, Sim 6.2.0.0, Lab 3.0 pinned source and Newton 1.6.1. Lab's package metadata may report 28.0.0. Read a real head-camera frame; inspect real CUDA processing after camera input exists. Do not conflate a loaded node with processed detections.
4. Rehearse training → checkpoint/export hashes → exact-policy inference → independent physical admission → actual local model/ROS episode. Require no silent public-ONNX fallback. A short actor warm-start with a new critic/optimizer is not convergence or full PPO resume. A failed new policy stays failed.
5. Keep failed runs, STOP/refusal cases, expired/foreign observation tests and uncertain-send evidence. Preserve the unchanged 0.5-second capture/lease bounds, BAM, physical limits, independent evaluator and no-retry policy.
6. On a 48 GB L40S, stop your own simulator/ROS/model before training; restart the model only after training/admission releases memory. Do not copy local RTX PRO performance claims onto a cloud SKU. No paid instance or public endpoint is created by these notebooks.
7. Start Jupyter on loopback with its token enabled. On this workstation launch the supervisor from the terminal with `heavyrun -n roscon-notebooks-jupyter -m 4G -- bash scripts/notebook_start.sh`. In a second **private, nonprojected terminal**, run `bash scripts/notebook_start.sh --url` with the same runtime-directory override. This reads the mode-0600 config without rotating the live token; `server.log` may redact it and is not a reliable login URL. Use an authenticated SSH tunnel, never public DDS/control/model listeners. Never copy the token-bearing URL into chat, notebook outputs or shared logs.
8. Open all six notebook titles in the correct order. Check that their action switches are false, student exercise file is still unfinished, and no private outputs are embedded. Prepare the explicit reference option, but do not preselect it.

**Staff release gate:** record whether each stage is CPU-only, recorded, live-local, SKIPPED, BLOCKED or cloud-unverified. Do not announce the whole route ready until the parent/instructor approves it. If a technical live gate is unavailable, students may still discuss code and read *clearly labeled actual recorded evidence*, but that lesson's live checkpoint is BLOCKED.

### Session-specific cold-start rehearsal

The earlier immutable Notebook03 rehearsal failed the old 180-second native deadline, then a separate extended run hit camera HTTP503 after health became ready. The helper uses **600 seconds by default**, shared across native and sensor readiness; `WORKSHOP_SIM_STARTUP_TIMEOUT` may explicitly select a finite value in `(0, 1800]`. This is a startup/read-only budget only. It does **not** alter either 0.5-second safety bound, training/admission 420-second teaching deadlines, motion/rest horizons or physical evaluator criteria. The subsequent complete local rehearsal passed the real cold startup/camera gate in 220.126 seconds. Preserve the earlier failures; this timing does not certify another instance or GPU.

1. Before Jupyter starts, select the approved immutable checkout/images, assigned GPU/domain/prefix and the exact intended `WORKSHOP_NOTEBOOK_WORK` (default `.workshop/notebooks`). `Session.sim_options()` uses **that directory's `sim-home`** for Kit/HOME caches. A Compose warmup, another worker's home, or a newly selected notebook work directory does not warm this session.
2. With allocation and EULA reviewed, execute actual 01→02→03 cells, in order, using the notebook opt-ins. Retain the executed notebook, elapsed startup time, runtime/image identity, real JPEG and original capture headers plus real ROS IMU/image-header output. The startup gate is GET-only and requires same-episode state and camera captures each no older than 0.5 seconds. It does not manufacture an input, restamp one, prove image/calibration exact pairing, or acquire a lease. The subsequent normal Notebook03 Gateway **does acquire its usual lease**.
3. On timeout, preserve the failed executed copy and owned container logs. Run the explicit owned cleanup; no process stealing, in-place rearm or automatic motion retry. A new deliberate rehearsal needs a new episode. Record it separately from the failed attempt.
4. Always finish Notebook03's ROS/Sim cleanup **before Notebook04 training**. Retain `sim-home` in the same session for classroom use, but do not retain a live lease/episode as a shortcut. Re-run actual classroom predecessor cells; do not seed completion from staff recordings. Notebooks05 and06 inherit the same bounded readiness gate;06 still needs the actual model diagnostic, a fresh exact-policy source episode and fresh sensors **before** gateway/attempt dispatch.
5. For an automated **live** nbclient rehearsal, give the cell runner a timeout above the selected startup bound **plus preflight/container-command overhead** (e.g. 1200 seconds for the 600-second default). The safe CPU validator's 180-second cell timeout is intentionally not a GPU acceptance harness. Keep public notebooks output-cleared and opt-ins false. Record cold and warmed session timings separately; neither certifies another GPU/cloud SKU.

The linked local run has been independently audited. For a new classroom instance, only mark this procedure rehearsed after reviewing that instance's exact-source outputs; until then its live gate remains **BLOCKED/unrehearsed**, even when CPU tests pass.

## 15:00–15:15 — Your slides

Keep your own introduction. At the handoff say:

> “We will build this chain in order: ROS messages, accelerated perception, a simulated robot, an actual learning update, inference with the model we just produced, and finally a reasoning agent. Each link has different evidence. A model saying it moved is not proof that the robot moved safely.”

Ask students to predict where safety authority belongs. Park detailed answers until Notebook06. Show the shutdown time now; do not spend it on an extra demo later.

## 01 · ROS 2 — 15:15–15:30

**Say:** “A node is a participant; a topic is a typed communication channel. We can inspect this graph without pretending that our first string message is a robot measurement.”

- **0–2:** Read the objective and predict whether a topic can exist with no subscriber. Confirm the lightweight host kernel. Explain the isolated tutorial container and configured ROS domain (default 71); do not reuse another team's domain.
- **2–6:** Opt into CPU ROS, launch the real publisher and read one message. Show the actual Docker invocation, caps and node name. Ask: “Which process produced these bytes?”
- **6–10:** Let pairs run node/topic/type/QoS inspection. Ask one pair to explain why the CLI echo node disappears. Do not present a sample output table as their result.
- **10–12:** Change the second message. Ask why `echo --once` is not a deterministic selector between simultaneous publishers. Discovery is asynchronous; explicit message type avoids the initial type-discovery race.
- **12–15:** Check each pair can identify a node, topic, type and subscriber. Stop only the notebook-owned tutorial. Confirm its removal and preserved logs.

**Check:** actual text received; actual type inspection; meaningful explanation. The `01` checkpoint is CPU tutorial evidence only.

**Recover:** Docker missing/denied → staff prepared environment, not a host ROS pip install. Missing image → setup is blocked. Publisher exists after kernel restart → owned cleanup then explicit restart. Wrong type/QoS → inspect real endpoints. If the exchange times out, retain the failure and label it missing evidence.

## 02 · Isaac ROS 5 — 15:30–15:45

**Say:** “Acceleration changes how a node computes, not what counts as evidence. A running detector with no camera is a running detector, not a successful perception pipeline.”

- **0–2:** Ask students to name the two calibrated-image inputs before inspecting the graph.
- **2–6:** Review the EULA/GPU opt-ins, start the actual CUDA AprilTag component alone and inspect its backend, family and physical tag-size parameters.
- **6–10:** Pairs locate inputs and output. Change the inspected input to CameraInfo. Ask: “Where is the publisher?” Correct answer is based on the actual graph; this isolated detector has no camera source yet.
- **10–13:** Explain tag size versus tag ID, optical frame and calibration. Ask how a wrong physical edge length affects estimated range. Explicitly say CPU image publication is not end-to-end GPU zero-copy.
- **13–15:** Save only the detector-only checkpoint, then stop the isolated detector. Preview that Notebook03 supplies real pixels.

**Check:** real node loaded; backend parameter reported; students do not invent detections or confuse missing camera with failed detection.

**Recover:** CUDA node fails → save launch log and inspect pinned image/driver. Do not start the full gateway before native Sim is available. If no GPU is available, use the actual earlier log only as recorded evidence; do not write a live completion checkpoint by hand.

## 03 · Isaac Sim 6.2 MicroDuck — 15:45–16:00

**Say:** “There is one physics owner: Isaac Lab's Newton model. Isaac Sim supplies rendering and application services. The onboard camera is a sensor; the human overview and evaluator's world pose are not agent observations.”

- **0–2:** Ask which of encoders, IMU acceleration, head image, root pose and overview the controller/agent may consume. Explain the public actor is only the introductory sensor episode, before student training.
- **2–6:** Opt in to the native zero-command episode. Check the actual runtime and episode ID. Explain that zero requested velocity still includes active neural balance, gravity and contact; it is not torque-off.
- **6–10:** Display the fetched head-camera JPEG. Ask students to identify a visible feature and its capture identity. Say explicitly that this is a real rendering, not a drawing. Do not show the overview as agent input.
- **10–13:** Start the full ROS bridge only now. Inspect actual IMU fields and image header. Ask what an unavailable IMU orientation means. Explain why two independent `--once` samples do not prove exact image/calibration pairing.
- **13–15:** Predict stale-source behavior; clean up this lesson's owned ROS and Sim before training. Read the owned container status, not just the notebook kernel status.

**Check:** real runtime, real head JPEG, episode match, actual ROS sensor message. No invented joint/IMU publisher is allowed. This lesson does not admit CASCADE motion.

**Recover:** occupied port → stop nothing automatically; coordinate with owner. Missing assets/camera → preserve log and label BLOCKED. Wrong/stopped/restarted episode → old checkpoint is invalid; explicit cleanup and operator restart, never rearm in place. Camera timeout is not a perception pass. A simulator screenshot alone is not an independent physical verdict.

## 04 · Train with Isaac Lab 3 — 16:00–16:20

**Say:** “We are doing real short PPO fine-tuning from a public actor, not learning a converged walking gait in seven minutes. The public ONNX lacks the optimizer and critic needed to resume a full PPO run.”

- **0–4:** Read the actual 61-to-14 contract. Ask which input slice encodes desired forward speed, and why previous raw action is not the filtered actuator target. Read the reward terms from the actual training source; do not call magnitude penalty smoothness.
- **4–7:** Predict the stability/tracking trade-off. Explain actor initialization versus critic/optimizer initialization, and reward-only evaluator truth versus policy observations.
- **7–14:** Stop competing owned workloads, run the explicitly bounded short warm-start job in a new output directory. Watch actual update metrics and retain both success and failure logs. If it exceeds the timebox, stop its exact owned container, record incomplete, and do not claim a checkpoint is deployable.
- **14–18:** Inspect actual `training_receipt.json`, `checkpoint.pt`, `actor.onnx` and `policy_manifest.json`. Check finite real update metrics and changed weights. Compute and preserve **both checkpoint and actor hashes**; those identities must survive Notebooks05 and06.
- **18–20:** Ask each pair: “What did this run prove, and what did it not prove?” Correct: actual optimizer work and export identity; not convergence, task success or safe motion.

**Check:** actual new checkpoint/export, source-bound manifest, disclosed warm-start provenance, no old ONNX substitution. Notebook05 must refuse absent or changed artifacts.

**Recover:** missing confirmed policy API → wrong checkout/image; fail rather than guess flags. Training fails → no completion checkpoint; inspect actual failure. Insufficient VRAM → sequence your own workloads. Do not raise control/evaluator limits, reuse another pair's model without explicit labeling, or quietly restore the pretrained actor.

## 05 · Inference with the same policy — 16:20–16:35

**Say:** “Inference does not update weights. We must first prove which bytes are running, then separately test whether their behavior meets the unchanged physical criteria.”

- **0–3:** Predict what should happen if the exported actor is edited or the manifest points elsewhere. Recompute checkpoint and actor identity; require Notebook04's exact pair.
- **3–10:** Run the independent, bounded exact-policy physical admission route with the existing motion/rest evaluator and BAM. **Admission must precede `serve`: the implemented API refuses an unadmitted serving process.** Read the real receipt even after failure. Keep physical admission distinct from later ROS/model acceptance.
- **10–13:** Only after admission, explicitly launch the exact manifest/admission pair in a fresh native episode. Read live runtime policy identity and display its actual onboard head snapshot. No fallback on load/admission error is allowed.
- **13–15:** Ask why a failed policy is still a useful training result. Preserve the failure rather than lower the threshold. Stop this inference episode;06 starts a different episode only after model readiness and explicit operator approval.

**Check:** same checkpoint and export hashes from04, actual runtime actor identity, real head snapshot and actual admission receipt. Physical admission must bind the exact actor, mode, profile and current source contract, not merely a filename.

**Recover:** mismatched hash → stop and repeat the provenance handoff, never copy a checksum over the mismatch. Failed admission → no agent movement; use no-motion analysis and adapter work in06. Restart → new episode, stale observations invalid. Camera may be available while movement remains unadmitted.

## 06 · CASCADE with that same policy — 16:35–16:55

**Say:** “CASCADE chooses tools; the ROS/native owners enforce authority. Our trained policy actuates joints. The independent evaluator decides whether the measured maneuver met the contract. These are separate facts.”

- **0–2:** Reconfirm exact policy identity/admission and one-attempt-per-episode. Locate emergency stop without firing it as a warmup. STOP latches and is not proof of rest or torque-off.
- **2–9:** Students implement `exercises/capstone/tools.py`: construct an allowlisted observation from episode/frame/capture/tag evidence, STOP wins, reject extra/numeric step arguments, delegate to the instructor-owned domain and preserve its real receipt. No world pose, overview, lease token or HTTP bypass enters student/model output. Run the CPU contract tests.
- **9–10:** If the coding timebox ends, offer **the explicit reference option**. Announce it and select the reference path openly. Never silently substitute the answer file. CPU fixtures are not real ROS/model/physics evidence.
- **10–15:** With instructor release approval, exact-policy admission and local-model readiness established, start the full gateway for the fresh episode. Read the current observation. Run one bounded actual Qwen/CASCADE attempt using the selected student/reference file. Do not reuse a lease from the earlier sensor lesson.
- **15–18:** Read actual provider/trace/report artifacts. Ask students to distinguish `accepted`, `completed`, `verification_available` and `verified`; an exit2/refusal is not a completed motion task. Trace the request ID to the independent native verdict.
- **18–20:** Discuss STOP/refusal using an explicitly operator-authorized new episode if there is time and approval, otherwise use the instructor's actual labeled recorded STOP evidence. Never automatically rerun an uncertain send. Runner teardown latches stop, so the old episode cannot be reused.

**Check:** exact04 actor still selected, actual onboard evidence → actual local model decision → ROS acceptance/refusal → independent execution verdict. No direct simulator command bypass, unrestricted numeric velocity or hidden retry.

**Recover:** model unavailable → preserve local-only/no-motion adapter lesson; no cloud model credentials. Expired lease or observation → refusal is correct, do not widen the 0.5-second gate or auto-renew authority. Gateway stalls → preserve timings/logs, block motion and inspect with staff. Failed admission → no-motion only. Uncertain send → no retry. Stopped episode → owned shutdown and deliberate new episode, not in-place rearm.

## Executable policy handoff card (04 → 05 → 06)

The public notebooks now contain the actual commands, not placeholders. `notebooks/policy_workshop.py` is a **stdlib orchestration/identity helper**, not another PPO implementation or safety evaluator. Its canonical checks call the existing `policy.student` loader inside the prepared container; native raw-trace evaluation is not reimplemented in the notebook kernel.

### Prepared-image gate

Set `WORKSHOP_SIM_IMAGE`, `WORKSHOP_ROS_IMAGE` and `WORKSHOP_AGENT_IMAGE` before starting Jupyter to images built from the approved source. The recorded local rehearsal used `roscon/microduck-{sim,ros5,agent}:notebook-final-candidate`; these are local tags, not public registry downloads. Brev preparation builds its own `:local` images. Do not assume an older tag contains the current API or reviewed control source.

Before any GPU job,04 probes the **shipped image**, without a source overlay, for `train --warm-start-onnx`, `admit_policy --policy-manifest`, and `play --policy-manifest --policy-admission`. It also checks **`onnx==1.22.0`**.06 checks `python -m microduck_workshop.agent.run --help` for the policy flags and `--native-health-url`. Missing capability means BLOCKED, not permission to install an ad hoc dependency stack or silently use the seed policy. The source overlay is read-only and explicit after that gate.

### Identity and lifecycle table

| Stage | Bytes/evidence checked | What is deliberately not claimed |
|---|---|---|
| 04 | `checkpoint.pt`, changed `actor.onnx`, `training_receipt.json`, `policy_manifest.json`, raw transitions, current training/control source | Convergence, full PPO resume or physical admission |
| 05 admission | Exact04 identity plus `admission.json` and **all required raw traces**; native loader recomputes unchanged physical verdicts | ROS/perception/model acceptance |
| 05 serving | Same checkpoint on disk and actor/manifest/admission hashes in live health; fresh episode and actual onboard camera | A camera image alone proves motion success |
| 06 | Recheck04/05 bytes, tested student/reference adapter hash, new episode, runner's before/after native identity and actual provider/report | Agent exit0 or `success:true` replaces independent physical audit |

Both the **entire run directory** and **entire admission directory** mount read-only into Sim and agent. Never mount just public receipt snapshots. The checkpoint is verified on disk; inference loads its exported actor, not a PPO optimizer. Hash checking is identity/provenance, not a model-visible world-state tool or a signed security credential.

Stage receipts also retain diagnostic helper/ROS source hashes and resolved container image IDs read from the actual containers. They do not hash student notebook answers or change the existing runtime-source/artifact checkpoint checks. These extra fields support audit; they are not an admission credential or proof that changed code was physically re-evaluated.

Training and admission output arguments point to a **new child directory under a new private mount parent**. The CLIs create that child themselves with `exist_ok=False`. Do not pre-create it, rerun into it, delete an incomplete attempt, or restamp checksums. Training/admission have420-second teaching deadlines; timeout stops the exact owned container and retains evidence. The run may be incomplete on slower hardware; this deadline is not a runtime benchmark.

Notebook05 admits **before** serving. An explicit isolated `play --mode validate` on an unadmitted manifest, with no step profile, is an optional offline diagnostic only: it does not enable a listener/agent and its direct-velocity result is not the fixed-step admission. This is not a substitute classroom completion route.

### Capstone facilitation and recovery

- All action switches start false. `RUN_ADAPTER_TESTS` is separate from `CHECK_MODEL` and `RUN_AGENT`; CPU work remains available when admission fails. Students edit the real exercise file, not a notebook answer stub. The unchanged unfinished starter is expected to fail its contract tests.
- `USE_REFERENCE=False` is the default. If time expires, explicitly switch it, announce the reference and rerun the exact selected file's tests. Its hash and selection label are retained in the private attempt record.
- The real local-model readiness probe uses **synthetic read-only diagnostic data**, not robot evidence. It finishes before the native agent episode and gateway lease. It does not start or stop someone else's model server.
- Notebook05's episode is shut down before06. Notebook06 rechecks admitted bytes and creates a different Sim episode. The gateway is launched immediately before the one actual CASCADE invocation, not while students code or a model loads.
- The attempt marker is saved **before dispatch**. If launch or delivery is uncertain, the attempt remains consumed. There is no motion retry, lease renewal, fallback, automatic rearm or threshold change. Inspect outputs, clean up and obtain deliberate new operator authorization for any new episode.
- The runner's entrypoint is **`microduck_workshop.agent.run`**, with explicit `--policy-manifest`, `--policy-admission`, `--native-health-url`, `--episode-id`, `--frame-id`, and `--tools-file`. Native identity never becomes a model control tool.
- Read `provider.jsonl`, `policy_identity.json`, `report.json`, the trace and independent native verdicts. The06 checkpoint means an actual **attempt requiring independent audit**, not a manufactured task-success flag. Missing report/verdict remains missing. Preserve exit2/refusal and incomplete paths.

### Executable CPU rehearsal (not live acceptance)

```bash
bash scripts/notebook_setup.sh
.workshop/notebook-venv/bin/python -m pytest tests/test_notebooks*.py -q
RUN_NOTEBOOK_POLICY_CPU=1 \
WORKSHOP_SIM_IMAGE=roscon/microduck-sim:notebook-final-candidate \
WORKSHOP_AGENT_IMAGE=roscon/microduck-agent:notebook-final-candidate \
  .workshop/notebook-venv/bin/python -m pytest tests/test_notebooks*.py -q
```

The opt-in executes the real06 CPU reference-checker cell through nbclient. It explicitly selects the reference **in the private executed copy only**; public06 remains student-first and output-free. CPU containers use `roscon-nb-complete-*`, domain72,4GiB/2CPUs and no GPU. Hardware actions still print SKIPPED. Keep `.workshop/executed/` private. Passing these tests does **not** complete the live train→admit→camera→ROS/CASCADE acceptance gate.

For distinct staff lanes, `WORKSHOP_NOTEBOOK_PREFIX` and `WORKSHOP_ROS_DOMAIN` select container prefix/domain before Jupyter starts. Defaults remain `roscon-nb`/71. Keep these stable until owned cleanup. Domain isolation does not make native8766 shareable: a live listener remains a hard conflict and is never stolen. `WORKSHOP_MODEL_URL` must be an explicit loopback endpoint; classroom default is `http://127.0.0.1:8080/v1`.

## 16:55–17:00 — Close the loop and shut down

**Say:** “Keep what actually happened, including what failed. A truthful blocked result is more useful than a green label without evidence.”

Ask each pair for one statement proved by a tool result and one claim still unproved. Save executed notebooks privately, preserve the training/export/admission/report artifacts and distinguish local from cloud evidence. Public notebooks remain cleared of outputs, tokens and private paths.

Run the notebooks' **owned** cleanup, confirm containers disappeared, then stop only your Jupyter supervisor and your prepared model process. Existing generic stop scripts target shared Compose names; do not use them to clean an unrelated notebook lane. Verify GPU allocations and listeners are gone for your own processes. Do not stop other teams' containers or models.

Finally use the actual Brev Console to stop/delete the authorized instance and verify billing state. Stopping Docker is not stopping cloud billing. Do not create, publish or delete paid resources on the students' behalf without authorization.

## Recovery card

| Actual failure | Say | Do | Never do |
|---|---|---|---|
| Safe validator prints SKIPPED | “The code path is readable; hardware was not run.” | Record skipped coverage | Call it live PASS |
| Missing predecessor/state | “The handoff is incomplete.” | Run the earlier notebook or restore its unchanged private evidence | Fabricate a state receipt |
| Kernel restart | “Python restarted; Docker may not have.” | Inspect owned state and explicit cleanup | Assume robot reset |
| Old episode/changed export | “This identity no longer matches.” | Stop, preserve logs, explicitly recreate the correct handoff | Restamp or substitute |
| Training timeout | “We do not have a completed update/export.” | Stop only the owned job; retain partial evidence | Claim convergence |
| Admission fails | “The policy is not admitted for movement.” | Keep no-motion/CPU work and actual failure | Weaken evaluator or use old ONNX |
| Agent/network timeout | “Delivery may be uncertain.” | Stop/refuse; investigate exact request | Retry movement |
| Missing cloud rehearsal | “Local evidence does not certify this SKU.” | Label cloud-unverified | Invent Brev receipt |

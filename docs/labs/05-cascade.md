# Lab 5 — CASCADE decides; a fixed ROS step executes

**25 minutes · 16:30–16:55.** Goal: implement a small sensor/tool adapter, run a real
**local Qwen3.8** brain, and distinguish its decision from an independent physical verdict.

**Entry gate:** the instructor must admit the release's full camera → Isaac ROS → local
model → ROS → Newton route using [same-episode acceptance](../capstone.md#final-acceptance-checklist).
Native step validation and a read-only model run are separate evidence, not that pass.
If admission is missing, complete the CPU exercise and the explicitly **no-motion** check
in [Brev instructions](../brev.md#start-the-live-session); mark the motion checkpoint blocked.

## 1. Understand the game and locate the stop — 4 minutes

| Tool | What it does |
|---|---|
| `microduck.observe` | Reads fresh allowlisted onboard detections; tag 0 = GO, tag 1 = STOP |
| `microduck.step_forward` | Sends at most one fixed maneuver; accepts `{}` or `{"action":"step_forward"}` only |
| `microduck.verify` | Reads the same request's status and independent verdict |
| `emergency_stop` / `task_done` | CASCADE's composed stop/completion tools; neither can invent physical success |

The fixed **`step-forward-v1`** maneuver requests peak `.10 m/s`, zero lateral/yaw,
and a **2.0-second simulation horizon**. The existing neural policy receives `.25` forward
for **1.0 second**, then **exact zero for 1.0 second** to settle with active balance,
gravity and contact. This is not raw `.10` velocity tracking. The original verifier's
rest window and limits are unchanged. Read [the fixed-step contract](../step_transport.md).

Do not use `walk_bounded` or choose numeric speeds for this game. The original
[constant-velocity calibration remains FAILED / NOT_READY](../calibration.md).

Keep this **ROS tools** command available, but **do not execute it just as a warmup**:

```bash
timeout 8s ros2 service call /workshop/microduck/emergency_stop std_srvs/srv/Trigger '{}'
```

A stop latches; it is not torque-off or proof of rest. Neither the model nor another
agent process may reset it. The operator must stop the stack and intentionally start a
new episode. Runner teardown also latches stop, so there is **one attempt per episode**.

## 2. Complete the adapter — 8 minutes

Edit [exercises/capstone/tools.py](../../exercises/capstone/tools.py) in your host editor:

1. **Observation (4 minutes):** validate source episode/frame, finite capture age and
   tag IDs; construct a new allowlisted result. STOP wins. No simulator poses, human
   overview, lease tokens or newly stamped old pixels.
2. **Fixed step (4 minutes):** accept only the two argument forms above. Reject numeric
   choices/unknown keys and delegate to `domain.step_forward`; return its real receipt.
   The instructor-owned domain rechecks freshness after inference and preserves UUID,
   generation, uncertain delivery, stop and verification. Do not create an HTTP bypass.

Run in the **host** checkout:

```bash
.workshop/student-venv/bin/python scripts/agent_check_exercise.py
# Explicit reference if your coding timebox expires:
.workshop/student-venv/bin/python scripts/agent_check_exercise.py --tools-file solutions/capstone/tools.py
```

Unfinished exercises fail with `NotImplementedError`; there is no silent solution fallback.
These are CPU fixtures, not live camera/model/physics evidence. Explain one rejected case
before proceeding. See [the reference](../../solutions/capstone/tools.py).

## 3. Run one observation-driven attempt — 7 minutes

Only after the entry gate passes, read the current **ROS tools** observation:

```bash
timeout 8s ros2 service call /workshop/microduck/observe \
  microduck_workshop_interfaces/srv/Observe '{}'
```

In a **host** terminal, copy its exact episode and frame, and choose a new output name:

```bash
read -r -p "Current Observe episode_id: " EPISODE_ID
read -r -p "Current Observe frame_id: " FRAME_ID
RUN_NAME=capstone-go-01
docker compose run --rm --no-deps --workdir /opt/workshop agent \
  python -m microduck_workshop.agent.run \
  --base-url http://127.0.0.1:8080/v1 --model qwen3.8-27b \
  --episode-id "$EPISODE_ID" --frame-id "$FRAME_ID" \
  --max-steps 6 --run-dir "/outputs/$RUN_NAME" \
  --tools-file /opt/workshop/exercises/capstone/tools.py
```

The runner's built-in task is the fixed-step signal game: observe; on fresh GO without
STOP, request **one** `step_forward` with no numeric choices; verify; report honestly.
This prompt is not the safety authority. The ROS/native owners independently enforce
freshness, episode, generation, lease and stop conditions.

The command explicitly uses **your edited file**. If staff choose the reference instead,
use the [reference invocation](../capstone.md#student-and-reference-handlers), not a quiet
change to production handlers. A timed-out send must not be retried.

Read the actual host output:

```bash
python3 -m json.tool ".workshop/agent-output/$RUN_NAME/report.json"
```

Keep `provider.jsonl`, `trace.jsonl`, `run.json` and the report. Trace the camera/detection
identity and request ID into the native evaluator evidence with staff. `accepted`,
`completed`, `verification_available` and `verified` differ. Exit **2** means the task
did not pass; a correct refusal can produce it. Never edit a report into success.

## 4. Compare refusal and stop — 6 minutes

The preceding runner has latched stop on teardown. For a STOP case, the **operator**
explicitly authorizes a new episode; there is no in-place re-arm:

```bash
# Host control terminal:
bash scripts/brev_stop.sh
```

Restart the model in its dedicated terminal, wait for `READY`, then launch STOP on the host:

```bash
# Model terminal (foreground):
MODEL_GPU=0 MODEL_PORT=8080 bash scripts/model_start.sh
```

```bash
# Separate host control terminal:
WORKSHOP_GPU=0 WORKSHOP_TAG_ID=1 bash scripts/brev_start.sh --accept-nvidia-eula
```

Open a new ROS tools shell. Repeat section 3 with the **new** observed episode/frame and
`RUN_NAME=capstone-stop-01`. Require no motion and an honest unverified/false outcome.
If restart exceeds the timebox, use the instructor's labeled real STOP receipt instead;
never claim it ran on your instance. Keep the stopped-source result from Lab 2 as another
no-motion case. Both tags, no allowed tag, stale/foreign evidence and an uncertain send
must not become permission to move; extra cases belong in the staff rehearsal.

## Checkpoint

Present **observation → real model choice → ROS acceptance/refusal → execution → independent
verdict** as distinct facts. Mark each case executed, observed or blocked. Do not call a
correct refusal a completed motion task.

Next: [recap and cloud shutdown](06-wrap-up.md). No extra run during the final five minutes.

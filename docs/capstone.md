# CASCADE capstone: sensor-only fixed-step signal game

The public CASCADE `AgentOrchestrator`, composed with `RobotRuntime`, calls a workshop
domain through **ROS 2 Lyrical services**, not directly through simulator HTTP. The gateway
owns the actuator lease. Isaac Lab owns Newton and learned joint control; the language
model chooses a tool, not joint targets.

For the timed lesson, use [Lab 5](labs/05-cascade.md). This page is the technical/run reference.

## Evidence boundaries

| Evidence | What it establishes |
|---|---|
| [Native fixed-step receipt](step.md) | Six preregistered requests plus two fresh production-admission confirmations passed unchanged native physical gates |
| [Portable local model](local_model.md) | Real Qwen3.8 GGUF / llama.cpp tool calls on local RTX PRO; its read-only diagnostic uses synthetic STOP, not live robot input |
| [Composed observation rehearsal](brev.md#execution-scope) | Actual Sim head pixels → CUDA AprilTag → ROS Observe → local Qwen, deliberately no motion |
| [Release readiness](../README.md) | Authority for the separate full same-episode motion acceptance; no adjacent layer supplies this result |

No Brev VM or L40S execution is established by these local receipts. Compiled SM 89 and
SM 120a kernels are not a hardware rehearsal. The original
[constant-velocity calibration](calibration.md) remains **FAILED / NOT_READY**; prior
[model-only failures and diagnostic receipts](../solutions/capstone/evidence/README.md)
and [native low-command failures](runtime.md) remain intact.

## One fixed maneuver, not a velocity exercise

| Tool | Meaning |
|---|---|
| `microduck.observe` | Actual gateway snapshot: episode, generation, original frame sequence/time, capture age, optical frame and tag IDs. Tag 0 = GO; tag 1 = STOP; STOP wins. |
| `microduck.step_forward` | At most one fixed `step-forward-v1` request per task. Accepts `{}` or `{"action":"step_forward"}` only. |
| `microduck.verify` | Query the last exact request's status. No request means `no_command`, not success. |
| `emergency_stop` | Independent priority route, backed by a separate ROS node/executor. An ACK is not proof of rest. |
| `task_done(success, summary)` | Model conclusion, constrained by the runtime's independent forward-step objective. |

Read tools accept `{}` or constant selectors `{"action":"observe"}` /
`{"action":"verify"}`. These do not change the frozen empty ROS Observe request.
Other keys and numeric step choices are refused, not repaired or clipped.

The step requests **peak `.10 m/s`, `vy=wz=0`, total horizon `2.0 s`**. It conditions the
existing public ONNX at **`.25` forward for `1.0 sim s`, then exact zero for `1.0 sim s`**.
The learned balance policy, gravity, contact, BAM/backlash and native physics stay active.
This is not raw `.10` velocity tracking, torque-off, a scripted gait or a frozen pose.
The settle phase is inside the requested horizon; the original **`.35 s` verification
wait, `.04 m/s` planar and `.10 rad/s` yaw rest bounds** are unchanged.

Compose explicitly launches `--step-profile step-forward-v1`. Standalone serving does
not enable that capability by default. The old `--command-profile direct` and
`calibrated-forward-v1` semantics are unchanged. `walk_bounded` and the ROS
`bounded_motion` service remain **operator diagnostics**, absent from this game's model
catalog. A verified standstill, tiny displacement, turn or legacy request cannot satisfy
the independent forward-step objective. See [step transport](step_transport.md).

## Admission, freshness and verification

1. The domain requires a prior fresh GO observation, then **re-reads perception after
   model inference**. Changed episode/generation, backwards frame/time, STOP or stale
   capture refuse motion. RPC time is included in effective age.
2. The ROS client checks the capture deadline immediately before sending. The ROS server
   independently checks its actual capture/detection cache, then forwards the original
   monotonic capture deadline (`capture + .5 s`), never receipt-now, to `/v1/step`.
3. Every active-step renewal needs fresh same-episode GO proof. The native owner checks
   proof on admission and each native consume, including queued first consumption.
   Missing/stale/foreign/STOP evidence disables authority; lease/proof expiry cannot
   be revived by a later GO. All processes use the same host monotonic clock.
4. A fresh UUID and expected generation bind the request. Unknown delivery latches stop
   and is never retried, even by starting another task. Float64 serialization is tested
   separately in the installed Lyrical interfaces; invalid numbers are rejected first.
5. `accepted`, `executing`, `completed`, `verification_available` and `verified` are
   distinct. The motion tool waits within a bounded budget for its real terminal verdict.
   A late verdict cannot erase the composed runtime's earlier unverified-motion debt.

A stop is latched until an explicitly operator-started **new simulator episode**. There
is no model reset/re-arm tool or staff reset service. Runner teardown sends stop too:
**one attempt per episode**. Zero intent does not prove physical rest.

### No ground-truth or secret channel

The domain creates a new allowlisted sensor result; it does not copy arbitrary gateway
objects, raw reasons, exceptions, verifier coordinates, world/root pose, overview images,
labels or lease tokens. A second projection filters provider tool messages. Evaluator
truth stays in evaluator-only files, not agent navigation context.

`RecordedLocalClient` permits named local Qwen3.8/Nemotron 3.5 models at an explicit
loopback HTTP `/v1` endpoint. It ignores proxy settings, follows no redirects, has no
hosted credential/fallback, and does not repair arguments or retry inference. Tool choice
comes from the actual model. `tool_choice=required` is not the motion safety authority.

## Prepared Brev route

Use [Brev preparation](brev.md) **before class**. It builds the real Lyrical/CASCADE image
and separately the pinned Sim/Lab image. CASCADE is public MIT source commit
`d7a456c22d46d53e9588db6a55a0c6c916aa4963`; the image setup runs
`python -m microduck_workshop.agent.api_check` against its actual imported contracts.
Do not source Sim's bundled ROS/Jazzy libraries into this Python process.

The classroom model is the pinned **Qwen3.8-27B UD-Q4_K_M GGUF** with F16 KV and source-built
llama.cpp, not an NVFP4 configuration assumed to work on L40S. Preparation/build/verification
commands and measured local limits are in [local_model.md](local_model.md). No API key is needed.

After setup, in the dedicated **host model terminal**:

```bash
MODEL_GPU=0 MODEL_PORT=8080 bash scripts/model_start.sh
```

Wait for `READY`; keep the terminal open. In another **host** terminal, from this checkout:

```bash
WORKSHOP_GPU=0 WORKSHOP_TAG_ID=0 bash scripts/brev_start.sh --accept-nvidia-eula
docker compose exec -T ros bash /opt/workshop/entrypoint.sh \
  timeout 8s ros2 service call /workshop/microduck/observe \
  microduck_workshop_interfaces/srv/Observe '{}'
```

Start neither an agent nor a second gateway during model initialization. Compose shares
only the ROS container's private IPC namespace with the agent, with LOCALHOST DDS and
domain **27**. A graph that discovers a service but cannot deliver a response is not ready.

## Student and reference handlers

Edit only `exercises/capstone/tools.py`: translate the observation into its allowlist and
delegate fixed-step requests to `domain.step_forward`. Do not modify safety limits,
verifiers or gateway ownership. The [complete reference](../solutions/capstone/tools.py)
uses the production [observation implementation](../src/microduck_workshop/agent/observation.py)
and the instructor-owned [domain](../src/microduck_workshop/agent/domain.py).

In the prepared **host CPU environment**:

```bash
# Intentionally fails until both student TODOs are complete:
.workshop/student-venv/bin/python scripts/agent_check_exercise.py
# Explicit reference; CPU fixtures only:
.workshop/student-venv/bin/python scripts/agent_check_exercise.py --tools-file solutions/capstone/tools.py
```

After full release admission, copy the actual current Observe identities and run once:

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

The host exercise directory is mounted read-only and **explicitly selected**. To use the
reference instead, choose a **fresh episode**, new output name, and explicit solution mount:

```bash
docker compose run --rm --no-deps --workdir /opt/workshop \
  -v "$PWD/solutions:/opt/workshop/solutions:ro" agent \
  python -m microduck_workshop.agent.run \
  --base-url http://127.0.0.1:8080/v1 --model qwen3.8-27b \
  --episode-id "$EPISODE_ID" --frame-id "$FRAME_ID" \
  --max-steps 6 --run-dir /outputs/capstone-reference-01 \
  --tools-file /opt/workshop/solutions/capstone/tools.py
```

Omitting `--tools-file` selects production handlers; it must not silently replace an
unfinished exercise. The built-in task already specifies the fixed signal game—do not
replace it with numeric velocity instructions. Every output directory must be new.

`provider.jsonl` records SDK request parameters/responses, not raw HTTP packets or auth
headers; the SDK merges `extra_body` into the HTTP body. `trace.jsonl`, `run.json` and
`report.json` retain choices/outcomes under `.workshop/agent-output/<run-name>`.
Exit **2** means the requested task did not pass. Inspect both report and independent
native verdict, not only the final model sentence.

## Stop and another episode

Ctrl+C queues cancellation and a priority stop independently of model inference. The
separate operator command, from a **host** terminal, is:

```bash
docker compose exec -T ros bash /opt/workshop/entrypoint.sh \
  timeout 8s ros2 service call /workshop/microduck/emergency_stop std_srvs/srv/Trigger '{}'
```

An unknown stop response is not a success; notify staff and use `bash scripts/brev_stop.sh`
to shut down the owned stack. That script also stops its owned local-model process.
For another authorized attempt: stop, restart the foreground model, wait for readiness,
then explicitly run `brev_start.sh --accept-nvidia-eula` and obtain **new** Observe identities.
Use `WORKSHOP_TAG_ID=1` on that new launch for the authored STOP board. There is no auto-rearm.

## Final acceptance checklist

Do not promote CPU, model-only or native-only results to an autonomous motion pass.
The full positive receipt must connect the **same actual episode and request**:

- Actual onboard image/CameraInfo and CUDA Isaac ROS detections, not synthetic IDs.
- Real local-model provider transcript choosing `microduck.step_forward`, not a scripted LLM.
- Matching ROS request UUID/episode/generation and actual learned-policy inputs/actions.
- Newton identity and unchanged independent movement/support/duration/rest verdicts.
- Native capture-deadline and lease enforcement; negative freshness, uncertain-delivery
  and priority-stop checks under unchanged limits, with cases labeled separately.
- Provider requests free of evaluator truth and lease secrets.

Brev/L40S or Brev/RTX PRO deployment additionally requires its **own** actual-host rehearsal,
including combined VRAM, preview access and cloud stop/delete verification. A local RTX PRO
receipt cannot supply those claims. Check [release readiness](../README.md) before class.

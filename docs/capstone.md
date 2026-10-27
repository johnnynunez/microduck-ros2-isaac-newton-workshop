# CASCADE capstone: sensor-only signal game

## What this implements—and what it does not prove

The real public CASCADE `AgentOrchestrator` calls a workshop domain composed with
`RobotRuntime`. The domain uses **ROS 2 Lyrical services**, not the simulator's HTTP
API. Isaac ROS 5.0 must process the actual onboard camera before live motion is
permitted. The ROS gateway, not the model client, owns and renews the simulator lease.

Implemented and CPU-tested: exact CASCADE contracts, strict motion admission,
allowlisted sensor/verdict messages, priority cancellation, student exercises and
complete runnable reference handlers. A real local Qwen3.8 model completed a
three-turn **read-only synthetic diagnostic**. That proves model/tool integration,
**not** ROS perception, learned locomotion, physical stopping or Brev execution.
The real camera → Isaac ROS → CASCADE → ROS → Newton acceptance run is a separate gate.

## Install in the ROS-capable Python environment

Use Ubuntu 24.04 / Python 3.12 with the project's ROS 2 Lyrical workspace already built.
Do not mix Jazzy or a different Python ABI into this process. The simulator can remain
in its separate Isaac Lab environment.

```bash
source /opt/ros/lyrical/setup.bash
source ros_ws/install/setup.bash
python3 -m venv --system-site-packages .venv-agent
source .venv-agent/bin/activate
python -m pip install -e . -r requirements-agent.txt pytest
python -m microduck_workshop.agent.api_check
python -m microduck_workshop.agent.run --help
```

`requirements-agent.txt` installs CASCADE from public MIT source commit
`d7a456c22d46d53e9588db6a55a0c6c916aa4963`. `api_check` checks the imported source
against that revision (or the Git install's recorded origin) and prints the actual
constructor signatures and consumed source hashes. It does not connect an actuator.
For CPU-only work, omit the ROS setup and use Python 3.12; ROS imports are lazy.

The verified upstream extension uses:

- `cascade.robotics.contracts.ResourceDescriptor` and `ToolDescriptor`;
- `cascade.robotics.runtime.RobotRuntime`;
- `cascade.agent.orchestrator.AgentOrchestrator`;
- `cascade.agent.llm.OpenAICompatClient`;
- `cascade.memory.episodic.EpisodicMemory` and `cascade.agent.trace.TraceLogger`.

There is no `RobotHAL` at this revision. No new YAML domain kind or private plugin
is assumed. The domain implements `tool_descriptors`, `begin_task`, `execute`, `stop`,
`reset_stop` and `close`, including members the short upstream Protocol omits.

## The tools and safety boundary

| Tool | Meaning |
|---|---|
| `microduck.observe` | Actual gateway detection snapshot: episode, generation, frame sequence/time, effective capture age, optical frame and tag IDs. Tag 0 = GO; tag 1 = STOP; STOP wins. |
| `microduck.step_forward` | At most one fixed `step-forward-v1` send per task. Accepts `{}` or `{"action":"step_forward"}` only; no model-selected velocities or duration. |
| `microduck.verify` | Query the last exact request's actual gateway status. No command means `no_command`, not success. |
| `emergency_stop` | CASCADE's composed priority route, backed by a separate ROS node/executor. An ACK is not proof of physical rest. |
| `task_done(success, summary)` | Model conclusion. Runtime requires an accepted fixed-step request and its same-episode independent verdict. A verified zero/tiny/turn/legacy command cannot satisfy the forward-step objective. |

Read tools accept `{}` or an explicitly declared constant selector:
`{"action":"observe"}` / `{"action":"verify"}`. These optional model-facing fields
never authorize motion and **do not change the frozen empty ROS Observe request**.
Other fields/selector values are refused. They address an observed Qwen argumentless-tool
failure; the client never silently repairs a model's arguments.

The new fixed step is **not** a renamed constant-velocity command. It requests peak
forward velocity `.10 m/s`, `vy=wz=0`, and a `2.0 s` horizon. The admitted
`step-forward-v1` policy profile conditions the existing network at `.25` forward
for the first `1.0 s`, then exactly zero for the second `1.0 s`. Gravity, contact,
ONNX/BAM and the learned balance policy stay active. The original `.35 s` rest
verification window and `.04 m/s` planar / `.10 rad/s` yaw rest limits are unchanged.

The prior constant-velocity direct and calibrated-forward trials remain **failed /
NOT READY**. The new step needs its own native validation and complete ROS/brain
acceptance episode; implementing this tool is not proof it walks or stops safely.
The common motion envelope is not expanded. The old `walk_bounded` Python helper
and ROS `bounded_motion` service remain operator diagnostics only and are **not in
the signal-game model catalog**. See [the step transport contract](step_transport.md).

The domain requires a prior GO observation, then **re-reads perception after model
inference**, rejects changed episode/generation or backwards frame/time, and includes
the complete service round trip in capture age. The ROS client checks the remaining
freshness deadline again after waiting for service availability and immediately before
`call_async`. A new UUID binds every send to the expected episode and generation.
Unknown delivery latches a stop and is never retried, including at a new task boundary.
The ROS step service independently rechecks its actual `CaptureCache` for same-episode
fresh GO without STOP at server admission. It forwards the original capture deadline
(`capture_monotonic + .5`, never receipt-now) to `/v1/step`. Every active-step lease
renewal needs a fresh server proof; stale, absent, foreign or STOP perception disables
renewal and requests priority stop. The simulator must enforce proof expiry at admission
and every native consume, including a delayed first consume. Client pre-send checks are
only an additional fence. These monotonic clocks must refer to the same host.
Validated motion numbers are converted to Python `float` at the ROS float64 ABI;
identifiers and generations keep their original types. Invalid numbers are rejected
before conversion, not repaired.

`accepted`, `executing`, `completed`, `verification_available` and `verified` remain
separate. The motion tool waits for an actual terminal verdict within a bounded budget;
otherwise its postcondition stays unverified. At the pinned CASCADE revision, a later
`verify` does not erase the composed runtime's earlier unverified-motion debt. A late
verdict therefore cannot retroactively turn the task green.

`begin_task` never clears a stop. There is no staff-reset service in the frozen API,
so this domain's `reset_stop` deliberately refuses even the operator route. Staff must
perform an independently authorized reset/new simulator episode. Normal command expiry
belongs to the owner, not to the LLM. Runner teardown sends a latched stop; starting
another agent process is not permission to re-arm.

### No ground-truth or secret channel

Observation translation builds a new allowlisted object; it does not copy the gateway
response. Raw reasons, exception text, verifier dictionaries, maps, world/root poses,
overview images, simulation object labels and lease tokens do not enter model context.
Verification exposes only identity, status and verdict—not coordinate-bearing evidence.
Resource metadata is fixed, minimal simulation/ROS metadata, not arbitrary backend data.
The provider boundary applies a second field projection to tool messages. CASCADE's
`agent_tool_output` is only a size projection; it is **not** used as a truth filter.

`RecordedLocalClient` accepts only explicitly named local Bolt/Qwen models at a loopback
HTTP `/v1` endpoint. It uses no hosted credential, ignores proxy environment settings,
follows no redirects, performs no automatic retries or parameter fallback, and bounds
requests, tokens and timeouts. `tool_choice=required` still lets the model choose the
tool and arguments; `task_done` is its completion/refusal channel. Schemas and independent
runtime admission—not this provider hint—are the safety authority.

## Student exercise (approximately 20–25 minutes)

Edit only `exercises/capstone/tools.py`:

1. **Observation translation:** validate the expected camera/episode, finite age and
   monotonic identifiers; construct the sensor-only result; handle STOP, missing and
   stale detections without any truth fallback.
2. **Fixed-step handler:** accept only `{}` or `{"action":"step_forward"}` and reject
   numeric choices/unknown keys. Delegate to `domain.step_forward` and return its real
   receipt unchanged. Do not dispatch directly to the gateway. The instructor constructs
   the fixed request and handles fresh-at-send checks, UUID/generation binding, uncertain
   delivery, priority stop and verification. The server and native owner still enforce
   their independent freshness checks.

```bash
# Initially fails explicitly with NotImplementedError; no silent reference fallback.
python scripts/agent_check_exercise.py

# Explicit reference selection: sixteen CPU fixture checks, not physical evidence.
python scripts/agent_check_exercise.py --tools-file solutions/capstone/tools.py
```

The complete observation reference is the actual tested production implementation at
`src/microduck_workshop/agent/observation.py`, re-exported by
`solutions/capstone/tools.py`; it is not a mock. The reference motion handler is in that
solution file, and the complete instructor dispatch is in `agent/domain.py`.

## Run the real ROS capstone

Start the independently admitted simulator, ROS gateway and actual Isaac ROS detector
using their documented launch commands first. Use the same local DDS domain for the
gateway and this client, isolated from physical robot networks:

```bash
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_DOMAIN_ID=71  # choose the instructor-assigned domain, not a shared hardware network
ros2 service call /workshop/microduck/observe microduck_workshop_interfaces/srv/Observe '{}'
```

Copy **the actual** `episode_id` and `frame_id` from the response into the variables
below. Do not use fixture IDs or guess a frame. A stale response is a blocker to diagnose,
not permission to bypass the detector.

```bash
python -m microduck_workshop.agent.run \
  --model qwen3.8-27b --base-url http://127.0.0.1:8080/v1 \
  --namespace /workshop/microduck \
  --episode-id "$EPISODE_ID" --frame-id "$FRAME_ID" \
  --max-steps 6 --run-dir runs/capstone-001 \
  --tools-file exercises/capstone/tools.py
```

The CLI default is local `qwen3.8-27b` at `http://127.0.0.1:8080/v1`, the intended
portable class configuration; its live acceptance is **pending**, not asserted by
this default. To use the existing explicitly selected NVFP4 Qwen server, pass
`--model qwen3.8-27b --base-url http://127.0.0.1:18510/v1`. There is no automatic
server, model or hosted fallback. Nemotron 3.5 Bolt remains an explicit allowed choice.

Use `--tools-file solutions/capstone/tools.py` only when deliberately selecting the
reference. Omitting the flag uses the complete production handlers. Output directories
must be new; previous failures are not overwritten. `provider.jsonl` records provider API
request parameters and responses, without authorization headers. The OpenAI SDK merges
`extra_body` into the HTTP JSON body; this file is not a raw packet capture. `trace.jsonl`, `run.json` and
`report.json` retain model choices and actual tool outcomes. Exit status 2 means the
requested task did not pass; do not edit it into a success.

`Ctrl-C` sets a cancellation event and queues `runtime.request_stop()` independently of
model inference. This deliberately does not call upstream `AgentOrchestrator.cancel()`,
which is arm-specific at the pin. The independent operator path is:

```bash
ros2 service call /workshop/microduck/emergency_stop std_srvs/srv/Trigger '{}'
```

Always audit the simulator's actual stop/expiry evidence separately. A balancing policy
can continue running at zero intent; zero intent is not torque-off or proof of rest.

## Local model preparation on Brev

Pre-stage downloads before the two-hour class. No command here provisions paid instances.
Keep the server loopback-only and forward ports through the approved Brev SSH session.
Check free RAM/VRAM before co-locating a model, Isaac ROS and the simulator.

### Historical explicit Bolt alternative (not the default; not executed here)

The pinned public CASCADE source supplies a checksum-verified GGUF/projector/drafter
recipe, model license attribution and pinned llama.cpp build. Given a clean checkout at
`$CASCADE_ROOT` of the commit above:

```bash
MODEL_ROOT="$PWD/.cache/brain" WARM_START=0 SPEC=none \
  bash "$CASCADE_ROOT/scripts/serve_nemotron_bolt_llamacpp.sh" --setup-only
MODEL_ROOT="$PWD/.cache/brain" WARM_START=0 SPEC=none PORT=18510 CTX=8192 PARALLEL=1 \
  bash "$CASCADE_ROOT/scripts/serve_nemotron_bolt_llamacpp.sh"
```

Select `--model nemotron-3.5-bolt` in the agent. This downloads separately licensed
NVIDIA model artifacts; consult the source manifest/license before redistribution.
The available validation host had neither the GGUF nor llama.cpp binary cached, and the
GGUF download redirect failed DNS. **No llama.cpp/Bolt inference or L40S result is claimed.**

### Actually exercised alternative: RTX PRO, vLLM 0.32.0, Qwen3.8

The local test used the existing vLLM 0.32.0 installation and cached Apache-2.0
`Inferact/Qwen3.8-27B-NVFP4` revision
`6128240ebaf4eaa7bad2b3d1c72c37d677c5f462`. Model weights and KV cache were NVFP4;
attention backend was FLASHINFER. This route is for the tested SM12x RTX PRO—not a
claim that L40S supports that NVFP4 configuration.

```bash
vllm serve Inferact/Qwen3.8-27B-NVFP4 \
  --revision 6128240ebaf4eaa7bad2b3d1c72c37d677c5f462 \
  --served-model-name qwen3.8-27b --host 127.0.0.1 --port 18510 \
  --max-model-len 8192 --max-num-seqs 1 --max-num-batched-tokens 2048 \
  --gpu-memory-utilization 0.40 --enforce-eager \
  --kv-cache-dtype nvfp4 --attention-backend FLASHINFER \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  --default-chat-template-kwargs '{"enable_thinking":false}'
```

The actual local process was memory-capped at 32 GiB on GPU 1 and used approximately
39,382 MiB reported VRAM. A `0.40` fraction on a smaller card is a different memory budget;
measure the full colocated workload rather than copying that fraction blindly.
No existing service, driver, clocks or model source was changed.

```bash
# Real local inference, but ONLY a synthetic read-only fixture. Never a robot acceptance test.
python scripts/agent_model_probe.py --model qwen3.8-27b --out runs/model-only-001
```

The passing diagnostic chose `observe(action=observe)`, read synthetic STOP, chose
`verify(action=verify)`, received `no_command`, and honestly called `task_done(false)`.
Three earlier three-call attempts exposed extra arguments on zero-argument tools;
explicit empty-argument prompting and `tool_choice=required` alone did not fix them.
Those failures are retained. The final three-call run used explicit optional constant
read selectors; no motion envelope, freshness threshold or verifier was relaxed.
This diagnostic never produces a physical success flag. The preserved request/response
records and failure history are in [the model-only evidence directory](../solutions/capstone/evidence/README.md).

## Final acceptance checklist

Do not promote the diagnostic to a workshop-ready physical episode until all of these
come from the **same actual episode**:

- Actual onboard images/CameraInfo and Isaac ROS detections, not a synthetic publisher.
- Real model provider transcript choosing the permitted motion, not a scripted LLM.
- Matching ROS request UUID, episode and generation; actual learned policy observations/actions.
- Newton runtime identity and independent movement/support/expiry/rest verdicts.
- Negative stale-perception, uncertain-delivery and priority-stop evidence under unchanged limits.
- No simulator truth or secrets in the captured provider requests.
- A separate Brev/L40S or Brev/RTX PRO rehearsal if those environments are advertised as tested.

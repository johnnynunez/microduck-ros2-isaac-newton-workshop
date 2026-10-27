# Instructor runbook — 120 minutes, not a two-hour installation

> **Primary classroom route:** use the [notebook instructor guide](notebook_instructor.md) and [six notebooks](../notebooks/README.md). This page retains the earlier terminal-based timing and commands as technical reference; do not mix its timetable with the notebook agenda.

**27 October 2026 · 15:00–17:00 Europe/Madrid · Aula 2-7 · ROSCon España, Valencia.**
Use [the student route](labs/README.md) as the projected navigation page. Bring your own NVIDIA/Newton slides; this runbook does **not** replace them with a generic deck.

## Before admitting the class

Follow [the Brev preparation sequence](brev.md#prepare-everything-before-the-120-minute-class)
on one pinned release; publish its exact evidence in the [README](../README.md). Setup
requires explicit `--accept-nvidia-eula --accept-mesh-license`, not preset attendee consent.
Preload images, public licensed robot/model assets, shader caches, Lyrical interfaces,
portable Qwen3.8 and `.workshop/student-venv`. Have students finish
[pre-class preparation](labs/00-before-class.md). Confirm each actual L40S/RTX PRO Brev SKU,
private access and one-day credit expiry. No laptop GPU or physical robot is needed.

Open the actual course on a student-equivalent account. Rehearse start, training, return to playback, detector start, local-agent run, stop and **Brev instance teardown**. Verify commands against the actual source and `--help` where supported; a filename or intended CLI is not an execution receipt. Do not ask students to discover unbuilt interfaces during the lesson.

Keep host/editor, foreground model, and sourced Lyrical ROS-tools terminals visibly separate. Students run Sim only through the prepared Compose image, not from a ROS shell. ROS 2 Lyrical on Noble must come from NVIDIA's buildfarm. Do not mix Jazzy libraries into it or use removed Isaac ROS 4.x NITROS packages instead of the 5.0 `rosidl::Buffer` architecture.

### Live release gates

Use the release's **actual evidence** to fill a staff checklist before class; this table states requirements, not achieved results.

| Gate | Evidence required | Does not count |
|---|---|---|
| Environment | Imported Sim 6.2 / Lab 3.0 / Newton identities, actual GPU, pinned assets and policy | Target version strings or a screenshot of an installed package |
| Robot | Real Newton reset/step; fixed `step-forward-v1` → zero → step and unchanged physical gates; stop/proof/lease expiry | ONNX shape, direct numeric velocity trial, scripted gait, MJLab/PhysX fallback |
| ROS | Actual `/clock`, encoders, IMU and timestamp-paired onboard Image/CameraInfo | Fabricated unit-test messages |
| Training | Real rollouts, optimizer update and parameter-change/output receipt | Import-only smoke or pretrained inference |
| Perception | Isaac ROS 5.0 detection tied to a real onboard image, stale-source refusal | Synthetic IDs; a sample rosbag proves only its own input path |
| Agent | Same-episode actual camera → CUDA detector → portable local Qwen → ROS fixed step → Newton verdict | Native-only pass, read-only observation run, model-only synthetic STOP, ACK or `task_done` |
| Cloud | Student-equivalent Brev rehearsal and stop/delete verification | A local RTX PRO run represented as Brev or L40S validation |

No gate inherits “PASS” from an adjacent layer. Native [fixed-step validation](step.md)
is real; the [old calibration](calibration.md) remains FAILED / NOT_READY. Portable Qwen
model-only and composed **no-motion** observation runs do not supply full autonomous
acceptance. Check the release receipt before enabling Lab 5's motion command. If blocked,
use its CPU exercise and [explicit no-motion check](brev.md#start-the-live-session), clearly
labeled. A local RTX PRO receipt is neither an L40S nor a Brev test.

### Staff setup and operator controls

- Start zero-intent Newton telemetry and its single gateway before 15:15. Lab 1 needs a real graph; Lab 2 inspects it rather than spawning another owner. Keep the agent disabled until its segment.
- Scene launch supports **GO tag 0** and **STOP tag 1**, selected with `WORKSHOP_TAG_ID` on a new episode. Both/no-tag cases may be discussed from labeled test/rehearsal evidence; do not invent live scene controls or publish synthetic IDs.
- There is **no pause/reset/re-arm service**. Lab 2 deliberately uses `sim_stop.sh` at its end and keeps ROS alive long enough to query stale-source refusal; Lab 3 then calls `brev_stop.sh` before training. After training, restart the foreground model, wait for `READY`, and start a new episode. Reopen ROS tools shells.
- A capstone runner **latches stop on teardown**, even for no-motion tasks. Each new attempt requires an operator-authorized stack stop/model restart/new episode and new Observe identities. Never run a stop warmup immediately before a GO attempt on the same episode.
- Keep the priority emergency-stop terminal visible. The stop path must remain responsive while model inference is blocked. Zero intent is not torque-off or proof of rest; inspect the independent state/verdict.
- Keep the transport loopback-only and preview authenticated. Do not publish model/control ports or DDS on the Internet. `ROS_DOMAIN_ID` is isolation, not access control.
- Rehearse the exact four-update, horizon-32, seed-7 training command in [Lab 3](labs/03-reinforcement-learning.md). Stop the model and playback first, especially on 48 GB L40S; measure the full restored simulator/ROS/model peak on the advertised SKU. Do not improvise environment counts.
- Keep the model foreground terminal open. Explicit `MODEL_PORT=8080` matches Brev start and agent commands; do not accidentally use the historical 18510/18511 diagnostic endpoint. If a port/cache/GPU override is needed, apply it consistently across lifecycle commands.
- Ask participants to set a reminder before their 24-hour credits expire. Locate their cloud stop/delete control before class, not at 16:59.

## Live facilitation

Use a visible timer. Each checkpoint is an observable result, not “everyone followed along.” Ask for a show of hands at transitions. A two-minute environment problem goes to staff; do not let one installation consume the room.

### 15:00–15:15 — existing instructor slides

Use your opening material to answer: what runs on the Brev GPU; what Isaac Sim, Isaac Lab, Newton and Isaac ROS each own; where ROS fits; and why the local agent is not a high-rate controller. Close with the actual data-path diagram in the [student index](labs/README.md), then show the priority stop and billing reminder.

Use the [NVIDIA MicroDuck workflow context](nvidia_workflow_context.md) to distinguish engineering agents that prepare/train an experiment from CASCADE choosing bounded runtime tools. Its larger ramp-training experiment is context, not our classroom result; retain the existing timebox and your own slides.

Do not imply the public MJLab policy is automatically valid in Newton, or that a two-hour class trains a gait from scratch. Ask: **“Which process is allowed to write joint intent?”** Answer: the single simulation-thread owner through the learned-policy/control contract, not every ROS subscriber or the LLM.

### 15:15–15:35 — [ROS basics](labs/01-ros-basics.md)

Budget: discovery 4 minutes; helper edits 8; real node 5; service schema 3. Demo one command, then let students type. Explain `name[i]`/`position[i]` before handing them Python.

- **Checkpoint:** real publisher, actual observer subscription, `use_sim_time=true`, helper tests.
- **Answer key:** selecting by name survives array reordering. A reliable-only subscriber may not match a best-effort publisher. Future stamps suggest a clock mismatch/reset/order issue, not fresh observations. Simulation age cannot detect an indefinitely paused source.
- **Recovery:** at 15:27 offer [the full reference solution](../solutions/ros_basics/README.md). It is a read-only observer, not a teleop bypass. Mark CPU tests and live subscriber evidence separately.

### 15:35–15:55 — [simulation and sensors](labs/02-simulation.md)

Budget: runtime ownership 5; IMU 4; camera pairing 7; deliberate source stop 4. Point to the actual imported backend and owner receipt, not just a logo. Show onboard and overview images side by side.

- **Checkpoint:** backend identity, sensor field/units, a genuinely paired Image/CameraInfo receipt, and the stopped-source observation retained for Lab 4.
- **Answer key:** separate `--once` commands can capture different frames. The camera is an authored teaching pinhole model, not measured hardware calibration. Unavailable IMU orientation cannot become a valid default quaternion. The human overview and GT pose stay out of agent inputs.
- **Recovery:** if a camera fails, keep that failure visible; no synthetic fallback. A recorded pairing may be discussed but cannot satisfy a student's live camera gate.

### 15:55–16:15 — [short RL experiment](labs/03-reinforcement-learning.md)

Budget: policy contract 5; reward reasoning 4; real run 7; playback restoration 4. The actual run gets four prewarmed minutes inside its segment. Stop at the timebox even if compilation or convergence is incomplete.

- **Checkpoint:** actual rollout/optimizer and parameter-change receipt, or explicit blocked status.
- **Answer key:** command slice `48:51` changes the desired body velocity. Previous raw action differs from a scaled/filtered target. A 61→14 ONNX does not restore critic/optimizer/counters, certify BAM/delay parity or demonstrate convergence. Read the implemented reward, not an assumed upstream port.
- **Recovery:** inspect labeled recorded evidence if necessary; never relabel random updates or ONNX inference as actual training. Restore the separately validated playback policy, not a newly initialized actor, before perception.

### 16:15–16:30 — [Isaac ROS perception](labs/04-isaac-ros.md)

Budget: architecture 3; real output discovery 4; gateway observation 4; compare fresh/stale evidence 4. Compose already launches the detector. Confirm `/workshop/microduck/tag_detections` in the graph and detector parameter `size=0.20` (launch argument `tag_size`). Reuse Lab 2's stale-source observation rather than spending another startup cycle.

- **Checkpoint:** a real image/detection identity pair and an observation refused after the source ages beyond its limit.
- **Answer key:** delivery time cannot replace capture time. Fresh-but-no-signal is not permission to move. CUDA acceleration does not establish zero-copy across a CPU image transport. Tag 0/1 is a classroom convention.
- **Recovery:** sample-rosbag output may diagnose the detector, but does not prove live MicroDuck input. Do not proceed to motion on stale/unmapped detections.

### 16:30–16:55 — [CASCADE capstone](labs/05-cascade.md)

Budget: game/stop path 4; adapter edits 8; local-model attempt 7; refusal comparison 6. Locate but do not pre-fire stop on the GO episode. The fixed action has no numeric model arguments: requested peak .10, neural .25 for 1 s then zero for 1 s, 2 s total. Offer the explicitly selected [reference handler](capstone.md#student-and-reference-handlers) when the coding timebox expires.

- **Checkpoint:** source image → detection → real local-model decision → bounded ROS request → learned policy/Newton execution → independent verdict.
- **Answer key:** an accepted request is not completed execution, and completed execution is not independent verification. `verification_available=false` means no verdict, not a pass. Unknown delivery must not be retried automatically. The model must not reset a stop. Evaluator truth is not agent navigation input.
- **Cases:** one admitted fresh GO attempt; a fresh operator-started STOP episode if the timebox allows, otherwise the instructor's labeled real receipt. The student already has Lab 2's stopped-source case. Never turn stale/foreign/no-tag/STOP evidence or uncertain delivery into motion. Do not spend the shutdown slot on another restart.
- **Recovery:** a correct refusal is a learning success; it is not a verified locomotion result. Do not loosen bounds or freshness to make the demo look successful.

### 16:55–17:00 — [recap and mandatory shutdown](labs/06-wrap-up.md)

One minute to explain the architecture; one to save work; three to stop processes and verify Brev stopped/deleted state plus retained resources. No final “one more run.” Ask staff to help anyone still holding a running instance at 17:00. Containers stopped ≠ cloud charges stopped.

## Review and evidence hygiene

Student evidence can be a short private note with: revision, actual device/runtime, episode/source frame/request IDs, test or run result, independent verdict and a clear **executed / observed / recorded / blocked** label. Never copy lease tokens, model API credentials or private endpoints into public logs. Keep source attribution and mesh/policy licenses separate; [NOTICE](../NOTICE) and [the pinned manifest](../provenance/sources.json) explain the boundary.

Static/CPU course verification from the repository root:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .workshop/student-venv/bin/python -m pytest --noconftest \
  tests/test_curriculum_docs.py tests/test_curriculum_ros_basics.py \
  tests/test_curriculum_ros_node.py -q
```

[Tested helper behavior](../tests/test_curriculum_ros_basics.py), [explicit fake-module adapter checks](../tests/test_curriculum_ros_node.py), and [course-link/timing checks](../tests/test_curriculum_docs.py) are separate from live ROS/GPU/Brev validation. Exercise TODOs intentionally fail when selected; reference solutions must pass. A green CPU suite is never a classroom-runtime certificate.

[Common problems and safe responses](troubleshooting.md) · [Transport and service schema](transport.md)

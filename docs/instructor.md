# Instructor runbook — 120 minutes, not a two-hour installation

**27 October 2026 · 15:00–17:00 Europe/Madrid · ROSCon España, Valencia.**
Use [the student route](labs/README.md) as the projected navigation page. Bring your own NVIDIA/Newton slides; this runbook does **not** replace them with a generic deck.

## Before admitting the class

Pin one tested repository revision and publish its exact runtime commands/evidence in the [README](../README.md). Have students finish [pre-class preparation](labs/00-before-class.md). Preload images, licensed robot assets, public policy weights, shader caches, local model and ROS workspace. Confirm one L40S or RTX PRO Brev instance per student, secure access and one-day credit expiry. No laptop GPU and no physical robot are required.

Open the actual course on a student-equivalent account. Rehearse start, training, return to playback, detector start, local-agent run, stop and **Brev instance teardown**. Verify commands against the actual source and `--help` where supported; a filename or intended CLI is not an execution receipt. Do not ask students to discover unbuilt interfaces during the lesson.

Keep two terminal roles visibly separate: the Isaac Lab/Newton environment and the Lyrical ROS gateway/tools environment. ROS 2 Lyrical on Noble must come from NVIDIA's buildfarm. Do not mix Jazzy libraries into it or use removed Isaac ROS 4.x NITROS packages instead of the 5.0 `rosidl::Buffer` architecture.

### Live release gates

Use the release's **actual evidence** to fill a staff checklist before class; this table states requirements, not achieved results.

| Gate | Evidence required | Does not count |
|---|---|---|
| Environment | Imported Sim 6.2 / Lab 3.0 / Newton identities, actual GPU, pinned assets and policy | Target version strings or a screenshot of an installed package |
| Robot | Real Newton reset/step, learned walk → zero → resume, actuator/observation contract and stop/watchdog checks | ONNX tensor shape, scripted gait, MJLab/PhysX fallback |
| ROS | Actual `/clock`, encoders, IMU and timestamp-paired onboard Image/CameraInfo | Fabricated unit-test messages |
| Training | Real rollouts, optimizer update and parameter-change/output receipt | Import-only smoke or pretrained inference |
| Perception | Isaac ROS 5.0 detection tied to a real onboard image, stale-source refusal | Synthetic IDs; a sample rosbag proves only its own input path |
| Agent | Real local-model requests/tool choices through ROS, command execution and independent verdict | Scripted tool sequence, hosted/mock fallback, ACK or `task_done` |
| Cloud | Student-equivalent Brev rehearsal and stop/delete verification | A local RTX PRO run represented as Brev or L40S validation |

No gate may inherit “PASS” from an adjacent layer. If a gate remains blocked, announce the precise limit and use labeled code/recorded-evidence discussion for that segment; do not advertise it as live completion. Do not substitute another physics backend. The complete live capstone requires all gates.

### Staff setup and operator controls

- Start zero-intent Newton telemetry and its single gateway before 15:15. Lab 1 needs a real graph; Lab 2 inspects it rather than spawning another owner. Keep the agent disabled until its segment.
- Prepare the rehearsed GO, STOP, ambiguous/no-tag and stale-camera scene conditions. Scene selection is staff-controlled; students must not create synthetic detection messages.
- Have the verified local pause/resume and **operator-only** reset/re-arm procedure ready. No such operation belongs in a model tool. Reset invalidates episodes/generations and cached observations.
- Keep the priority emergency-stop terminal visible. The stop path must remain responsive while model inference is blocked. Zero intent is not torque-off or proof of rest; inspect the independent state/verdict.
- Keep the transport loopback-only and preview authenticated. Do not publish model/control ports or DDS on the Internet. `ROS_DOMAIN_ID` is isolation, not access control.
- Rehearse switching the one GPU from playback/local-model work to the bounded training profile and back. Do not improvise environment counts on student instances.
- Ask participants to set a reminder before their 24-hour credits expire. Locate their cloud stop/delete control before class, not at 16:59.

## Live facilitation

Use a visible timer. Each checkpoint is an observable result, not “everyone followed along.” Ask for a show of hands at transitions. A two-minute environment problem goes to staff; do not let one installation consume the room.

### 15:00–15:15 — existing instructor slides

Use your opening material to answer: what runs on the Brev GPU; what Isaac Sim, Isaac Lab, Newton and Isaac ROS each own; where ROS fits; and why the local agent is not a high-rate controller. Close with the actual data-path diagram in the [student index](labs/README.md), then show the priority stop and billing reminder.

Do not imply the public MJLab policy is automatically valid in Newton, or that a two-hour class trains a gait from scratch. Ask: **“Which process is allowed to write joint intent?”** Answer: the single simulation-thread owner through the learned-policy/control contract, not every ROS subscriber or the LLM.

### 15:15–15:35 — [ROS basics](labs/01-ros-basics.md)

Budget: discovery 4 minutes; helper edits 8; real node 5; service schema 3. Demo one command, then let students type. Explain `name[i]`/`position[i]` before handing them Python.

- **Checkpoint:** real publisher, actual observer subscription, `use_sim_time=true`, helper tests.
- **Answer key:** selecting by name survives array reordering. A reliable-only subscriber may not match a best-effort publisher. Future stamps suggest a clock mismatch/reset/order issue, not fresh observations. Simulation age cannot detect an indefinitely paused source.
- **Recovery:** at 15:27 offer [the full reference solution](../solutions/ros_basics/README.md). It is a read-only observer, not a teleop bypass. Mark CPU tests and live subscriber evidence separately.

### 15:35–15:55 — [simulation and sensors](labs/02-simulation.md)

Budget: runtime ownership 5; IMU 4; camera pairing 7; controlled pause 4. Point to the actual imported backend and owner receipt, not just a logo. Show onboard and overview images side by side.

- **Checkpoint:** backend identity, sensor field/units and a genuinely paired Image/CameraInfo receipt.
- **Answer key:** separate `--once` commands can capture different frames. The camera is an authored teaching pinhole model, not measured hardware calibration. Unavailable IMU orientation cannot become a valid default quaternion. The human overview and GT pose stay out of agent inputs.
- **Recovery:** if a camera fails, keep that failure visible; no synthetic fallback. A recorded pairing may be discussed but cannot satisfy a student's live camera gate.

### 15:55–16:15 — [short RL experiment](labs/03-reinforcement-learning.md)

Budget: policy contract 5; reward reasoning 4; real run 7; playback restoration 4. The actual run gets four prewarmed minutes inside its segment. Stop at the timebox even if compilation or convergence is incomplete.

- **Checkpoint:** actual rollout/optimizer and parameter-change receipt, or explicit blocked status.
- **Answer key:** command slice `48:51` changes the desired body velocity. Previous raw action differs from a scaled/filtered target. A 61→14 ONNX does not restore critic/optimizer/counters, certify BAM/delay parity or demonstrate convergence. Read the implemented reward, not an assumed upstream port.
- **Recovery:** inspect labeled recorded evidence if necessary; never relabel random updates or ONNX inference as actual training. Restore the separately validated playback policy, not a newly initialized actor, before perception.

### 16:15–16:30 — [Isaac ROS perception](labs/04-isaac-ros.md)

Budget: architecture 3; real output discovery 4; gateway observation 4; stale-source challenge 4. Point to the real launch remaps and authored tag size. Do not guess detector output topics; derive them from the running graph.

- **Checkpoint:** a real image/detection identity pair and an observation refused after the source ages beyond its limit.
- **Answer key:** delivery time cannot replace capture time. Fresh-but-no-signal is not permission to move. CUDA acceleration does not establish zero-copy across a CPU image transport. Tag 0/1 is a classroom convention.
- **Recovery:** sample-rosbag output may diagnose the detector, but does not prove live MicroDuck input. Do not proceed to motion on stale/unmapped detections.

### 16:30–16:55 — [CASCADE capstone](labs/05-cascade.md)

Budget: game/stop 4; adapter edits 8; local-model attempt 7; refusal tests 6. Rehearse stop first, then inspect and re-arm through the tested staff procedure only. Offer the release's complete capstone reference if students exhaust the coding timebox.

- **Checkpoint:** source image → detection → real local-model decision → bounded ROS request → learned policy/Newton execution → independent verdict.
- **Answer key:** an accepted request is not completed execution, and completed execution is not independent verification. `verification_available=false` means no verdict, not a pass. Unknown delivery must not be retried automatically. The model must not reset a stop. Evaluator truth is not agent navigation input.
- **Cases:** one fresh GO attempt and one no-motion case per student; show separately labeled real rehearsal evidence for additional cases. STOP/ambiguous/no-tag, stale source, old episode/generation, stop latch and uncertain send must never silently become motion.
- **Recovery:** a correct refusal is a learning success; it is not a verified locomotion result. Do not loosen bounds or freshness to make the demo look successful.

### 16:55–17:00 — [recap and mandatory shutdown](labs/06-wrap-up.md)

One minute to explain the architecture; one to save work; three to stop processes and verify Brev stopped/deleted state plus retained resources. No final “one more run.” Ask staff to help anyone still holding a running instance at 17:00. Containers stopped ≠ cloud charges stopped.

## Review and evidence hygiene

Student evidence can be a short private note with: revision, actual device/runtime, episode/source frame/request IDs, test or run result, independent verdict and a clear **executed / observed / recorded / blocked** label. Never copy lease tokens, model API credentials or private endpoints into public logs. Keep source attribution and mesh/policy licenses separate; [NOTICE](../NOTICE) and [the pinned manifest](../provenance/sources.json) explain the boundary.

Static/CPU course verification from the repository root:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest --noconftest \
  tests/test_curriculum_docs.py tests/test_curriculum_ros_basics.py \
  tests/test_curriculum_ros_node.py -q
```

[Tested helper behavior](../tests/test_curriculum_ros_basics.py), [explicit fake-module adapter checks](../tests/test_curriculum_ros_node.py), and [course-link/timing checks](../tests/test_curriculum_docs.py) are separate from live ROS/GPU/Brev validation. Exercise TODOs intentionally fail when selected; reference solutions must pass. A green CPU suite is never a classroom-runtime certificate.

[Common problems and safe responses](troubleshooting.md) · [Transport and service schema](transport.md)

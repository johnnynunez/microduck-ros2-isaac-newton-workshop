# Student route — two hours with MicroDuck

**ROSCon España · Valencia · 27 October 2026 · 15:00–17:00 Europe/Madrid · Aula 2-7.**
Use your own NVIDIA Brev **L40S or RTX PRO** instance and the instructor's one-day credits. Your laptop is a terminal and browser; it does not need a GPU.

[Complete pre-class setup](00-before-class.md) **before** this clock starts. This route teaches one small end-to-end system, not a full ROS course or a gait trained to convergence.

| Local time | Minutes | Activity | Evidence you keep |
|---|---:|---|---|
| 15:00–15:15 | 15 | Instructor's existing NVIDIA/Newton slides | Draw the data path and identify the physics owner |
| 15:15–15:35 | 20 | [1. ROS 2 basics](01-ros-basics.md) | Real joint-state subscription and passing helper tests |
| 15:35–15:55 | 20 | [2. Robot, simulation and sensors](02-simulation.md) | Actual Newton identity; matching camera metadata |
| 15:55–16:15 | 20 | [3. Observations, actions, rewards and training](03-reinforcement-learning.md) | Real optimizer-update receipt; no convergence claim |
| 16:15–16:30 | 15 | [4. Isaac ROS 5.0 perception](04-isaac-ros.md) | Detection tied to an actual onboard image |
| 16:30–16:55 | 25 | [5. CASCADE signal game](05-cascade.md) | Agent tool trace plus independent motion verdict |
| 16:55–17:00 | 5 | [6. Recap and cloud shutdown](06-wrap-up.md) | Saved work and confirmed cloud stop/delete |

## Keep this picture in mind

```text
Isaac Lab 3.0 owns Newton + learned locomotion policy
          │ actual encoder / IMU / rendered onboard RGB
          ▼
ROS 2 Lyrical gateway ── images + calibration ──► Isaac ROS 5.0 CUDA AprilTag
          ▲                                              │
          │ bounded ROS services                         │ fresh, allowlisted signal
          └──────────────── CASCADE local brain ◄─────────┘

Independent evaluator ──► physical verdict, not agent navigation inputs
Human overview preview ─► your browser only, not the agent's eyes
```

Isaac Sim **6.2** provides the rendering/application environment. Isaac Lab **3.0** owns the task and Newton model. Isaac ROS **5.0** runs CUDA perception; ROS 2 **Lyrical on Noble** comes from NVIDIA's buildfarm. CASCADE connects a local language model to constrained tools. A natural-language request is **not** a joint target.

## How to use the commands

- **Host** means your Brev checkout; **ROS tools** means the sourced Lyrical container shell opened in [pre-class preparation](00-before-class.md#2-prepare-the-terminals). Each lab labels the boundary. Do not mix ROS libraries into the simulation interpreter.
- Run the copy-paste commands in each lab. [Brev setup](../brev.md) is instructor preparation; the [README](../../README.md) records release readiness. The fixed-step game uses `microduck.step_forward`, not a model-selected numeric velocity.
- **A readiness gate is real:** if that release has no verified runtime command/receipt for a stage, stop that stage and ask the instructor. A CPU test or a source file is not a live-runtime pass. Do not substitute a fake publisher, scripted gait, MJLab runtime or PhysX demo.
- `timeout` bounds observation commands. Exit code 124 means the timeout expired; it is not a passing measurement. Ctrl+C stops a continuous CLI subscriber, not cloud billing.
- Keep a short local notebook of your observations. Never paste credentials, lease tokens, private model URLs or a public motion endpoint into it.

## If you fall behind

Use [the complete ROS basics solution](../../solutions/ros_basics/README.md), then rejoin at the next checkpoint. Ask for help after **two minutes** on an environment problem. A staff demonstration can teach the concept, but mark it **observed**, not **executed on my instance**. Recorded evidence must be labeled recorded; it does not replace today's live acceptance.

[Instructor runbook](../instructor.md) · [Troubleshooting](../troubleshooting.md) · [Frozen ROS contract](../transport.md)

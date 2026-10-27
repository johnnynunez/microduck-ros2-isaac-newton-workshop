# MicroDuck: ROS 2, reinforcement learning and physical-AI agents

**ROSCon España 2026 · 27 October · 15:00–17:00 · Valencia**

A two-hour, hands-on workshop using **ROS 2 Lyrical, NVIDIA Isaac ROS 5.0, Isaac Sim 6.2.0, Isaac Lab 3.0 and Newton**, ending with a real **CASCADE** agent controlling a simulated MicroDuck.

Participants work in **NVIDIA Brev**, using instructor-provided one-day credits on **L40S or RTX PRO**. No laptop GPU is required. Prepare downloads and environments before the two-hour session.

> **Readiness:** implementation and live validation are in progress. The target stack is explicit, but source availability and passing CPU tests are not proof of a working ROS/Isaac ROS/Newton/agent episode. Do not use this initial revision as an unqualified classroom-ready release. Runtime results and reproducible commands are being added before the instructor's 08:30 handoff.

## Official MicroDuck sources

- [Pollen MicroDuck runtime and SDK](https://github.com/pollen-robotics/microduck)
- [Pollen MicroDuck RL environments](https://github.com/pollen-robotics/microduck_rl) — **MJLab**, used as upstream reference, not the workshop simulator.
- [Official public policy set](https://huggingface.co/pollen-robotics/microduck-policies) — hosted on **Hugging Face**, not a GitHub policy repository.
- [CASCADE](https://github.com/johnnynunez/cascade) — physical-AI agent orchestration.
- [Official workshop program](https://roscon.org.es/roscon2026/ROSConES2026.html)

## Learning route

1. Understand the technology stack and why the physics engine is Newton.
2. Inspect ROS 2 nodes, topics, messages, QoS, parameters and simulation time.
3. Run a public MicroDuck asset in Isaac Lab/Newton, rendered through Isaac Sim.
4. Inspect observations/actions/rewards and run a short real RL training experiment.
5. Process actual onboard camera images with Isaac ROS 5.0.
6. Implement CASCADE observation and bounded-motion tools, then run the agent game.
7. Stop workshop processes and stop/delete the Brev instance when finished.

**Stopping a Docker container does not stop cloud billing.** Do not assume credits automatically shut an instance down.

## Technical and licensing boundaries

- **Newton only.** PhysX and MJLab are not fallback runtimes disguised as the requested stack.
- Isaac ROS **5.0 uses ROS 2 Lyrical** and native `rosidl::Buffer` support. Removed Isaac ROS 4.x NITROS package APIs are not the basis of this project.
- The actor and agent receive onboard-derived data. Simulator truth is confined to independent evaluation; there is no perfect-pose navigation or fake detector fallback.
- A short training exercise is not a claim that walking converges from scratch during the class. Public ONNX inference weights are not a full PPO training checkpoint.
- Pollen software and MJCF files are Apache-2.0; Pollen STL meshes and their derivatives are **CC BY-NC-SA 4.0**. Keep these terms and attribution separate. Third-party models/assets are fetched from pinned public sources rather than bundled or relicensed here.
- No private Creative/NVIDIA assets, private checkpoints, credentials, or physical-robot operation are included.

## Development checks available now

With Python 3.12 and pytest:

```bash
python -m pytest tests/test_contracts.py -q
```

This checks the fixed, simulation-only motion envelope and rejects malformed, nonfinite and extra-field requests. It does **not** test ROS transport or robot motion.

The implementation contract and current plan are in [the workshop specification](docs/superpowers/specs/2026-10-27-workshop.md) and [implementation plan](docs/superpowers/plans/2026-10-27-workshop.md).

# MicroDuck: ROS 2, reinforcement learning and physical-AI agents

**ROSCon España 2026 · 27 October · 15:00–17:00 · Valencia**

A two-hour, hands-on workshop using **ROS 2 Lyrical, NVIDIA Isaac ROS 5.0, Isaac Sim 6.2.0, Isaac Lab 3.0 and Newton**, ending with a real **CASCADE** agent controlling a simulated MicroDuck.

Participants work in **NVIDIA Brev**, using instructor-provided one-day credits on **L40S or RTX PRO**. No laptop GPU is required. Prepare downloads and environments before the two-hour session.

> **Readiness:** implementation, exercises and measured evidence are available. **Reliable uninstrumented camera → ROS → agent → Newton acceptance is still blocked.** A complete instrumented episode passed, but ordinary repetitions expired safely. Use the [current readiness record](verification/READINESS.md); CPU CI and native-only passes do not approve the motion lab.

## Official MicroDuck sources

- [Pollen MicroDuck runtime and SDK](https://github.com/pollen-robotics/microduck)
- [Pollen MicroDuck RL environments](https://github.com/pollen-robotics/microduck_rl) — **MJLab**, used as upstream reference, not the workshop simulator.
- [Official public policy set](https://huggingface.co/pollen-robotics/microduck-policies) — hosted on **Hugging Face**, not a GitHub policy repository.
- [CASCADE](https://github.com/johnnynunez/cascade) — physical-AI agent orchestration.
- [Official workshop program](https://roscon.org.es/roscon2026/ROSConES2026.html)

## Workshop materials

- [Student route and 120-minute agenda](docs/labs/README.md)
- [Before class: Brev preparation](docs/labs/00-before-class.md)
- [Instructor runbook](docs/instructor.md)
- [ROS 2 exercises](exercises/ros_basics/README.md) and [complete reference solution](solutions/ros_basics/README.md)
- [Troubleshooting](docs/troubleshooting.md)

The native step, real PPO, CUDA detector, portable local model, read-only preview and bounded Brev lifecycle are implemented. The latest joined-run outcomes, repaired safety boundaries and remaining availability issue are recorded separately in [release readiness](verification/READINESS.md). Earlier failed velocity and integrated attempts are retained rather than relabeled as success.

- [Isaac Lab/Newton runtime and real PPO exercise](docs/runtime.md)
- [Isaac ROS 5.0 setup and actual CUDA detector evidence](docs/isaac_ros.md)
- [CASCADE capstone implementation and evidence limits](docs/capstone.md)
- [Calibration results — currently NOT READY](docs/calibration.md)
- [Brev setup and cloud lifecycle](docs/brev.md)
- [Fixed step: native results and exact semantics](docs/step.md)
- [Native verifier/renewal safety fixes and fresh confirmation](docs/native_fences.md)
- [Portable local Qwen3.8 model](docs/local_model.md)
- [Read-only browser preview](docs/preview.md)

The read-only ROS exercises do not bypass the motion gateway.

## Learning route

1. Understand the technology stack and why the physics engine is Newton.
2. Inspect ROS 2 nodes, topics, messages, QoS, parameters and simulation time.
3. Run a public MicroDuck asset in Isaac Lab/Newton, rendered through Isaac Sim.
4. Inspect observations/actions/rewards and run a short real RL training experiment.
5. Process actual onboard camera images with Isaac ROS 5.0.
6. Implement CASCADE observation and fixed-step tools, then run the agent game.
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

```bash
# Small CPU-only environment, not the simulator or ROS installation.
uv sync --extra policy --extra agent --group dev
uv run --no-sync pytest -q
uv run --no-sync python -m microduck_workshop.doctor

# Review the mesh license and your permissions before acknowledging it.
uv run --no-sync python -m microduck_workshop.assets fetch --accept-mesh-license
```

The downloader admits **121 public files** by exact pinned URL, size and SHA-256, including **43 separately licensed STL meshes** and the public VelStand v8 ONNX. Files remain in the ignored `.cache/assets/` directory. A corrupt cache entry is refused, not silently replaced. Transient GET retries are bounded; motion requests never inherit this retry behavior.

The CPU suite checks command bounds, malformed/nonfinite values, asset admission and conservative version classification. `doctor` reports the packages and import origin in **its own interpreter** and explicitly does not claim to run the simulator or ROS. Isaac Lab's internal package version is not its product release; the GA source identity is checked separately. These checks do **not** prove robot motion, live detection, a real agent episode, or Brev deployment.

GitHub Actions runs CPU contracts only. Runtime readiness remains separate.

The implementation contract and current plan are in [the workshop specification](docs/superpowers/specs/2026-10-27-workshop.md) and [implementation plan](docs/superpowers/plans/2026-10-27-workshop.md).

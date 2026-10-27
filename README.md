# MicroDuck: ROS 2, reinforcement learning and physical-AI agents

**ROSCon España 2026 · 27 October · 15:00–17:00 · Valencia**

A two-hour, hands-on workshop using **ROS 2 Lyrical, NVIDIA Isaac ROS 5.0, Isaac Sim 6.2.0, Isaac Lab 3.0 and Newton**, ending with a real **CASCADE** agent controlling a simulated MicroDuck.

Participants work in **NVIDIA Brev**, using instructor-provided one-day credits on **L40S or RTX PRO**. No laptop GPU is required. Prepare downloads and environments before the two-hour session.

> **Release candidate — not full-course acceptance.** All six notebooks and the teaching guide are implemented. Notebooks 01–03 have real local execution evidence, and the ROS stall repair has independently audited GO/STOP results after 65 seconds idle. **The current full-course rehearsal is blocked at Notebook 04:** its offline training container cannot retrieve the SDK ground asset;05–06 were not executed. Follow the [current readiness record](verification/READINESS.md), preserve the failed attempt, and do not label this a complete classroom or Brev/L40S pass.

## Official MicroDuck sources

- [Pollen MicroDuck runtime and SDK](https://github.com/pollen-robotics/microduck)
- [Pollen MicroDuck RL environments](https://github.com/pollen-robotics/microduck_rl) — **MJLab**, used as upstream reference, not the workshop simulator.
- [Official public policy set](https://huggingface.co/pollen-robotics/microduck-policies) — hosted on **Hugging Face**, not a GitHub policy repository.
- [CASCADE](https://github.com/johnnynunez/cascade) — physical-AI agent orchestration.
- [Official workshop program](https://roscon.org.es/roscon2026/ROSConES2026.html)
- [NVIDIA MicroDuck AI-agent workflow](https://developer.nvidia.com/blog/using-ai-agents-to-teach-robots-like-microduck-to-walk-in-simulation/) — [how it maps to this workshop](docs/nvidia_workflow_context.md), separating engineering agents, RL training, and runtime CASCADE orchestration.

## Workshop materials

- **[Start here: six executable Jupyter notebooks](notebooks/README.md)**
- **[Instructor speaking, questions and recovery guide](docs/notebook_instructor.md)**
- [Before class: Brev preparation](docs/labs/00-before-class.md)
- [Terminal-based reference labs](docs/labs/README.md) and [technical instructor reference](docs/instructor.md)
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

Keep the instructor's existing 15-minute introduction. Then follow this notebook sequence:

1. **[ROS 2](notebooks/01_ros2.ipynb)** — nodes, typed topics, publishers and subscribers.
2. **[Isaac ROS 5.0](notebooks/02_isaac_ros_5.ipynb)** — load and inspect the CUDA perception component; camera input arrives in the next stage.
3. **[MicroDuck in Isaac Sim 6.2.0](notebooks/03_microduck_isaac_sim_6_2.ipynb)** — Newton physics, actual onboard images and ROS sensors.
4. **[Train with Isaac Lab 3.0](notebooks/04_train_isaac_lab_3.ipynb)** — short actor warm-start PPO training, your checkpoint and actual exported ONNX.
5. **[Policy inference](notebooks/05_policy_inference.ipynb)** — evaluate and admit that exact export, then load it in Isaac Sim; no pretrained substitution.
6. **[CASCADE with your policy](notebooks/06_cascade_policy_agent.ipynb)** — implement the adapter, run a local-agent attempt and inspect the independent verdict for the same admitted policy.

The notebook timeboxes are 15/15/15/20/15/20 minutes, followed by five minutes of mandatory shutdown. Setup and image/model downloads happen before the class. A short fine-tuning run is not a promise of converged walking from scratch, and an admission failure does not trigger a hidden fallback.

For a host already configured for NVIDIA CDI, set `WORKSHOP_GPU_SELECTOR=cdi` and the assigned numeric `WORKSHOP_GPU` before starting Jupyter. Otherwise the explicit default is Docker's `--gpus device=N` selector. Unknown selectors fail; no silent device fallback is attempted. This is host configuration, not evidence that a particular cloud instance was tested.

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
# CPU software/notebook checks, not the simulator or ROS installation.
uv sync --extra policy --extra agent --group dev
uv pip install --python .venv/bin/python -r requirements-notebooks.txt
uv run --no-sync pytest -q
uv run --no-sync python -m microduck_workshop.doctor

# Review the mesh license and your permissions before acknowledging it.
uv run --no-sync python -m microduck_workshop.assets fetch --accept-mesh-license
```

The downloader admits **121 public files** by exact pinned URL, size and SHA-256, including **43 separately licensed STL meshes** and the public VelStand v8 ONNX. Files remain in the ignored `.cache/assets/` directory. A corrupt cache entry is refused, not silently replaced. Transient GET retries are bounded; motion requests never inherit this retry behavior.

The CPU suite checks command bounds, malformed/nonfinite values, asset admission and conservative version classification. `doctor` reports the packages and import origin in **its own interpreter** and explicitly does not claim to run the simulator or ROS. Isaac Lab's internal package version is not its product release; the GA source identity is checked separately. These checks do **not** prove robot motion, live detection, a real agent episode, or Brev deployment.

GitHub Actions runs CPU contracts only. Runtime readiness remains separate.

The implementation contract and current plan are in [the workshop specification](docs/superpowers/specs/2026-10-27-workshop.md) and [implementation plan](docs/superpowers/plans/2026-10-27-workshop.md).

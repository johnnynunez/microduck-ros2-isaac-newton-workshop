# NVIDIA Brev: full one-day workshop environment

**No paid instance or Launchable has been created by this repository.** Local RTX PRO execution is not a Brev/L40S receipt. The instructor must check availability, rates, one-day credit coverage and expiry in the Brev Console before authorizing deployment.

## Architecture and resource budget

| Process | Environment | Budget / boundary |
| --- | --- | --- |
| `sim` | Public Ubuntu 24.04, Python 3.12; Isaac Lab **v3.0.0** source `e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4`; Isaac Sim **6.2.0.0**, Newton **1.6.1**, MuJoCo-Warp **3.12**, Warp **1.17**, Torch **2.11 cu130** from Lab's frozen lock | 32 GiB RAM, 8 CPU; one selected GPU; `graphics,compute,utility` driver capabilities |
| `ros` | Signed NVIDIA Isaac ROS 5 / ROS 2 Lyrical packages in a separate Noble container | 24 GiB RAM, 8 CPU; GPU compute; domain 27, LOCALHOST DDS |
| `agent` | CASCADE public commit + OpenAI-compatible client in the **Lyrical Python 3.12 venv**, real rclpy/interfaces | 4 GiB RAM, 2 CPU; explicit student invocation, no GPU reservation |
| Local model | Pinned llama.cpp / Qwen deployment from [local_model.md](local_model.md) | Separate process; loopback **8080**; check measured combined VRAM before starting |
| `preview` | GET-only human overview proxy | 256 MiB RAM, 1 CPU; loopback **8765**; no control endpoint proxy |

Lab's distribution reports `isaaclab 28.0.0`: this is not the product version. Lab owns Newton physics; Sim supplies conversion/rendering. Never source Sim's bundled ROS/Jazzy libraries into the Lyrical process. The Sim image upgrades Pillow to **13.0.0** after Lab resolution; do not run `uv sync` afterwards and silently undo the security overlay.

ROS and the agent share **only the ROS container's private IPC namespace** (`ipc: shareable` / `ipc: service:ros`). Fast DDS with host networking otherwise discovers the service but can time out sending requests between isolated shared-memory namespaces. The host and Sim IPC namespaces remain isolated. Do not replace this with `ipc: host` or privileged mode. Start the gateway before using the agent profile.

Choose a single **L40S (48 GB)** or **RTX PRO** GPU, at least 64 GiB host RAM (96 GiB recommended for headroom), and **at least 200 GiB storage**, preferably more for retained BuildKit caches. These are workshop planning recommendations, not a guarantee that every offered SKU fits. GPU VRAM is **not** capped by Docker RAM limits. On a 48 GB GPU, sequence the short PPO exercise and local model; do not train while the LLM and rendered capstone are loaded. Start with `WORKSHOP_GPU=0` on a one-GPU VM.

## Real Launchable fields (instructor only)

Use the current [Launchables builder](https://docs.nvidia.com/brev/concepts/launchables) and [custom-container guide](https://docs.nvidia.com/brev/guides/development-tools/custom-containers), not an invented provisioning API or Launchable ID.

| Builder section | Value |
| --- | --- |
| Details | MicroDuck ROSCon España 2026; simulation-only, noncommercial mesh terms, two-hour lesson and one-day credit window |
| Default hardware | L40S or RTX PRO; check driver, VRAM, RAM, storage, region, availability and price |
| Software | **VM Mode** with CUDA, Docker/Compose and NVIDIA Container Toolkit; use the setup below. The local-model build also needs its documented CUDA compiler/CMake/Ninja prerequisites |
| Source | The instructor's **actual published repository URL and immutable commit**; do not substitute a guessed URL |
| Network | No public DDS, model 8080, or simulator control 8766. Only the human preview 8765 may receive a Brev-authenticated Secure Link; otherwise use an SSH forward |
| Launch parameters | Nonsecret `WORKSHOP_GPU=0`, `ROS_DOMAIN_ID=27`, optional exact image references. Never preset license acceptance for attendees |
| View access | Instructor chooses organization/link-only/public. Copy the real badge/link from Console only after creation |

Compose mode accepts an uploaded file or GitHub/GitLab URL. It is **not** the reference bootstrap here: `compose.yaml` references locally built images and repository-local volumes. For a URL-only Compose Launchable, first publish tested image digests and arrange the asset/config volumes explicitly. A relative build context or local tag does not magically become available in Brev.

## Prepare everything BEFORE the 120-minute class

ROSCon España · 27 October 2026 · 15:00–17:00 Europe/Madrid · Aula 2-7. The first
15 minutes use the instructor's own technology/Newton slides; setup is not part of this clock.

Large wheels, shader compilation, vendor groundplane/MDL loading, public assets and model weights are preparation work, not student exercise time. Use a fresh checkout of the final merged commit. Keep at least one full rehearsal buffer; network failures can require retries.

1. Run the read-only host gate and inspect inventory:

   ```bash
   bash scripts/brev_preflight.sh
   nvidia-smi
   docker build --help    # this recipe requires BuildKit's --resource limits
   ```

   Driver **595+** is required by this ROS 5 stack. Do not install/downgrade host drivers automatically; select a compatible Brev environment. Use signed Ubuntu/NVIDIA packages, never `trusted=yes` or unauthenticated apt. If the supplied Docker/Buildx lacks `--resource`, update it through the instance owner's approved installation procedure; do not drop resource limits silently.

2. Review the [NVIDIA Isaac Sim terms](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_python.html), repository `NOTICE`, and Pollen's pinned CC BY-NC-SA mesh license. Only an authorized operator who accepts both should run:

   ```bash
   export WORKSHOP_GPU=0 ROS_DOMAIN_ID=27
   bash scripts/brev_setup.sh --accept-nvidia-eula --accept-mesh-license
   ```

   This builds the signed-package ROS base if missing; rebuilds current workshop/ROS/provenance/CASCADE source layers; checks the actual CASCADE API; builds the clean Sim/Lab image; fetches the public robot and ONNX through the hash-checking asset CLI; renders a bounded zero-intent camera warmup; and invokes `model_setup.sh` plus its offline verification. **A missing model lane is an error, not a full-setup success.** No hosted API key is needed.

   Repeated setup reuses Docker layers and verifies existing asset bytes. Warmup starts only if loopback 8766 is free, and always removes its own temporary container. Downloads and derived conversion/output caches belong to this checkout. No host SDK or another checkout's writable asset cache is mounted. Optional instructor acceleration: set `WORKSHOP_UV_CACHE` to a **private, trusted copy** of a compatible uv package cache; this seeds BuildKit without changing the source cache. It is not required by the public download recipe.

   Setup requires explicit flags each time; `OMNI_KIT_ACCEPT_EULA=YES` is set only for the accepted invocation, never baked into the image or provided as an attendee default. Save nonsecret GPU/image selections in a local `.env` if desired; Brev launch-time environment values do not automatically appear in later SSH shells.

3. Inspect `.workshop/receipts/`, `.workshop/sim-output/warmup/evaluation.json`, and the **actual** `.workshop/receipts/head.jpg`. A clean Kit exit is insufficient: warmup requires Newton steps, real runtime identity and a JPEG fetched from the native camera endpoint. Keep native-camera validation separate from the CUDA AprilTag acceptance in the ROS lesson. The rendered tag's black-border size is **0.20 m**; Compose overrides the official bag example's different 0.22 m value.

4. Prepare a separate **host CPU exercise environment** (no ROS libraries or GPU needed):

   ```bash
   python3.12 -m venv .workshop/student-venv
   .workshop/student-venv/bin/python -m pip install -e . -r requirements-agent.txt pytest==9.1.1
   PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .workshop/student-venv/bin/python -m pytest --noconftest \
     tests/test_curriculum_docs.py tests/test_curriculum_ros_basics.py \
     tests/test_curriculum_ros_node.py -q
   .workshop/student-venv/bin/python scripts/agent_check_exercise.py --tools-file solutions/capstone/tools.py
   ```

   These checks use CPU fixtures, not a live ROS/model/physics stack. Students edit the host
   `exercises/` directory; Compose mounts those edits read-only for the observer/agent.
   Do not make the class pip-install packages in the simulation interpreter.

5. Complete the ROS DDS/AprilTag and local-model rehearsal before admitting students.
   Keep receipts labeled by host/GPU. A successful official bag test is not a live MicroDuck
   perception test. Rehearse the full positive motion gate and a separate STOP episode
   on the actual student SKU; otherwise retain the motion lesson's explicit blocked route.

On a shared development workstation, launch setup/simulation through its memory-capped job wrapper (for example `heavyrun -n roscon-brev-setup -m 32G -g 1 -- bash scripts/brev_setup.sh ...`). Docker workloads carry their own limits because dockerd children are outside the wrapper's cgroup. Do not run two workshop stacks on the same loopback ports.

## Start the live session

1. In one terminal, use the model lane's actual foreground launcher after setup:

   ```bash
   MODEL_GPU=0 MODEL_PORT=8080 bash scripts/model_start.sh
   ```

   Follow [local_model.md](local_model.md) for its supported supervision and stop procedure. Confirm `http://127.0.0.1:8080/v1/models` lists the intended classroom model. Model initialization must finish **before** the gateway's one-shot control claim. No mock/hosted fallback is selected.

2. In another terminal, explicitly start a **new operator-authorized episode**:

   ```bash
   WORKSHOP_GPU=0 bash scripts/brev_start.sh --accept-nvidia-eula
   ```

   The script checks the model, starts Sim at zero velocity intent, waits for actual Newton health and head JPEG, then starts ROS and the human preview. It does **not** run an agent, send motion, automatically reset a stop, or restart crashed containers. Starting while a simulator is running is refused. The default is a bounded **180000 control steps** (nominal one hour at 50 Hz). Explicit `WORKSHOP_SIM_STEPS=0` selects serve-until-signal; it is not the classroom default or a two-hour soak claim. Schedule an explicit operator stop/new episode between class segments if needed. Use `WORKSHOP_TAG_ID=1` at a new episode launch for the authored STOP board.

3. Verify real ROS admission, not merely `docker compose ps`:

   ```bash
   docker compose exec -T ros bash /opt/workshop/entrypoint.sh \
     ros2 service call /workshop/microduck/observe microduck_workshop_interfaces/srv/Observe '{}'
   docker compose exec -T ros bash /opt/workshop/entrypoint.sh \
     ros2 param get /workshop/microduck/apriltag size
   ```

   Require fresh, same-episode detections from the live head image and correct optical frame. A stale/absent observation must refuse movement. Initialization and asset/model downloads must not occur after taking the motion lease. A latched stop requires the operator to stop this stack and intentionally start a new episode; never have the agent retry/re-arm.

4. Compose now explicitly enables **`--step-profile step-forward-v1`**, whose native
   validation is in [step.md](step.md). The old direct velocity API is unchanged;
   [constant-velocity calibration](calibration.md) remains **FAILED / NOT_READY**.
   Native step validation alone is **not full motion-capstone admission**: check the
   [release's same-episode acceptance](../README.md) before teaching
   [Lab 5's fixed action](labs/05-cascade.md). Do not teach numeric `walk_bounded` as its substitute.

   To check deployment plumbing without motion, confirm the observed episode/frame and
   use a **new** output directory:

   ```bash
   EPISODE=$(python3 -c 'import json,urllib.request; print(json.load(urllib.request.urlopen("http://127.0.0.1:8766/v1/health"))["episode_id"])')
   docker compose run --rm --no-deps --workdir /opt/workshop agent python -m microduck_workshop.agent.run \
     --base-url http://127.0.0.1:8080/v1 --model qwen3.8-27b \
     --episode-id "$EPISODE" --frame-id microduck_head_optical \
     --max-steps 2 --run-dir /outputs/student-run-01 \
     --task 'Observe the signal once. Do not request motion. Finish with success=false: this is a deployment plumbing check, not an admitted locomotion capstone.'
   ```

   This diagnostic deliberately uses production handlers and can exit **2** with
   `success=false`; that is not a physical task pass. It also latches stop on runner
   teardown. Stop/restart the owned stack for a new operator-authorized episode before
   the class game. Students explicitly select their file as shown in
   [Lab 5](labs/05-cascade.md), not an implicit reference fallback. An ACK or final model
   sentence is never a substitute for the same-request independent verdict.

## Human browser view

Forward **only 8765**, for example through Brev's SSH workflow with `-L 8765:127.0.0.1:8765`, and open `http://127.0.0.1:8765`. The preview serves static HTML/JS/CSS, actual head/overview JPEGs and an allowlisted status summary only; control paths are rejected and POST is unsupported. A Secure Link is acceptable only after verifying its authenticated proxy reaches this loopback listener. Never solve access by opening 8766, 8080 or DDS to all IPs. The overview is not agent perception.

## Short fresh PPO exercise

Stop the agent, gateway, live Sim and model first, especially on L40S. Confirm VRAM is free enough. After reviewing/accepting the EULA for this shell:

```bash
bash scripts/brev_stop.sh
export OMNI_KIT_ACCEPT_EULA=YES WORKSHOP_GPU=0
docker compose run --rm --no-deps --name roscon-brev-train sim \
  -m microduck_workshop.sim.train --asset-root /assets \
  --updates 4 --horizon 32 --seed 7 --output /outputs/train-class-01
```

Read `.workshop/sim-output/train-class-01/training_receipt.json`; use a fresh output name on a repeat. Require nonzero optimizer/weight changes and a checkpoint roundtrip. This is fresh PPO over real Lab/Newton transitions, **not** resuming the public ONNX, and four updates do not establish a converged gait. Keep outputs local; source meshes and derived USD remain under their upstream licenses. Restart the model, then explicitly start a new live episode when returning to the capstone.

## Shutdown and billing checklist

- [ ] Stop the agent and issue the priority emergency stop; ACK is not proof of rest.
- [ ] Run `bash scripts/brev_stop.sh`. It stops this Compose project and the supported model stop script if present. If the model is running in its own foreground terminal, stop it there and verify its process/GPU allocation is gone.
- [ ] Confirm `docker compose --profile agent ps -a` has no running workshop services; verify `nvidia-smi` against your owned processes. Never kill unrelated services.
- [ ] Export code and small receipts, not licensed meshes/model caches by accident.
- [ ] In the **Brev Console stop the instance and verify its stopped state**. Closing a browser, SSH session or Docker container does not stop VM billing.
- [ ] Delete the instance and unwanted persistent storage when appropriate, after reviewing the Console's confirmation. Stopped compute may still incur storage charges.
- [ ] Instructor checks credit balance and confirms no workshop VM is left running beyond the one-day credit window. No automatic cloud deletion is performed.

## Execution scope

Local RTX PRO container verification exercised the real path, not only image imports:

- Public asset CLI downloaded and hash-verified **121 files**; a repeated fetch verified them with **zero downloads**.
- Isaac Sim 6.2 / Lab GA / Newton reset and **800 physics steps** preserved 15 bodies and 28 joint coordinates. The actual head JPEG showed the tag board. An in-Kit probe confirmed **Pillow 13.0.0** and its compiled imaging module during capture.
- Fresh PPO performed **512 Newton steps, four updates and 16 optimizer steps**, nonzero weight changes and checkpoint reload. This is not a converged gait.
- The rebuilt Lyrical/CASCADE containers, private shared IPC, real CUDA tag detector and local Qwen completed a **no-motion observation check**: CASCADE received fresh tag 0 from the native head camera. The report deliberately had `success=false` because no physical capstone action was requested or verified.
- `brev_start.sh` / `brev_stop.sh`, real preview JPEG, rejected control paths and rejected POST were exercised. Source/cache warmup and six deployment-contract tests passed. Original network-download, missing-libXt and cross-container DDS failures were retained during development and fixed rather than masked.

The Sim build used a private copy of a trusted package cache after cold public wheel
downloads timed out. The composed no-motion check used the existing local Qwen endpoint
(18510). Separately, the [portable GGUF lane](local_model.md) ran actual llama.cpp/Qwen
tool calls on RTX PRO and compiled SM 89/120a code; those model-only checks used synthetic
STOP, not live camera input. Neither result establishes the full portable-model motion
path on a Brev VM. Rehearse the **final merged image and model together** on the advertised
SKU; retain the actual image/package/model receipts. These are not cold-network or
cloud-certification claims.

Record `local RTX PRO`, `Brev RTX PRO` and `Brev L40S` separately. Local image builds and native smokes do not establish cloud provisioning, credit allocation, Secure Link operation, L40S memory/performance, or a physically verified capstone. Those remain explicit instructor rehearsal gates.

# Before class — arrive ready to observe, not to install

**Before 15:00 · Aula 2-7. Setup/download/build time is outside the 120-minute lesson.**

## What you need

- A laptop with a browser and SSH terminal or VS Code remote connection. Your laptop does not need a GPU.
- Your instructor's Brev access and **one-day credit** instructions; a prepared **L40S or RTX PRO** instance.
- The public workshop checkout at the instructor's tested commit. Do not update it during class.
- The instructor must finish [Brev preparation and rehearsal](../brev.md) first: images, public assets,
  shaders, ROS interfaces, the CPU exercise environment and the local Qwen3.8 model.

The target is Ubuntu 24.04, Python 3.12, Isaac Sim **6.2.0.0**, Isaac Lab **3.0**
(source `e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4`), Newton **1.6.1**, Isaac ROS **5.0**
and ROS 2 **Lyrical from NVIDIA's buildfarm**. Sim and ROS use separate containers.
The [README's release evidence](../../README.md) determines which live stages are admitted;
local RTX PRO evidence does not establish Brev or L40S execution.

## 1. Know what you are downloading

Read [NOTICE](../../NOTICE), [the source manifest](../../provenance/sources.json) and
[the policy contract](../../provenance/policy_contract.json).

- Pollen software/MJCF: **Apache-2.0**. Meshes and converted derivatives: **CC BY-NC-SA 4.0**.
  Fetch separately, acknowledge the mesh terms explicitly, and retain attribution.
- Public VelStand v8 ONNX: an inference policy, **not a full PPO resume checkpoint**.
  The native fixed-step validation does not make arbitrary velocity commands valid.
- Portable Qwen3.8 GGUF: separately downloaded Apache-2.0 model; pinned llama.cpp: MIT.
- MJLab is the upstream training reference, **not** our runtime. No private teacher checkpoints
  or Creative/NVIDIA assets are needed. Do not bypass a license or hash failure.

## 2. Prepare the terminals

All **host** commands run in your checkout on the Brev instance, not on your laptop.
Keep the following terminal roles separate:

| Terminal | Purpose |
|---|---|
| Host/editor | Edit files, run `.workshop/student-venv/bin/python` CPU checks, start/stop Compose |
| Model | Keep the foreground `model_start.sh` process running; do not close it accidentally |
| ROS tools | Inspect the existing gateway through its Lyrical container |

Staff start the model and a new zero-intent episode using [the exact start sequence](../brev.md#start-the-live-session).
Do not launch a second simulator. In a host terminal:

```bash
git rev-parse HEAD
.workshop/student-venv/bin/python --version
docker compose ps
```

Open a **ROS tools terminal** with this command from a host terminal:

```bash
docker compose exec --workdir /opt/workshop ros   bash /opt/workshop/entrypoint.sh bash --noprofile --norc
```

This sources the correct Lyrical underlay and built workshop overlay. Inside it:

```bash
printenv ROS_DISTRO ROS_DOMAIN_ID
ros2 pkg prefix microduck_workshop_interfaces
ros2 interface show microduck_workshop_interfaces/srv/Observe
ros2 topic list -t
```

Expect `lyrical`, domain `27` unless staff configured another domain, and a resolving
Observe type. A package name is not proof of a running node. Use `exit` to return to the
host. After staff stop/recreate the stack, open a **new** ROS tools terminal this way.
Never source Sim's bundled ROS/Jazzy libraries into this shell.

## 3. Check the real path

Before the lesson, show staff:

- Actual `/clock`, encoder and IMU samples from the single Lab/Newton owner.
- Actual onboard RGB and matching calibration, plus the separate human overview.
- A live Isaac ROS observation with the current episode and optical frame.
- The locally served Qwen3.8 model ready; no agent is launched automatically.

Use the instructor's authenticated preview link, or the approved SSH forward of
**8765 to 127.0.0.1:8765**, then open `http://127.0.0.1:8765` on your laptop.
The [preview](../preview.md) is read-only: LIVE means fresh source imagery, not task success.
Keep simulator control **8766**, model **8080**, and DDS private. `ROS_DOMAIN_ID` is not authentication.

## 4. Put shutdown on your calendar now

Record the credit expiry and set a reminder **before the one-day / 24-hour expiry**.
Locate Brev's stop/delete control now. Stopping a container or exhausting credits does not
prove that VM/storage billing stopped. Follow [the shutdown checklist](06-wrap-up.md).

## Checkpoint

Before 15:00, show your revision, real joint-state and `/clock` samples, private preview,
and the cloud stop/delete control. Mark missing runtime evidence **blocked**, not ready.

Next: [student route](README.md) and [ROS basics](01-ros-basics.md).

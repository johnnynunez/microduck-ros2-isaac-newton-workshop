# Six-notebook MicroDuck course

**Readiness: the complete local reference rehearsal passed—six notebooks, 39 code cells, and an independently verified same-policy CASCADE motion.** [Evidence and limits](../verification/notebook-course-final.json). This remains **NOT READY for unattended live motion**: the instructor must approve the selected instance and policy, all live switches start false, and Brev/L40S hardware remains unverified. A notebook validator alone is not physical acceptance.

Use the instructor's own opening slides, then these notebooks in this exact order:

| Notebook | Time | What you actually establish |
|---|---:|---|
| [01 — ROS 2](01_ros2.ipynb) | 15 min | Real isolated typed publisher/subscriber graph |
| [02 — Isaac ROS 5](02_isaac_ros_5.ipynb) | 15 min | Real CUDA detector loaded; no camera or invented detections yet |
| [03 — MicroDuck / Isaac Sim 6.2](03_microduck_isaac_sim_6_2.ipynb) | 15 min | Real Newton owner, rendered onboard image and ROS sensors |
| [04 — Isaac Lab 3 training](04_train_isaac_lab_3.ipynb) | 20 min | Actual warm-start PPO updates and your checkpoint/export identity |
| [05 — Policy inference](05_policy_inference.ipynb) | 15 min | The exact Notebook04 actor, real image and independent admission |
| [06 — CASCADE and that policy](06_cascade_policy_agent.ipynb) | 20 min | Student adapter, actual local model/ROS attempt, independent verdict |

Together with 15 minutes of existing slides and five minutes of shutdown, this is the 120-minute course. [Instructor speaking and recovery guide](../docs/notebook_instructor.md).

## Prepare before class

The Docker images, licensed assets, drivers and local model are prepared through the existing [Brev instructions](../docs/brev.md). The host must provide `uv`; preparation checks this before building images. This setup does not provision paid cloud resources or accept licenses for you. The host Jupyter kernel is **not** the ROS or Kit interpreter.

```bash
bash scripts/notebook_setup.sh
bash scripts/notebook_start.sh --check
bash scripts/notebook_start.sh
```

The server binds **127.0.0.1**, requires a random token and does not open a browser. Jupyter may **redact the token in `server.log`**; that redacted URL cannot authenticate you. After starting the server, run this in a **second private terminal on the same host/checkout**, with the same `WORKSHOP_NOTEBOOK_RUNTIME` override if you used one:

```bash
bash scripts/notebook_start.sh --url
```

This reads the actual mode-0600 config and prints the usable authenticated loopback `/lab?token=...` URL **only to that terminal**. It does not rotate the token or overwrite the running server's config. Do not run it in a notebook cell, shared log, projected terminal or chat; do not paste its output into screenshots or source control. Use your authenticated SSH tunnel (`ssh -L 8888:127.0.0.1:8888 YOUR_INSTANCE`) and open the locally forwarded URL. If your tunnel uses a different local port, change only the URL's port to that local port. Do not expose Jupyter, DDS, the model or simulator control on a public interface. `WORKSHOP_NOTEBOOK_PORT` changes the loopback port; no public-bind override is supported.

On a shared workstation use the host's memory-capped supervisor from a **terminal**, for example:

```bash
heavyrun -n roscon-notebooks-jupyter -m 4G -- bash scripts/notebook_start.sh
```

Docker has its own CPU/RAM caps because its child workloads do not inherit that host cgroup. On a single L40S, sequence training and model serving; do not co-load them. Ask staff which physical GPU is yours. No automatic process stealing, stop/rearm, motion retry or model fallback occurs.

Optional **nonsecret** environment overrides, set before starting Jupyter:

- `WORKSHOP_ROS_IMAGE`, `WORKSHOP_SIM_IMAGE`, `WORKSHOP_AGENT_IMAGE`: prepared image references.
- `WORKSHOP_ASSET_ROOT`: verified public asset directory (default `.cache/assets`).
- `WORKSHOP_GPU`: one physical GPU index (default `0`).
- `WORKSHOP_ROOT`: checkout discovery override; normally unnecessary.
- `WORKSHOP_NOTEBOOK_WORK`: private state/log/output directory (default `.workshop/notebooks`). Keep it private and stable across notebooks.
- `WORKSHOP_NOTEBOOK_PREFIX`, `WORKSHOP_ROS_DOMAIN`: staff-assigned container prefix and ROS domain (defaults `roscon-nb` and71). Keep them unchanged until owned cleanup. A distinct DDS domain does not make native port8766 shareable.
- `WORKSHOP_MODEL_URL`: prepared local model endpoint (default `http://127.0.0.1:8080/v1`); loopback only, no hosted fallback.
- `WORKSHOP_SIM_STARTUP_TIMEOUT`: finite seconds in `(0, 1800]`, default **600**, for bounded read-only native/state/camera startup readiness. This never changes the **0.5-second capture or lease** bounds, training/admission deadlines, motion budgets or evaluator thresholds. All native serving episodes in03/05/06 use it.

Images must actually contain the student-policy API.04 probes shipped `train`, `admit_policy` and `play` help before overlays and requires `onnx==1.22.0`;06 probes **`microduck_workshop.agent.run`**. An older image tag is not evidence of capability. Staff can select explicitly built private `:student-candidate` images during integration; those tags do not imply a public download or live acceptance.

**Online SDK assets are required for04 training and05 admission.** These native jobs explicitly use Docker `--network bridge` for outbound DNS/HTTPS to NVIDIA's public asset server (`omniverse-content-production.s3-us-west-2.amazonaws.com`), with no published ports and no host networking. The pinned Isaac Lab SDK retrieves its default ground USD and dependencies into each container's temporary directory;03's persistent session HOME warmup does **not** make subsequent containers offline-ready. Keep the actual ground and physics unchanged. A blocked download is a setup failure, not a training/admission result. Capability, identity and adapter-test jobs retain `--network none`; existing loopback serving/ROS networking is unchanged.

## Your exact artifact, not a pretrained replacement

04 produces a new run containing `checkpoint.pt`, changed `actor.onnx`, `policy_manifest.json`, `training_receipt.json` and actual transitions.05 re-hashes that bundle and performs native admission **before serving**, as required by the implemented API. Both the full run and full admission/raw-trace directories mount read-only; receipt snapshots alone cannot deploy a policy.

06 rechecks the same checkpoint/export/manifest/admission, tests the actual student adapter (or an explicitly chosen reference), verifies the local model before a gateway lease, and starts a fresh Sim episode. It persists one-attempt ownership before dispatch and records actual provider/report evidence. These are identity and audit checks, not permission to weaken capture/lease/rest gates. The06 checkpoint records an attempt requiring independent audit, never automatically a successful task.


## Run cells deliberately

Every notebook begins with objectives and a prediction. Run one cell, inspect the actual result, then do the small task. Hardware actions default to **off**. Set only the named opt-in switches after their prerequisites and license review. `WORKSHOP_NOTEBOOK_MODE=validate` forcibly skips hardware even if a switch was edited; it never claims a live pass. The real ROS CPU rehearsal uses `WORKSHOP_NOTEBOOK_MODE=cpu` for Notebook01 only.

`notebooks/workshop.py` prints the exact Docker commands and applies bounded waits. Its helpers are ordinary host orchestration, not hidden motion controllers. You can read every command. ROS libraries remain in their image; Kit remains in the simulator image. Private checkpoint state detects out-of-order work and changed artifacts. A kernel restart preserves Docker and disk state; it does not reset the robot or reauthorize motion.

Native health can become ready **before the first camera frame exists**. The helper waits for fresh same-episode state, camera calibration and the actual JPEG/capture headers before reporting serving readiness, displaying a snapshot or starting a gateway. It preserves original capture timestamps; missing/stale input remains BLOCKED at the deadline. These are read-only polls, not motion retries. Notebook03's normal full Gateway **does claim a lease** when its ROS cell starts; this sensor lesson is not capstone admission. Before class, rehearse with the **same session's `sim-home`**, not another worker's cache; see the [session-specific prewarm procedure](../docs/notebook_instructor.md#session-specific-cold-start-rehearsal).

If a cell fails, keep its log and run the owned cleanup cell. Do not use Run All to bypass a failed checkpoint. If a motion send is uncertain, do not retry. A new episode requires explicit cleanup and operator authorization; old episode/frame/lease state is invalid.

## Verification and privacy

```bash
.workshop/notebook-venv/bin/python -m pytest tests/test_notebooks*.py -q
RUN_NOTEBOOK_ROS=1 WORKSHOP_ROS_IMAGE=roscon/microduck-ros5:local \
  .workshop/notebook-venv/bin/python -m pytest \
  tests/test_notebooks_execution.py::test_nbclient_ros_tutorial_actual_pub_sub -q
```

Executed notebooks are written to `.workshop/executed/`, logs and actual artifacts to `.workshop/`. These are private and git-ignored. The six public notebooks must have **no outputs or execution counts**. Do not commit tokens, local paths, model weights, large JPEG outputs or your executed notebook copy. Retain failed runs as failures, rather than replacing their receipts.

Coverage categories must remain separate: **CPU-only**, **recorded**, **live-local**, **SKIPPED**, **BLOCKED**, and **cloud-unverified**. No source fixture is live pipeline evidence. No local RTX PRO run proves Brev/L40S availability or performance.

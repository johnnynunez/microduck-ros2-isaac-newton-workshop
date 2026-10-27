# Native runtime (development evidence)

The runtime is **Isaac Lab v3.0.0 owning Newton 1.6.1 / MuJoCo-Warp 3.12.0**, with Isaac Sim 6.2.0.0 supplying conversion and rendering. It does not start Sim's separate Newton physics engine. The GA tag's installed Python distribution reports `isaaclab 28.0.0`; that is not the product release number.

## Setup

Use the published GA tag, a clean Python 3.12 environment, and its own dependency resolution:

```bash
git clone --branch v3.0.0 --depth 1 https://github.com/isaac-sim/IsaacLab.git
cd IsaacLab
uv sync --extra isaacsim
# Set REPO to this workshop's absolute checkout path.
uv pip install --python .venv/bin/python -e "$REPO" -r "$REPO/requirements-sim.txt"
# Accept the NVIDIA EULA only after reviewing it.
export OMNI_KIT_ACCEPT_EULA=YES
```

Fetch the separately licensed public robot/model using the parent repository's asset downloader. Do not copy private checkpoints or replace the backlash model with a simpler robot.

```bash
python -m microduck_workshop.assets fetch --accept-mesh-license --destination .cache/assets
python -m microduck_workshop.sim.play --asset-root .cache/assets \
  --mode validate --steps 350 --output artifacts/native-training-mode
python -m microduck_workshop.sim.play --asset-root .cache/assets \
  --mode validate --steps 350 --policy-mode deployment --output artifacts/native-deployment-mode
```

`validate` runs one continuous settle → walk → zero → resume episode. Commands change only the neural observation, never the root pose or joint state. It exits nonzero if the independent evaluator fails. `policy_trace.jsonl` preserves all 61 inputs, 14 raw actions and 14 targets. `evaluator_truth.jsonl` is intentionally separate and must never enter the ROS/agent observation contract.

`--mode serve` binds only `127.0.0.1:8766`; it starts with zero velocity intent. The loopback HTTP API is in `docs/transport.md`. Only the physics loop applies efforts. HTTP threads and the wall watchdog mutate intent, not physics. A stop remains latched until a new operator-started episode; no model reset/re-arm tool exists. The command ACK is not physical verification.

## Actuator and asset fidelity

- Exact canonical asset: `robot_allcollisions_backlash.xml`, SHA-256 `ccee92e435e39eefc64ee99745823751492ae7f948d835c89701710717e71de8`.
- The authored model has 15 bodies and 28 hinge DOFs plus a free root. Newton merges each same-body coaxial pair into a two-axis joint; it does **not** remove the passive DOF. Native labels can be `joint:0/1` or `passive_joint_backlash:0/1`. The adapter validates both DOFs and uses the ±1° limits to identify the passive coordinate, then independently resolves the exact original labels through Newton's MuJoCo DOF metadata.
- Select the converted USD `Physics=mujoco` variant. The importer's warnings about dropping duplicate axes refer to its **unused PhysX variant**.
- GA's native actuator USD importer rejects these merged 2-DOF joints. The documented `use_newton_actuators=False` path supplies a **zero-gain, effort-only sink**; it is not a PD replacement. The source-equation BAM M6 voltage/current/back-EMF/friction model computes efforts, and the public indexed Lab friction writer updates native solver dry friction each physics tick. Native friction values are read back and checked.
- Derived XML removes the legacy XML position drives, sets BAM armature/passive damping/stiff friction constraints, and reapplies the public foot/contact overrides. Original meshes, body frames, inertials and both coaxial joints remain intact. Derived USD/meshes retain the upstream CC BY-NC-SA terms.
- The actor gets encoder position/velocity as servo + backlash and a gravity estimate computed only from the real Lab Newton IMU gyro/accelerometer. It never reads root orientation. The estimator is an authored complementary filter, not a claim of hardware AHRS parity.
- A/B modes preserve the upstream discrepancy: `training` is HOME + raw, unfiltered; `deployment` uses scale .9 plus head α=.5 / leg α=.7 EMA. Previous-action observations always use the **raw** output.
- The static pinned training dependency uses a 1.75 A limiter, unlike its inference script's disabled limiter. This runtime uses 1.75 A and records it, plus fixed nominal voltage 7.5 V, sag gain .1 and four physics-tick delay (inside the source training ranges).

## Live sensors and fresh PPO

```bash
# Actual head RGB + human overview + encoder/IMU HTTP endpoint; starts at zero intent.
python -m microduck_workshop.sim.play --asset-root .cache/assets --mode serve \
  --cameras --tag-id 0 --steps 1500 --output artifacts/serve
# Operator selects STOP at launch with --tag-id 1; this is not an agent reset tool.
python -m microduck_workshop.sim.train --asset-root .cache/assets \
  --updates 4 --horizon 32 --seed 7 --output artifacts/train
```

The head camera is an authored 640×480 teaching pinhole, actual rendered K = `[480,0,320; 0,480,240; 0,0,1]`, no distortion. Its mount uses Pollen's source `head_camera` site plus 5 mm forward lens clearance; orientation is source-model HOME forward. These are **authored intrinsics/extrinsics, not hardware measurements**. The .20 m black-border tag36h11 square sits on a .25 m textured board. Both tag0 GO and tag1 STOP are authored; the operator chooses which is visible at episode start. `camera_authorship.json` records the mount. No root/world state enters Image/CameraInfo/IMU or the neural policy.

PPO is a small explicit PyTorch actor/critic trainer over real Lab-owned MicroDuck transitions (one environment for the short exercise). It uses GAE and clipped PPO, saves actor/critic/optimizer state, and checks both nonzero weight changes and checkpoint reload. Ground truth is restricted to reward, termination and evaluator logs. Fallen-episode resets are legitimate training resets, not hidden playback recoveries. The public ONNX is **not** a PPO resume checkpoint, and this exercise does not produce a converged gait.

## Execution evidence and limits

- Clean GA native reset/step preserved 15 bodies and all 28 joint DOFs. Actual Lab Newton IMU/encoders captured. BAM native armature, damping, stiff friction constraints and per-step dynamic dry friction readback passed.
- Actual ONNX ran 1,400 consecutive physics steps through walk → zero → resume. At diagnostic **neural command .4**, measured walk displacement was .341 m, stop tail speed .000819 m/s, and resume displacement .330 m; no resets. **This is outside the frozen HTTP .10 m/s envelope.**
- The .08/.10 neural commands did not produce meaningful walking, in either training or deployment mode at .10. These failures remain visible. Do not silently boost commands, relax physical thresholds or claim the agent capstone is ready from the .4 diagnostic run. `--validation-vx` is explicit offline diagnostics only and never alters HTTP admission bounds.
- Both actual rendered head-camera signal images passed a CPU tag36h11 pixel-input check (tag0 and tag1 in separate episodes). This proves usable **real rendered detector input**, not Isaac ROS CUDA execution; the ROS worker supplies that separate receipt. Initial occluded/black-camera failures were retained and the source-site mount fixed.
- A real fresh PPO run executed 512 Newton steps / 128 transitions, four updates and 16 optimizer steps, with nonzero weight changes and a reloaded checkpoint. It reset two failed training episodes. No convergence claim.
- The real native HTTP probe observed the submitted command in actual ONNX input, atomic image headers/calibration, actual sensor streams, duplicate rejection and priority stop. The completed interrupted request had `verification_available=true, verified=false`; the final neural command was zero.
- Local RTX PRO 6000 execution is not Brev or L40S evidence.

Kit must launch before importing `NewtonManager` or other USD-bearing runtime modules. Use `InteractiveScene` so GA's explicit clone plan actually imports the model. Warm the camera's capture path, not just the empty visualizer render loop. A clean shell exit from Kit alone is not acceptance: require the explicit assertion/receipt written before shutdown.

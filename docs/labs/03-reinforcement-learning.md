# Lab 3 — observations → actions → rewards → an actual update

**20 minutes · 15:55–16:15.** Goal: explain what the learned controller consumes and produces, then identify evidence of a real short training run. **An optimizer update is not convergence.**

## 1. Read the public policy contract — 5 minutes

Open [policy_contract.json](../../provenance/policy_contract.json), especially `contract`, `actuator` and `risks`. From the repository root, this read-only command prints the pinned contract:

```bash
python3 -c 'import json; from pathlib import Path; c=json.loads(Path("provenance/policy_contract.json").read_text())["contract"]; print("input:", c["input"]); print("output:", c["output"]); print("joints:", c["joint_order"]); print("slices:", c["observation_slices"])'
```

For the public VelStand v8 candidate:

| Policy input slice | Meaning |
|---|---|
| `0:3` | Trunk angular velocity |
| `3:6` | Projected gravity in the trunk frame |
| `6:20` | Encoder positions relative to home |
| `20:34` | Encoder velocities |
| `34:48` | Previous **raw network output**, before target filtering |
| `48:51` | Desired body velocity `[vx, vy, wz]` |
| `51:55` | Head command deltas |
| `55:61` | Body command deltas; not a global navigation pose |

The candidate maps **61 observations to 14 actions**. These are not 14 body velocities: they become ordered joint targets through the specific scale/actuator/delay contract. Normalization is embedded in this ONNX; adding a generic normalizer changes its meaning. Shape matching alone cannot validate the port. The provenance explicitly records training/deployment scale, filtering and actuator differences.

**Mini-exercise:** point to the observation entry that changes when the desired forward speed changes. Then explain why the previous action is not interchangeable with the last filtered joint target. Check your explanation against the JSON descriptions.

## 2. Predict the reward trade-off — 4 minutes

A **policy** selects actions from observations. A **reward** scores behavior during learning. An **episode** ends or resets after a task-defined condition. PPO updates model parameters from rollouts; the optimizer is not running during ordinary pretrained inference.

Open [sim/train.py](../../src/microduck_workshop/sim/train.py). Find its velocity-tracking term, upright reward, action-magnitude penalty and height/upright/episode-length termination. The penalty is not an implemented action-smoothness term; do not assume the full upstream MJLab reward is already ported.

Write a prediction: “If tracking reward is increased without adequate stability constraints, the robot might …”. Compare walking at the requested speed, falling forward, and shaking joints. A reward curve can improve while the behavior remains unacceptable. This discussion is a hypothesis exercise, not a measured training result.

## 3. Run the short Newton training experiment — 7 minutes

In a **host** terminal, stop playback, ROS, observers/agent and model before the short job.
On a 48 GB L40S, do not co-load training and the LLM. Confirm your owned GPU allocations
have cleared; do not kill unrelated processes.

```bash
bash scripts/brev_stop.sh
nvidia-smi
# Only after you have reviewed and accepted the NVIDIA EULA:
OMNI_KIT_ACCEPT_EULA=YES WORKSHOP_GPU=0 \
  docker compose run --rm --no-deps --name roscon-brev-train sim \
  -m microduck_workshop.sim.train --asset-root /assets \
  --updates 4 --horizon 32 --seed 7 --output /outputs/train-class-01
```

Use a new output suffix if you already ran this exercise; do not overwrite failures.
Give the prewarmed job **four minutes**. If it exceeds the timebox, use another host terminal:
`docker stop --time 10 roscon-brev-train`. Label an interrupted job incomplete.

After normal completion, inspect the **actual** receipt on the host:

```bash
python3 -m json.tool .workshop/sim-output/train-class-01/training_receipt.json
```

The recorded local RTX PRO example made 512 Newton physics steps, four updates and
16 optimizer steps. Your receipt must establish its own runtime, finite metrics,
nonzero `weight_delta_l2` and checkpoint roundtrip; do not copy those numbers as your
result. It explicitly reports `converged_gait=false` and `resumed_onnx=false`.
The optimizer is CPU-side; its transitions come from the real GPU Newton robot.
An import or pretrained ONNX inference is not a PPO update.

The completed experiment is short actual Isaac Lab/Newton training, **not convergence**. If the runtime gate is blocked, inspect clearly labeled recorded evidence with the instructor and record **not executed here**.

## 4. Return to separately validated inference — 4 minutes

After training exits, restart the model in its dedicated **host** terminal:

```bash
MODEL_GPU=0 MODEL_PORT=8080 bash scripts/model_start.sh
```

Wait for its `READY` line, then in another **host** terminal start a fresh episode:

```bash
WORKSHOP_GPU=0 WORKSHOP_TAG_ID=0 bash scripts/brev_start.sh --accept-nvidia-eula
```

Reopen your [ROS tools shell](00-before-class.md#2-prepare-the-terminals). This restores
the pinned public ONNX and the native-validated fixed-step profile, **not** your short-run
actor. If startup exceeds the timebox, ask staff; do not reuse a stale episode or old ROS lease.

The public ONNX is an inference candidate. It does not contain the PPO critic, optimizer state and training counters needed for full training resume. Do not claim a private teacher checkpoint or a full PPO resume from this file. Pollen's MJLab code informs the port; the class still runs Isaac Lab/Newton only.

Before agent motion, staff also require the [same-episode full acceptance](../capstone.md#final-acceptance-checklist). Native step → zero → step evidence does not itself establish ROS/model acceptance. A scripted gait is not an equivalent shortcut.

## Checkpoint

Keep the run ID and evidence of actual optimizer work, or explicitly mark the training attempt blocked. Explain the distinction between a desired body velocity, a policy action and a filtered actuator target; between ONNX inference and PPO resume; and between an update and convergence.

Next: [Isaac ROS perception](04-isaac-ros.md).

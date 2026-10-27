# Lab 3 — observations → actions → rewards → an actual update

**20 minutes · 15:55–16:15.** Goal: explain what the learned controller consumes and produces, then identify evidence of a real short training run. **An optimizer update is not convergence.**

## 1. Read the public policy contract — 5 minutes

Open [policy_contract.json](../../provenance/policy_contract.json), especially `contract`, `actuator` and `risks`. From the repository root, this read-only command prints the pinned contract:

```bash
python -c 'import json; from pathlib import Path; c=json.loads(Path("provenance/policy_contract.json").read_text())["contract"]; print("input:", c["input"]); print("output:", c["output"]); print("joints:", c["joint_order"]); print("slices:", c["observation_slices"])'
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

Open the actual task/reward implementation through the training entry point in the [README](../../README.md). Identify one tracking term, one stability/smoothness term and a termination condition **that really exist in this revision**; do not assume an upstream MJLab reward is already ported.

Write a prediction: “If tracking reward is increased without adequate stability constraints, the robot might …”. Compare walking at the requested speed, falling forward, and shaking joints. A reward curve can improve while the behavior remains unacceptable. This discussion is a hypothesis exercise, not a measured training result.

## 3. Run the short Newton training experiment — 7 minutes

Use only the verified short-training command and bounded configuration in the [README](../../README.md), after its reset/step gate has passed. Do not guess task names, flags, a GPU memory budget or checkpoint paths.

1. The instructor stops/disables the interactive command owner as directed by that runtime procedure; do not run a second owner against the playback robot. Stop competing local-model/render work if the tested training profile requires it.
2. Record the run's actual task, Newton backend, seed, environment count and observation/action shapes. Those are run facts, not just target constants.
3. Run the prewarmed short job. Give it **four minutes of this segment**; if startup compilation consumes that budget, stop the lesson attempt through the documented path and label it incomplete. Never replace it with random numbers or a toy loop presented as robot RL.
4. Inspect real rollout steps, finite optimization statistics and proof that model parameters changed; retain the output/checkpoint receipt. An import, ONNX inference or a loss-shaped printout alone does not prove a PPO update.
5. State what the experiment did **not** prove: stable gait, generalization, transfer to hardware, or reproducible reward improvement across seeds.

The completed experiment is short actual Isaac Lab/Newton training, **not convergence**. If the runtime gate is blocked, inspect clearly labeled recorded evidence with the instructor and record **not executed here**.

## 4. Return to separately validated inference — 4 minutes

Stop training cleanly and restore the release's tested interactive playback configuration before perception. Use a **separately validated** learned policy for the game, not a just-initialized short-run actor.

The public ONNX is an inference candidate. It does not contain the PPO critic, optimizer state and training counters needed for full training resume. Do not claim a private teacher checkpoint or a full PPO resume from this file. Pollen's MJLab code informs the port; the class still runs Isaac Lab/Newton only.

Before allowing agent motion, staff must have real Newton evidence for walk → zero-command balance → resume, bounds and stop/watchdog behavior. A scripted gait is not an equivalent shortcut.

## Checkpoint

Keep the run ID and evidence of actual optimizer work, or explicitly mark the training attempt blocked. Explain the distinction between a desired body velocity, a policy action and a filtered actuator target; between ONNX inference and PPO resume; and between an update and convergence.

Next: [Isaac ROS perception](04-isaac-ros.md).

"""Short fresh PPO exercise using actual public MicroDuck / Lab Newton transitions."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from microduck_workshop.policy.contract import DECIMATION, HOME, PHYSICS_DT, observation
from microduck_workshop.policy.imu import GravityEstimator


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset-root", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("artifacts/train"))
    p.add_argument("--updates", type=int, default=4)
    p.add_argument("--horizon", type=int, default=32)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--device", default="cuda:0")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if not 1 <= args.updates <= 10000 or not 8 <= args.horizon <= 512:
        raise ValueError("updates 1..10000, horizon 8..512 required")
    import torch

    from .native import MicroDuckRuntime
    from .ppo import PPO

    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    # Small optimizer stays on CPU; actual physics remains on the selected GPU.
    ppo = PPO(device="cpu")
    ppo.save(args.output / "initial.pt", metadata={"fresh": True, "seed": args.seed})
    previous_raw = np.zeros(14, np.float32)
    gravity = GravityEstimator()
    command = [0.08, 0.0, 0.0]

    def make_obs(sample):
        return observation(
            gyro=sample["imu"]["angular_velocity"],
            gravity=gravity.gravity,
            encoder_position=sample["joint_position"],
            encoder_velocity=sample["joint_velocity"],
            previous_raw=previous_raw,
            command=command,
        )[0]

    wall_start = time.monotonic()
    with MicroDuckRuntime(
        args.asset_root / "robot/robot_allcollisions_backlash.xml",
        output_dir=args.output,
        cameras=False,
        device=args.device,
    ) as runtime:
        runtime.enable_bam()
        sample = runtime.sample()
        episode, episode_steps = 0, 0
        metrics_list = []
        with (args.output / "transitions.jsonl").open("w") as evidence:
            for update in range(args.updates):
                obs_batch, act_batch, logp_batch, values, rewards, masks = [], [], [], [], [], []
                for _ in range(args.horizon):
                    obs = torch.from_numpy(make_obs(sample))
                    with torch.no_grad():
                        action, logp, value = ppo.sample(obs)
                    raw = action.numpy()
                    for _ in range(DECIMATION):
                        sample = runtime.step_target(HOME + raw)
                        gravity.update(
                            sample["imu"]["angular_velocity"],
                            sample["imu"]["linear_acceleration"],
                            PHYSICS_DT,
                        )
                    previous_raw = raw.copy()
                    truth = runtime.evaluator_truth()  # reward/termination only, never actor input
                    pose, vel = np.array(truth["root_pose"]), np.array(truth["root_velocity"])
                    up = 1 - 2 * (pose[3] ** 2 + pose[4] ** 2)
                    reward = float(
                        up
                        + 0.5 * np.exp(-(((vel[0] - command[0]) / 0.05) ** 2))
                        - 0.005 * (raw**2).sum()
                    )
                    episode_steps += 1
                    done = bool(pose[2] < 0.07 or up < 0.7 or episode_steps >= 250)
                    obs_batch.append(obs)
                    act_batch.append(action)
                    logp_batch.append(logp)
                    values.append(value)
                    rewards.append(reward)
                    masks.append(not done)
                    evidence.write(
                        json.dumps(
                            {
                                "episode": episode,
                                "sim_time": runtime.sim_time,
                                "observation": obs.tolist(),
                                "raw_action": raw.tolist(),
                                "reward": reward,
                                "terminated": done,
                                "evaluator_only": truth,
                            },
                            allow_nan=False,
                        )
                        + "\n"
                    )
                    if done:
                        # Legitimate episode reset only. Playback never invokes this branch.
                        runtime._initial_reset()
                        runtime.enable_bam()
                        sample = runtime.sample()
                        previous_raw = np.zeros(14, np.float32)
                        gravity = GravityEstimator()
                        episode += 1
                        episode_steps = 0
                with torch.no_grad():
                    bootstrap = ppo.model.critic(torch.from_numpy(make_obs(sample))).squeeze()
                advantages = torch.zeros(args.horizon)
                gae = torch.tensor(0.0)
                next_value = bootstrap
                for t in reversed(range(args.horizon)):
                    mask = float(masks[t])
                    delta = rewards[t] + 0.99 * next_value * mask - values[t]
                    gae = delta + 0.99 * 0.95 * mask * gae
                    advantages[t] = gae
                    next_value = values[t]
                metrics = ppo.update(
                    torch.stack(obs_batch),
                    torch.stack(act_batch),
                    torch.stack(logp_batch),
                    returns=advantages + torch.stack(values),
                    advantages=advantages,
                )
                metrics.update(
                    update=update, reward_mean=float(np.mean(rewards)), episodes_reset=episode
                )
                metrics_list.append(metrics)
                evidence.flush()
                ppo.save(
                    args.output / "checkpoint.pt",
                    metadata={
                        "fresh": True,
                        "seed": args.seed,
                        "update": update,
                        "physics": "newton",
                        "sim_time": runtime.sim_time,
                    },
                )
                print("PPO_UPDATE", json.dumps(metrics), flush=True)
        checkpoint = torch.load(args.output / "checkpoint.pt", weights_only=True)
        if checkpoint["optimizer_steps"] != ppo.optimizer_steps:
            raise RuntimeError("saved optimizer checkpoint failed roundtrip")
        receipt = {
            "evidence_kind": "LIVE_MICRODUCK_NEWTON_FRESH_PPO",
            "converged_gait": False,
            "resumed_onnx": False,
            "runtime": runtime.identity,
            "seed": args.seed,
            "updates": metrics_list,
            "physics_steps": runtime.sequence,
            "wall_seconds": time.monotonic() - wall_start,
            "checkpoint_sha256": hashlib.sha256(
                (args.output / "checkpoint.pt").read_bytes()
            ).hexdigest(),
            "initial_sha256": hashlib.sha256((args.output / "initial.pt").read_bytes()).hexdigest(),
            "saved_optimizer_steps": checkpoint["optimizer_steps"],
            "note": "Real transitions and gradients. This short exercise does not establish locomotion convergence.",
        }
        (args.output / "training_receipt.json").write_text(json.dumps(receipt, indent=2))
        print("LIVE_PPO_COMPLETE", json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()

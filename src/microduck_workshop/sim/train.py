"""Short real Newton PPO: optional public actor warm-start, fresh critic/optimizer."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from microduck_workshop.policy.contract import DECIMATION, HOME, PHYSICS_DT, observation, targets
from microduck_workshop.policy.imu import GravityEstimator


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset-root", type=Path, required=True)
    p.add_argument(
        "--warm-start-onnx", type=Path, help="pinned public actor only; not full PPO resume"
    )
    p.add_argument("--policy-mode", choices=("training", "deployment"), default="training")
    p.add_argument("--learning-rate", type=float, default=None)
    p.add_argument("--initial-std", type=float, default=None)
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
    args.output.mkdir(parents=True, exist_ok=False)
    from microduck_workshop.policy.student import artifact, create_manifest, sha256, write_json
    from microduck_workshop.policy.warmstart import export_checkpoint, import_public_actor

    actor = import_public_actor(args.warm_start_onnx) if args.warm_start_onnx else None
    lr = args.learning_rate if args.learning_rate is not None else (1e-6 if actor else 3e-4)
    std = args.initial_std if args.initial_std is not None else (0.005 if actor else 0.1)
    if not 0 < lr <= 0.01 or not 0 < std <= 1:
        raise ValueError("learning rate and action std must be positive and bounded")
    actor_init = "public_v8_actor_only" if actor else "random"
    # Small optimizer stays on CPU; actual physics remains on the selected GPU.
    ppo = PPO(device="cpu", actor=actor, learning_rate=lr, initial_std=std)
    initial_actor = {k: v.clone() for k, v in ppo.model.actor.state_dict().items()}
    ppo.save(args.output / "initial.pt", metadata={"actor_init": actor_init, "seed": args.seed})
    previous_raw = np.zeros(14, np.float32)
    previous_target = HOME.copy()
    gravity = GravityEstimator()
    command = [0.08, 0.0, 0.0]
    recorded_obs = []

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
                    if args.warm_start_onnx:
                        # Declared fixed curriculum; no world-truth control feedback.
                        elapsed = episode_steps * PHYSICS_DT * DECIMATION
                        command = [0.25 if 0.4 <= elapsed % 2.4 < 1.4 else 0.0, 0.0, 0.0]
                    obs = torch.from_numpy(make_obs(sample))
                    recorded_obs.append(obs.clone())
                    with torch.no_grad():
                        action, logp, value = ppo.sample(obs)
                    raw = action.numpy()
                    target = targets(raw, mode=args.policy_mode, previous_target=previous_target)
                    for _ in range(DECIMATION):
                        sample = runtime.step_target(target)
                        gravity.update(
                            sample["imu"]["angular_velocity"],
                            sample["imu"]["linear_acceleration"],
                            PHYSICS_DT,
                        )
                    previous_raw = raw.copy()
                    previous_target = target.copy()
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
                                "target": target.tolist(),
                                "policy_mode": args.policy_mode,
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
                        previous_target = HOME.copy()
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
                        "actor_init": actor_init,
                        "critic_init": "fresh_random",
                        "optimizer_init": "fresh_adam",
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
            "evidence_kind": "LIVE_MICRODUCK_NEWTON_PPO",
            "actor_init": actor_init,
            "critic_init": "fresh_random",
            "optimizer_init": "fresh_adam",
            "full_ppo_resume": False,
            "learning_rate": lr,
            "initial_action_std": std,
            "policy_mode": args.policy_mode,
            "bam": runtime.bam_receipt,
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
        if args.warm_start_onnx:
            import onnxruntime as ort

            saved_actor = export_checkpoint(
                args.output / "checkpoint.pt",
                args.output / "actor.onnx",
                source_onnx=args.warm_start_onnx,
            )
            frozen_actor = import_public_actor(args.warm_start_onnx)
            options = ort.SessionOptions()
            options.intra_op_num_threads = options.inter_op_num_threads = 1

            def parity(model, path):
                session = ort.InferenceSession(
                    str(path), sess_options=options, providers=["CPUExecutionProvider"]
                )
                actual, expected = [], []
                for obs in recorded_obs:
                    with torch.no_grad():
                        expected.append(model(obs).numpy())
                    actual.append(session.run(None, {"obs": obs.numpy()[None]})[0][0])
                np.testing.assert_allclose(actual, expected, atol=2e-5, rtol=2e-5)
                return {
                    "samples": len(actual),
                    "max_abs_error": float(
                        np.max(np.abs(np.asarray(actual) - np.asarray(expected)))
                    ),
                    "atol": 2e-5,
                    "rtol": 2e-5,
                    "inputs": "recorded_native_encoder_imu_command_previous_raw",
                }

            after = saved_actor.state_dict()
            changed = sum(int((initial_actor[k] != v).sum()) for k, v in after.items())
            if changed <= 0 or sha256(args.output / "actor.onnx") == sha256(args.warm_start_onnx):
                raise RuntimeError("training did not change the exported actor")
            receipt.update(
                parent_policy_sha256=sha256(args.warm_start_onnx),
                actor_sha256=sha256(args.output / "actor.onnx"),
                actor_changed_parameters=changed,
                warmstart_parity=parity(frozen_actor, args.warm_start_onnx),
                export_parity=parity(saved_actor, args.output / "actor.onnx"),
                transitions=artifact(args.output / "transitions.jsonl"),
                training_source_sha256={
                    name: sha256(Path(__file__).with_name(name)) for name in ("train.py", "ppo.py")
                },
                warmstart_source_sha256=sha256(Path(__file__).parents[1] / "policy/warmstart.py"),
                imported_training_file=str(Path(__file__).resolve()),
                imported_isaaclab_file=__import__("isaaclab").__file__,
            )
        write_json(args.output / "training_receipt.json", receipt)
        if args.warm_start_onnx:
            create_manifest(args.output, mode=args.policy_mode)
        print("LIVE_PPO_COMPLETE", json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()

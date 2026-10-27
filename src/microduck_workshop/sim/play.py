"""Run public VelStand on the Lab-owned Newton model, or serve transport v1."""

import argparse
import itertools
import json
import logging
import signal
import time
import uuid
from collections import deque
from contextlib import contextmanager, nullcontext
from logging.handlers import RotatingFileHandler
from pathlib import Path

from microduck_workshop.contracts import MAX_VX, MAX_VY, MAX_WZ
from microduck_workshop.policy.calibration import PROFILE_NAME, CommandProfile
from microduck_workshop.policy.contract import DECIMATION, PHYSICS_DT
from microduck_workshop.policy.imu import GravityEstimator
from microduck_workshop.policy.onnx import VelStandPolicy

from .evaluate import MotionVerifier, evaluate_trace
from .http import SnapshotStore, serve
from .intent import IntentOwner
from .native import MicroDuckRuntime


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset-root", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("artifacts/runtime"))
    p.add_argument("--mode", choices=("validate", "serve"), default="serve")
    p.add_argument(
        "--steps",
        type=int,
        default=1500,
        help="50 Hz control steps; 0 explicitly serves until SIGINT/SIGTERM",
    )
    p.add_argument("--command-profile", choices=("direct", PROFILE_NAME), default="direct")
    p.add_argument("--policy-mode", choices=("training", "deployment"), default="training")
    p.add_argument("--cameras", action="store_true")
    p.add_argument(
        "--tag-id",
        type=int,
        choices=(0, 1),
        default=0,
        help="operator-authored visible signal at episode launch: 0 GO, 1 STOP",
    )
    p.add_argument("--realtime", action="store_true", help="pace against monotonic wall clock")
    p.add_argument("--device", default="cuda:0")
    p.add_argument(
        "--validation-vx",
        type=float,
        default=0.08,
        help="evaluation only; values above .10 are diagnostic, outside the frozen HTTP envelope",
    )
    return p


def control_steps(steps, mode):
    if steps == 0 and mode == "serve":
        return itertools.count()
    if not 1 <= steps <= 180000:
        raise ValueError("steps must be 1..180000, or 0 for interactive serve only")
    return iter(range(steps))


class JsonlLog:
    """Fixed disk budget for indefinite classroom telemetry, no dropped live checks."""

    def __init__(self, path, *, max_bytes=32 * 1024 * 1024, backups=2):
        self.handler = RotatingFileHandler(
            path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8"
        )
        self.handler.setFormatter(logging.Formatter("%(message)s"))

    def write(self, text):
        record = logging.LogRecord("telemetry", logging.INFO, "", 0, text.rstrip("\n"), (), None)
        self.handler.emit(record)

    def flush(self):
        self.handler.flush()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.handler.close()


@contextmanager
def shutdown_signals(owner):
    requested = []

    def stop(signum, _frame):
        if not requested:
            requested.append(signum)
            owner.stop(owner.episode_id, latch=True)

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield requested
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def infer_command(policy, profile, sample, gravity, desired):
    command = profile.condition(desired)
    target, neural = policy.step(
        gyro=sample["imu"]["angular_velocity"],
        gravity=gravity,
        encoder_position=sample["joint_position"],
        encoder_velocity=sample["joint_velocity"],
        command=command,
    )
    neural.update(
        desired_command=list(desired),
        neural_command=list(command),
        command_profile=profile.receipt(),
        desired_within_frozen_envelope=all(
            abs(x) <= b for x, b in zip(desired, (MAX_VX, MAX_VY, MAX_WZ))
        ),
        neural_within_direct_envelope=all(
            abs(x) <= b for x, b in zip(command, (MAX_VX, MAX_VY, MAX_WZ))
        ),
        neural_within_training_bounds=all(abs(x) <= b for x, b in zip(command, (0.4, 0.3, 1))),
    )
    return target, neural


def validation_command(sim_time, vx=0.08, *, shutdown=False):
    if shutdown:
        return "shutdown", (0.0, 0.0, 0.0)
    if sim_time < 1:
        return "settle", (0.0, 0.0, 0.0)
    if sim_time < 3:
        return "walk", (vx, 0.0, 0.0)
    if sim_time < 5:
        return "zero", (0.0, 0.0, 0.0)
    return "resume", (vx, 0.0, 0.0)


def main(argv=None):
    args = parser().parse_args(argv)
    steps = control_steps(args.steps, args.mode)
    if not 0 < args.validation_vx <= 0.4:
        raise ValueError("validation velocity must be in (0,.4], the source training range")
    args.output.mkdir(parents=True, exist_ok=True)
    policy = VelStandPolicy(args.asset_root / "policies/velstand.onnx", mode=args.policy_mode)
    profile = CommandProfile(args.command_profile)
    profile.bind(policy_sha256=policy.sha256, policy_mode=policy.mode)
    owner = IntentOwner("ep_" + uuid.uuid4().hex, command_profile=profile)
    gravity = GravityEstimator()
    with MicroDuckRuntime(
        args.asset_root / "robot/robot_allcollisions_backlash.xml",
        output_dir=args.output,
        cameras=args.cameras,
        device=args.device,
        tag_id=args.tag_id,
    ) as runtime:
        runtime.enable_bam()
        store = SnapshotStore(
            owner,
            runtime=dict(
                runtime.identity,
                policy_sha256=policy.sha256,
                policy_mode=policy.mode,
                command_profile=profile.receipt(),
            ),
        )
        sample = runtime.sample()
        trace = [] if args.mode == "validate" else deque(maxlen=500)
        wall_start = time.monotonic()
        transport = serve(store) if args.mode == "serve" else nullcontext()

        def log(name):
            path = args.output / name
            return JsonlLog(path) if args.steps == 0 else path.open("w")

        with (
            transport,
            shutdown_signals(owner) as shutdown,
            log("policy_trace.jsonl") as neural_log,
            log("evaluator_truth.jsonl") as truth_log,
            log("evaluator_verdicts.jsonl") as verdict_log,
        ):
            verifier = MotionVerifier(owner, verdict_log)
            shutdown_at = None
            for step in steps:
                if shutdown:
                    if shutdown_at is None:
                        shutdown_at = runtime.sim_time
                    if runtime.sim_time - shutdown_at >= 0.5:
                        break
                if args.mode == "validate":
                    phase, command = validation_command(
                        runtime.sim_time, args.validation_vx, shutdown=bool(shutdown)
                    )
                else:
                    verifier.begin_tick(runtime.sim_time, runtime.evaluator_truth())
                    phase, command = "transport", owner.consume(sim_time=runtime.sim_time)
                target, neural = infer_command(policy, profile, sample, gravity.gravity, command)
                neural_log.write(
                    json.dumps(
                        dict(sequence=step, sim_time=runtime.sim_time, event="control", **neural),
                        allow_nan=False,
                    )
                    + "\n"
                )
                for _ in range(DECIMATION):
                    # A stopped/paused loop must consume cleared intent before the
                    # next actuation, not finish an old four-substep batch first.
                    if args.mode == "serve" or shutdown:
                        fresh = owner.consume(sim_time=runtime.sim_time)
                        if fresh != command:
                            command = fresh
                            target, neural = infer_command(
                                policy, profile, sample, gravity.gravity, command
                            )
                            neural_log.write(
                                json.dumps(
                                    dict(
                                        sequence=step,
                                        sim_time=runtime.sim_time,
                                        event="intent_preemption",
                                        **neural,
                                    ),
                                    allow_nan=False,
                                )
                                + "\n"
                            )
                    sample = runtime.step_target(target)
                    gravity.update(
                        sample["imu"]["angular_velocity"],
                        sample["imu"]["linear_acceleration"],
                        PHYSICS_DT,
                    )
                store.publish_state(sample)
                if args.cameras:
                    runtime.publish_camera(store, owner.episode_id)
                row = dict(
                    sim_time=runtime.sim_time,
                    phase=phase,
                    command=command,
                    **runtime.evaluator_truth(),
                )
                trace.append(row)
                if args.mode == "serve":
                    verifier.end_tick(runtime.sim_time, runtime.evaluator_truth())
                truth_log.write(json.dumps(row, allow_nan=False) + "\n")
                if step % 50 == 0:
                    neural_log.flush()
                    truth_log.flush()
                    print(
                        json.dumps({"step": step, "sim_time": runtime.sim_time, "phase": phase}),
                        flush=True,
                    )
                if args.realtime or args.mode == "serve":
                    time.sleep(max(0.0, wall_start + runtime.sim_time - time.monotonic()))
            owner.stop(owner.episode_id, latch=True)
            verdict = evaluate_trace(trace)
            verdict.update(
                runtime=runtime.identity,
                bam=runtime.bam_receipt,
                physics_steps=runtime.sequence,
                control_steps=runtime.sequence // DECIMATION,
                command_profile=profile.receipt(),
                telemetry_bounded=args.steps == 0,
                shutdown_signal=shutdown[0] if shutdown else None,
                wall_seconds=time.monotonic() - wall_start,
                actual_policy_sha256=policy.sha256,
                policy_mode=policy.mode,
            )
            verdict["within_frozen_command_envelope"] = args.validation_vx <= 0.10
            (args.output / "evaluation.json").write_text(json.dumps(verdict, indent=2))
            print("RUNTIME_EVALUATION", json.dumps(verdict), flush=True)
            if args.mode == "validate" and not verdict["walk_stop_resume_verified"]:
                raise SystemExit(2)


if __name__ == "__main__":
    main()

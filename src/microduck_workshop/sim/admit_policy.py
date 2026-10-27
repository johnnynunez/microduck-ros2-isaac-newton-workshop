"""Exact student policy native admission; NEVER ROS/perception/agent acceptance.

Fixed plan mirrors the original step holdout timings. No threshold, actuator,
command adapter or runtime edits; all failures and raw traces remain on disk.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from microduck_workshop.policy.contract import DECIMATION, PHYSICS_DT
from microduck_workshop.policy.imu import GravityEstimator
from microduck_workshop.policy.student import (
    ADMISSION_CASES,
    CandidateStepProfile,
    StudentPolicy,
    admission_plan,
    artifact,
    fixed_step_spec,
    load_admission,
    load_manifest,
    read_json,
    source_hashes,
    write_json,
)

from .evaluate import evaluate_motion
from .native import MicroDuckRuntime
from .play import infer_command

CASES = ADMISSION_CASES


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset-root", type=Path, required=True)
    p.add_argument("--policy-manifest", type=Path, required=True)
    p.add_argument(
        "--output", type=Path, required=True, help="NEW directory; prior attempts preserved"
    )
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--_native-worker", action="store_true", help=argparse.SUPPRESS)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    manifest = load_manifest(args.policy_manifest)
    if not args._native_worker:
        if args.output.exists():
            raise FileExistsError("admission output must be a new directory")
        # Kit may terminate its interpreter on close. The lightweight parent
        # verifies the final receipt and propagates failures rather than its ACK.
        command = [
            sys.executable,
            "-m",
            "microduck_workshop.sim.admit_policy",
            *(sys.argv[1:] if argv is None else argv),
            "--_native-worker",
        ]
        final_path = args.output / "admission.json"
        try:
            result = subprocess.run(command, check=False)
            if result.returncode:
                raise RuntimeError(f"native worker exited {result.returncode}")
            load_admission(final_path, manifest, replay_policy=StudentPolicy(manifest))
        except BaseException as exc:
            if final_path.exists():
                failed = read_json(final_path)
                failed.update(
                    passed=False, lifecycle="failed", error=f"{type(exc).__name__}: {exc}"
                )
                write_json(final_path, failed)
            raise
        return
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema_version": 1,
        "scope": "native_only_not_ros_agent_acceptance",
        "policy_sha256": manifest["policy_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
        "policy_mode": manifest["policy_mode"],
        "source_sha256": source_hashes(),
        "fixed_step": fixed_step_spec(),
        "passed": False,
        "lifecycle": "running",
        "cases": [],
        "plan": admission_plan(),
        "gates": "unchanged evaluate_motion: .04m/s, .10rad/s after >=.35sim seconds",
        "reset_scope": "between independent holdout episodes only; never between requests",
    }
    write_json(args.output / "preregistration.json", receipt)
    try:
        with MicroDuckRuntime(
            args.asset_root / "robot/robot_allcollisions_backlash.xml",
            output_dir=args.output / "native",
            cameras=False,
            device=args.device,
        ) as runtime:
            receipt["runtime"] = runtime.identity
            for index, (name, initial_zero, zero_wait) in enumerate(CASES):
                if index:
                    runtime._initial_reset()
                runtime.enable_bam()
                policy, gravity = StudentPolicy(manifest), GravityEstimator()
                sample = runtime.sample()
                policy_rows, truth_rows, verdicts = [], [], []
                spec = CandidateStepProfile(policy)

                def tick(
                    desired,
                    phase,
                    policy=policy,
                    spec=spec,
                    gravity=gravity,
                    policy_rows=policy_rows,
                    truth_rows=truth_rows,
                ):
                    nonlocal sample
                    target, neural = infer_command(policy, spec, sample, gravity.gravity, desired)
                    policy_rows.append(dict(sim_time=runtime.sim_time, phase=phase, **neural))
                    for _ in range(DECIMATION):
                        sample = runtime.step_target(target)
                        gravity.update(
                            sample["imu"]["angular_velocity"],
                            sample["imu"]["linear_acceleration"],
                            PHYSICS_DT,
                        )
                    row = dict(sim_time=runtime.sim_time, phase=phase, **runtime.evaluator_truth())
                    truth_rows.append(row)
                    return row

                def zero(seconds, phase):
                    for _ in range(round(seconds / (DECIMATION * PHYSICS_DT))):
                        tick((0, 0, 0), phase)

                zero(initial_zero, "initial_zero")
                for request in ("step", "resume"):
                    trace = [dict(sim_time=runtime.sim_time, **runtime.evaluator_truth())]
                    for n in range(100):
                        trace.append(tick((0.1, 0, 0) if n < 50 else (0, 0, 0), request))
                    for _ in range(18):  # completion + .36s, not a relaxed verifier
                        trace.append(tick((0, 0, 0), request + "_verify_wait"))
                    command = SimpleNamespace(vx=0.1, wz=0.0, duration_s=2.0)
                    verdicts.append(
                        dict(request=request, **evaluate_motion(trace, command, "completed"))
                    )
                    zero(zero_wait - 0.36, request + "_remaining_zero_wait")
                rest = [dict(sim_time=runtime.sim_time, **runtime.evaluator_truth())]
                for _ in range(68):
                    rest.append(tick((0, 0, 0), "rest_control"))
                verdicts.append(
                    dict(
                        request="rest_control",
                        **evaluate_motion(
                            rest, SimpleNamespace(vx=0.0, wz=0.0, duration_s=1.0), "completed"
                        ),
                    )
                )
                import json

                artifacts = []
                for suffix, rows in (("policy", policy_rows), ("truth", truth_rows)):
                    path = args.output / f"{name}_{suffix}.jsonl"
                    path.write_text(
                        "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows)
                    )
                    artifacts.append(artifact(path))
                result = {"id": name, "verdicts": verdicts, "artifacts": artifacts}
                receipt["cases"].append(result)
                write_json(args.output / "admission.json", receipt)
                print("POLICY_ADMISSION_CASE", json.dumps(result), flush=True)
            receipt["bam"] = runtime.bam_receipt
            receipt["physics_steps"] = runtime.sequence
            receipt["passed"] = all(v["verified"] for c in receipt["cases"] for v in c["verdicts"])
            receipt["lifecycle"] = "complete" if receipt["passed"] else "failed"
            # This write MUST precede Kit teardown (which can exit the process).
            write_json(args.output / "admission.json", receipt)
            print("POLICY_ADMISSION", receipt["passed"], manifest["policy_sha256"], flush=True)
    except BaseException as exc:
        receipt["passed"] = False
        receipt["lifecycle"] = "failed"
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        write_json(args.output / "admission.json", receipt)
        raise
    if not receipt["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fresh real Newton HTTP holdouts. Run under heavyrun, never against another server.

Only the client schedule reads public sim_time. GT is read OFFLINE after shutdown,
never fed into policy/command generation. Existing MotionVerifier supplies gates.
"""

import argparse
import hashlib
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def command_intervals(rows):
    intervals, start = [], None
    for row in rows:
        desired = row["desired_command"]
        neural = row["neural_command"]
        assert len(row["observation"]) == 61
        assert all(abs(a - b) < 1e-7 for a, b in zip(row["observation"][48:51], neural))
        assert (desired, neural) in [([0, 0, 0], [0, 0, 0]), ([0.1, 0, 0], [0.25, 0, 0])]
        if desired[0] and start is None:
            start = row["sim_time"]
        if not desired[0] and start is not None:
            intervals.append((start, row["sim_time"]))
            start = None
    assert start is None, "last command did not return to exact neural zero"
    return intervals


def request(path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Workshop-Lease"] = token
    req = urllib.request.Request(
        "http://127.0.0.1:8766" + path,
        data=None if body is None else json.dumps(body).encode(),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def wait_until(predicate, process, timeout=150):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"native server exited early ({process.returncode})")
        try:
            result = predicate()
            if result:
                return result
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.01)
    raise TimeoutError("native probe wait exceeded deadline")


def run_case(case, asset_root, output, plan_hash):
    output.mkdir(parents=True, exist_ok=False)
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 8766)) == 0:
            raise RuntimeError("8766 in use; will not touch another server")
    command = [
        sys.executable,
        "-m",
        "microduck_workshop.sim.play",
        "--asset-root",
        str(asset_root),
        "--mode",
        "serve",
        "--steps",
        "0",
        "--command-profile",
        "calibrated-forward-v1",
        "--output",
        str(output / "native"),
    ]
    done = threading.Event()
    renew_errors = []
    with (output / "server.log").open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:

            def health():
                code, value = request("/v1/health")
                return value if code == 200 and value["ready"] else None

            state = wait_until(health, process)
            ep = state["episode_id"]
            assert state["runtime"]["command_profile"]["name"] == "calibrated-forward-v1"

            def sim_time():
                return request("/v1/health")[1]["sim_time"]

            def wait_sim(target):
                return wait_until(lambda: sim_time() >= target, process)

            wait_sim(case["initial_zero_s"])
            code, claim = request("/v1/claim", {"owner_id": "calibration_probe"})
            assert code == 200
            token = claim.pop("lease_token")
            code, other = request("/v1/claim", {"owner_id": "second_owner"})
            assert code == 409 and not other["accepted"]

            def renew():
                while not done.wait(0.1):
                    try:
                        code, _ = request("/v1/renew", {"episode_id": ep}, token)
                        if code != 200 and not done.is_set():
                            renew_errors.append(code)
                    except OSError as exc:
                        renew_errors.append(type(exc).__name__)

            thread = threading.Thread(target=renew, daemon=True)
            thread.start()
            results = []

            def submit(name):
                code, value = request(
                    "/v1/command",
                    {
                        "episode_id": ep,
                        "request_id": name,
                        "expected_generation": request("/v1/health")[1]["generation"],
                        "vx": 0.1,
                        "vy": 0,
                        "wz": 0,
                        "duration_s": case["duration_s"],
                    },
                    token,
                )
                assert code == 200 and value["accepted"], value
                return value

            for name in ("walk", "resume"):
                before_wall, before_sim = time.monotonic(), sim_time()
                ack = submit(name)

                def completed(name=name):
                    value = request("/v1/status/" + name)[1]
                    return value if value["completed"] else None

                status = wait_until(completed, process)
                completed_sim = sim_time()
                results.append(
                    {
                        "request_id": name,
                        "ack": ack,
                        "completed_status": status,
                        "submitted_sim_s": before_sim,
                        "completed_sim_s": completed_sim,
                        "request_wall_s": time.monotonic() - before_wall,
                    }
                )
                # Fixed schedule, never gate next command on GT or the physical verdict.
                wait_sim(completed_sim + (case["zero_wait_s"] if name == "walk" else 1.0))
            for result in results:
                result["physical_status"] = request("/v1/status/" + result["request_id"])[1]
            ack = submit("interrupted")
            wait_sim(sim_time() + 0.3)
            code, stop = request("/v1/stop", {"episode_id": ep, "latch": True})
            assert code == 200 and stop["stop_latched"]
            done.set()
            thread.join(timeout=2)
            stop_at = sim_time()
            wait_sim(stop_at + 0.8)
            interrupted = request("/v1/status/interrupted")[1]
            assert interrupted["status"] == "stopped" and not interrupted["verified"]
            assert interrupted["verification_available"]
            final_state = request("/v1/state")[1]
            assert final_state["stop_latched"] and not final_state["command_active"]
            process.terminate()
            assert process.wait(timeout=90) == 0
            native = output / "native"
            rows = [
                json.loads(line)
                for line in (native / "policy_trace.jsonl").read_text().splitlines()
            ]
            intervals = command_intervals(rows)
            assert len(intervals) == 3
            assert all(row["neural_within_training_bounds"] for row in rows)
            truth = [
                json.loads(line)
                for line in (native / "evaluator_truth.jsonl").read_text().splitlines()
            ]
            physical = [
                json.loads(line)
                for line in (native / "evaluator_verdicts.jsonl").read_text().splitlines()
            ]
            import numpy as np

            measurements = []
            for start, end in intervals:
                segment = [r for r in truth if start - 1e-7 <= r["sim_time"] <= end + 1e-7]
                poses = np.array([r["root_pose"] for r in segment])
                velocity = np.array([r["root_velocity"] for r in segment])
                displacement = float(poses[-1, 0] - poses[0, 0])
                onset = next(
                    (r["sim_time"] - start for r, v in zip(segment, velocity) if v[0] > 0.02), None
                )
                measurements.append(
                    {
                        "neural_start_sim_s": start,
                        "neural_end_sim_s": end,
                        "actual_neural_duration_s": end - start,
                        "active_forward_displacement_m": displacement,
                        "active_mean_world_x_speed_m_s": displacement / (end - start),
                        "first_world_x_speed_above_02_latency_s": onset,
                        "min_height_m": float(poses[:, 2].min()),
                        "min_up_cosine": float(
                            (1 - 2 * (poses[:, 3] ** 2 + poses[:, 4] ** 2)).min()
                        ),
                    }
                )
            post_stop = [r for r in truth if r["sim_time"] >= stop_at + 0.6]
            stop_speed = float(np.mean([np.linalg.norm(r["root_velocity"][:2]) for r in post_stop]))
            evaluation = json.loads((native / "evaluation.json").read_text())
            receipt = {
                "case": case,
                "plan_sha256": plan_hash,
                "evidence_kind": "FRESH_REAL_NEWTON_HTTP_CALIBRATION_HOLDOUT",
                "profile": state["runtime"]["command_profile"],
                "runtime": state["runtime"],
                "requests": results,
                "physical_verdicts": physical,
                "measurements": measurements,
                "stop_tail_speed_m_s": stop_speed,
                "stop": stop,
                "interrupted": interrupted,
                "single_owner_rejected": True,
                "renew_errors": renew_errors,
                "signal_shutdown": evaluation["shutdown_signal"],
                "desired_within_frozen_envelope": True,
                "neural_within_training_bounds": True,
                "both_completed_requests_verified": all(
                    r["physical_status"]["verified"] for r in results
                ),
                "artifacts_sha256": {
                    name: hashlib.sha256((native / name).read_bytes()).hexdigest()
                    for name in (
                        "policy_trace.jsonl",
                        "evaluator_truth.jsonl",
                        "evaluator_verdicts.jsonl",
                        "evaluation.json",
                    )
                },
            }
            (output / "receipt.json").write_text(json.dumps(receipt, indent=2))
            print(
                json.dumps(
                    {
                        "case": case["id"],
                        "verified": receipt["both_completed_requests_verified"],
                        "physical": physical,
                        "measurements": measurements,
                    }
                ),
                flush=True,
            )
            return receipt
        finally:
            done.set()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def summarize_receipts(receipts, expected_ids, plan_hash):
    ids = [r["case"]["id"] for r in receipts]
    if len(ids) != len(set(ids)) or set(ids) != set(expected_ids):
        raise ValueError("receipts must contain each preregistered case exactly once")
    if any(r["plan_sha256"] != plan_hash for r in receipts):
        raise ValueError("receipt preregistration hash mismatch")
    return {
        "plan_sha256": plan_hash,
        "case_count": len(receipts),
        "cases": [
            {
                "id": r["case"]["id"],
                "gating": r["case"]["gating"],
                "verified": r["both_completed_requests_verified"],
            }
            for r in receipts
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", help="one preregistered case ID; default runs all")
    parser.add_argument(
        "--summarize-existing",
        action="store_true",
        help="recheck existing native receipts without simulation or new tuning",
    )
    args = parser.parse_args()
    raw_plan = args.plan.read_bytes()
    document = json.loads(raw_plan)
    plan = document.get("preregistration", document)
    plan_hash = document.get("preregistration_sha256", hashlib.sha256(raw_plan).hexdigest())
    cases = [dict(case, gating=True) for case in plan["gating_cases"]]
    cases.append(dict(plan["non_gating_confirmation"], gating=False))
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
        if not cases:
            parser.error("case is not preregistered")
    receipts = []
    if args.summarize_existing:
        if "holdouts" in document:
            receipts = [
                r for r in document["holdouts"] if r["case"]["id"] in {c["id"] for c in cases}
            ]
        else:
            receipts = [
                json.loads((args.output / case["id"] / "receipt.json").read_text())
                for case in cases
            ]
    else:
        from microduck_workshop.policy.calibration import PROFILE_NAME, CommandProfile

        profile = CommandProfile(PROFILE_NAME).receipt()
        if not profile["forward_durations_s"]:
            parser.error(
                "NOT_READY: round1 failed all forward durations; use --summarize-existing. "
                "Historical experimental reproduction is pinned in provenance/command_calibration.json."
            )
        if args.asset_root is None:
            parser.error("native validation requires --asset-root")
        for case in cases:
            receipts.append(run_case(case, args.asset_root, args.output / case["id"], plan_hash))
    summary = summarize_receipts(receipts, {c["id"] for c in cases}, plan_hash)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)
    if not all(case["verified"] for case in summary["cases"] if case["gating"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fresh native planned-step campaign. No ROS/perception acceptance claim.

Diagnostic proofs use ORIGINAL native sensor capture timestamps, not receipt-now.
World truth is read only after server shutdown, never used to choose motion.
Run under heavyrun on the allocated GPU using the clean pinned GA runtime.
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

from sim_validate_calibration import command_intervals, summarize_receipts, wait_until


def request(path, body=None, token=None, proof=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Workshop-Lease"] = token
    if proof:
        headers.update(proof)
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


def diagnostic_proof():
    code, state = request("/v1/state")
    assert code == 200
    return {
        "X-Workshop-Observation-Episode": state["episode_id"],
        "X-Workshop-Observation-Sequence": str(state["sequence"]),
        "X-Workshop-Observation-Deadline": str(state["capture_monotonic_s"] + 0.5),
    }


def run_case(case, asset_root, output, plan_hash, *, candidate):
    output.mkdir(parents=True, exist_ok=False)
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 8766)) == 0:
            raise RuntimeError("8766 already in use; refusing another owner's server")
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
        "--step-profile",
        "step-forward-v1",
        "--output",
        str(output / "native"),
    ]
    if candidate:
        command.append("--step-candidate-validation")
    done = threading.Event()
    renewal = threading.Event()
    errors = []
    with (output / "server.log").open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:

            def health():
                code, value = request("/v1/health")
                return value if code == 200 and value["ready"] else None

            initial = wait_until(health, process)
            ep = initial["episode_id"]

            def sim_time():
                return request("/v1/health")[1]["sim_time"]

            def wait_sim(target):
                wait_until(lambda: sim_time() >= target, process)

            def claim():
                code, value = request("/v1/claim", {"owner_id": "native_step_diagnostic"})
                assert code == 200, value
                return value["lease_token"]

            wait_sim(case["initial_zero_s"])
            token = claim()
            assert request("/v1/claim", {"owner_id": "second_owner"})[0] == 409

            def renew():
                while not done.wait(0.08):
                    if renewal.is_set():
                        try:
                            code, value = request(
                                "/v1/renew", {"episode_id": ep}, token, diagnostic_proof()
                            )
                            if code != 200 and renewal.is_set():
                                errors.append(value)
                        except OSError as exc:
                            errors.append(str(exc))

            thread = threading.Thread(target=renew, daemon=True)
            thread.start()
            renewal.set()

            def submit(name, proof=None):
                body = {
                    "episode_id": ep,
                    "request_id": name,
                    "expected_generation": request("/v1/health")[1]["generation"],
                    "vx": 0.1,
                    "vy": 0.0,
                    "wz": 0.0,
                    "duration_s": 2.0,
                }
                return request(
                    "/v1/step", body, token, proof if proof is not None else diagnostic_proof()
                )

            def completed(name):
                value = request("/v1/status/" + name)[1]
                return value if value["completed"] else None

            results = []
            for name in ("step", "resume"):
                code, ack = submit(name)
                assert code == 200 and ack["accepted"], ack
                status = wait_until(lambda name=name: completed(name), process)
                ended = sim_time()
                results.append({"request_id": name, "ack": ack, "completed_status": status})
                # Schedule is fixed before execution, never driven by GT/verdict.
                wait_sim(ended + case["zero_wait_s"])
            for result in results:
                result["physical_status"] = request("/v1/status/" + result["request_id"])[1]
            # Live proof expiry while actuator lease is refreshed with the SAME proof.
            renewal.clear()
            time.sleep(0.12)  # drain any in-flight renewal before constructing short proof
            frozen = diagnostic_proof()

            code, ack = submit("proof_expiry", frozen)
            assert code == 200, ack
            time.sleep(0.10)
            assert request("/v1/renew", {"episode_id": ep}, token, frozen)[0] == 200
            expired = wait_until(lambda: completed("proof_expiry"), process)
            assert expired["status"] == "expired", expired
            assert request("/v1/renew", {"episode_id": ep}, token, diagnostic_proof())[0] == 409
            wait_sim(sim_time() + 0.8)
            token = claim()
            time.sleep(0.15)  # newer proof expires after the unrenewed actuator lease
            code, ack = submit("lease_expiry")
            assert code == 200, ack
            expired_lease = wait_until(lambda: completed("lease_expiry"), process)
            assert expired_lease["status"] == "expired"
            assert request("/v1/renew", {"episode_id": ep}, token, diagnostic_proof())[0] == 409
            wait_sim(sim_time() + 0.8)
            token = claim()
            renewal.set()
            code, ack = submit("interrupted")
            assert code == 200, ack
            wait_sim(sim_time() + 0.3)
            renewal.clear()
            code, stop = request("/v1/stop", {"episode_id": ep, "latch": True})
            assert code == 200 and stop["stop_latched"]
            done.set()
            thread.join(timeout=2)
            wait_sim(sim_time() + 0.8)
            interrupted = request("/v1/status/interrupted")[1]
            assert interrupted["status"] == "stopped" and not interrupted["verified"]
            assert interrupted["verification_available"]
            process.terminate()
            assert process.wait(timeout=90) == 0
            native = output / "native"
            rows = [
                json.loads(line)
                for line in (native / "policy_trace.jsonl").read_text().splitlines()
            ]
            intervals = command_intervals(rows)
            assert len(intervals) == 5, intervals
            assert all(abs(end - start - 1.0) < 1e-7 for start, end in intervals[:2]), intervals
            for row in rows:
                if row.get("maneuver_phase") == "settle":
                    assert row["neural_command"] == [0.0, 0.0, 0.0]
                if row.get("maneuver_phase") == "drive":
                    assert row["requested_peak_command"] == [0.1, 0.0, 0.0]
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
                measurements.append(
                    {
                        "neural_start_sim_s": start,
                        "neural_end_sim_s": end,
                        "actual_drive_s": end - start,
                        "drive_world_x_displacement_m": float(poses[-1, 0] - poses[0, 0]),
                    }
                )
            receipt = {
                "case": case,
                "plan_sha256": plan_hash,
                "evidence_kind": "FRESH_NATIVE_OPERATOR_STEP_DIAGNOSTIC_NOT_ROS_PERCEPTION",
                "runtime": initial["runtime"],
                "requests": results,
                "physical_verdicts": physical,
                "measurements": measurements,
                "proof_expiry": expired,
                "lease_expiry": expired_lease,
                "interrupted": interrupted,
                "renewal_errors": errors,
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
            print(json.dumps(receipt), flush=True)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case")
    parser.add_argument("--production-admission", action="store_true")
    args = parser.parse_args()
    raw = args.plan.read_bytes()
    plan = json.loads(raw)
    plan_hash = hashlib.sha256(raw).hexdigest()
    cases = plan["cases"]
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
        if not cases:
            parser.error("case was not preregistered")
    receipts = [
        run_case(
            case,
            args.asset_root,
            args.output / case["id"],
            plan_hash,
            candidate=not args.production_admission,
        )
        for case in cases
    ]
    summary = summarize_receipts(receipts, {case["id"] for case in cases}, plan_hash)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)
    if not all(case["verified"] for case in summary["cases"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

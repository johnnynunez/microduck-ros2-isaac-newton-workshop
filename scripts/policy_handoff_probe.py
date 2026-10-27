#!/usr/bin/env python3
"""Native-only HTTP handoff/fence confirmation on a private port. No ROS claim."""

import argparse
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18766)
    parser.add_argument("--policy-manifest", type=Path)
    parser.add_argument("--policy-admission", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", args.port))
    root = Path(__file__).resolve().parents[1]
    from microduck_workshop.policy.contract import POLICY_SHA256
    from microduck_workshop.policy.student import load_manifest, sha256, source_hashes, write_json

    expected = POLICY_SHA256
    if args.policy_manifest:
        expected = load_manifest(args.policy_manifest)["policy_sha256"]
    # Only the transport listener is bound to a private port. No policy, gate,
    # control loop, evaluator or runtime is patched by this diagnostic harness.
    bootstrap = (
        "import functools; from microduck_workshop.sim import play; "
        "from microduck_workshop.sim.http import serve; "
        f"play.serve=functools.partial(serve,port={args.port}); play.main()"
    )
    command = [
        sys.executable,
        "-c",
        bootstrap,
        "--asset-root",
        str(args.asset_root),
        "--mode",
        "serve",
        "--steps",
        "0",
        "--step-profile",
        "step-forward-v1",
        "--output",
        str(args.output / "native"),
    ]
    if args.policy_manifest:
        command += [
            "--policy-manifest",
            str(args.policy_manifest),
            "--policy-admission",
            str(args.policy_admission),
        ]
    base = f"http://127.0.0.1:{args.port}"
    done, renewal = threading.Event(), threading.Event()
    errors, requests = [], []
    receipt = {
        "scope": "native_only_not_ros_agent_acceptance",
        "passed": False,
        "policy_sha256": expected,
        "port": args.port,
        "launch_command": command,
        "source_sha256": {"src/microduck_workshop/" + k: v for k, v in source_hashes().items()},
        "harness_sha256": sha256(__file__),
        "requests": requests,
        "prior_native_merged_sha256": sha256(root / "provenance/native_merged_validation.json"),
    }

    def request(path, body=None, token=None, proof=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Workshop-Lease"] = token
        if proof:
            headers.update(proof)
        req = urllib.request.Request(
            base + path, headers=headers, data=None if body is None else json.dumps(body).encode()
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    with (args.output / "server.log").open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:

            def wait(fn, timeout=180):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f"native server exited {process.returncode}")
                    try:
                        value = fn()
                        if value:
                            return value
                    except OSError:
                        pass
                    time.sleep(0.02)
                raise TimeoutError("native probe deadline")

            def ready_health():
                value = request("/v1/health")[1]
                return value if value["ready"] else None

            health = wait(ready_health)
            receipt["runtime"] = health["runtime"]
            ep = receipt["episode_id"] = health["episode_id"]
            assert health["runtime"]["policy_sha256"] == expected
            if args.policy_manifest:
                from microduck_workshop.policy.identity import read_policy_identity

                identity = read_policy_identity(
                    args.policy_manifest, args.policy_admission, base + "/v1/health", episode_id=ep
                )
                receipt["selected_policy_identity"] = identity
                write_json(args.output / "policy_identity.json", identity)

            def sim_time():
                return request("/v1/health")[1]["sim_time"]

            def wait_sim(target):
                wait(lambda: sim_time() >= target)

            def proof():
                state = request("/v1/state")[1]
                return {
                    "X-Workshop-Observation-Episode": ep,
                    "X-Workshop-Observation-Sequence": str(state["sequence"]),
                    "X-Workshop-Observation-Deadline": str(state["capture_monotonic_s"] + 0.5),
                }

            def claim():
                code, body = request("/v1/claim", {"owner_id": "policy_native_diagnostic"})
                assert code == 200, body
                return body["lease_token"]

            wait_sim(1.3)
            token = claim()
            assert request("/v1/claim", {"owner_id": "other_owner"})[0] == 409

            def renew():
                while not done.wait(0.08):
                    if renewal.is_set():
                        try:
                            code, value = request("/v1/renew", {"episode_id": ep}, token, proof())
                            if code != 200 and renewal.is_set():
                                errors.append(value)
                        except OSError as error:
                            errors.append(str(error))

            thread = threading.Thread(target=renew, daemon=True)
            thread.start()
            renewal.set()

            def submit(name, observation=None):
                command = {
                    "episode_id": ep,
                    "request_id": name,
                    "expected_generation": request("/v1/health")[1]["generation"],
                    "vx": 0.1,
                    "vy": 0.0,
                    "wz": 0.0,
                    "duration_s": 2.0,
                }
                return request("/v1/step", command, token, observation or proof())

            def finished(name):
                status = request("/v1/status/" + name)[1]
                return status if status["completed"] else None

            for name in ("step", "resume"):
                code, ack = submit(name)
                assert code == 200 and ack["accepted"], ack
                status = wait(lambda: finished(name))
                ended = sim_time()
                wait_sim(ended + 1.1)
                physical = request("/v1/status/" + name)[1]
                requests.append(
                    {
                        "request_id": name,
                        "ack": ack,
                        "completed_status": status,
                        "physical_status": physical,
                    }
                )
                assert physical["verified"], physical
            renewal.clear()
            time.sleep(0.12)
            frozen = proof()
            assert submit("proof_expiry", frozen)[0] == 200
            time.sleep(0.10)
            assert request("/v1/renew", {"episode_id": ep}, token, frozen)[0] == 200
            receipt["proof_expiry"] = wait(lambda: finished("proof_expiry"))
            assert receipt["proof_expiry"]["reason"] == "observation proof expired"
            assert request("/v1/renew", {"episode_id": ep}, token, proof())[0] == 409
            wait_sim(sim_time() + 0.8)
            token = claim()
            time.sleep(0.15)
            assert submit("lease_expiry")[0] == 200
            receipt["lease_expiry"] = wait(lambda: finished("lease_expiry"))
            assert receipt["lease_expiry"]["reason"] == "wall lease expired"
            assert request("/v1/renew", {"episode_id": ep}, token, proof())[0] == 409
            wait_sim(sim_time() + 0.8)
            token = claim()
            renewal.set()
            assert submit("interrupted")[0] == 200
            wait_sim(sim_time() + 0.3)
            renewal.clear()
            assert request("/v1/stop", {"episode_id": ep, "latch": True})[0] == 200
            done.set()
            thread.join(timeout=2)
            wait_sim(sim_time() + 0.8)
            receipt["interrupted"] = request("/v1/status/interrupted")[1]
            assert receipt["interrupted"]["status"] == "stopped"
            assert receipt["interrupted"]["verified"] is False
            assert request("/v1/claim", {"owner_id": "no_rearm"})[0] == 409
            assert not errors, errors
            receipt["passed"] = True
        except BaseException as error:
            receipt["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            done.set()
            receipt["renewal_errors"] = errors
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=90)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            receipt["server_exit_code"] = process.returncode
            native = args.output / "native"
            receipt["artifacts_sha256"] = {p.name: sha256(p) for p in native.glob("*.json*")}
            write_json(args.output / "receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()

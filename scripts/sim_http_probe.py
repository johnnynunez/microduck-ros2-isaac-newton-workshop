#!/usr/bin/env python3
"""Exercise real native HTTP sensors/command/stop; never fabricates physics or images."""

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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 8766)) == 0:
            raise RuntimeError("8766 already in use; refusing to touch another server")

    def get(path):
        with urllib.request.urlopen("http://127.0.0.1:8766" + path, timeout=3) as response:
            return json.load(response)

    def post(path, body, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Workshop-Lease"] = token
        request = urllib.request.Request(
            "http://127.0.0.1:8766" + path,
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    server_output = args.output / "native"
    command = [
        sys.executable,
        "-m",
        "microduck_workshop.sim.play",
        "--asset-root",
        str(args.asset_root),
        "--mode",
        "serve",
        "--steps",
        "200",
        "--cameras",
        "--output",
        str(server_output),
    ]
    done = threading.Event()
    with (args.output / "server.log").open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 150
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"native server exited before ready: {process.returncode}")
                try:
                    health = get("/v1/health")
                    if health["ready"]:
                        info = get("/v1/camera_info")
                        break
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(0.1)
            else:
                raise TimeoutError("native server did not become sensor-ready")
            assert health["physics"] == "newton" and health["runtime"]["newton"] == "1.6.1"
            state = get("/v1/state")
            assert len(state["joint_position"]) == 14 and "root_pose" not in state
            with urllib.request.urlopen("http://127.0.0.1:8766/v1/camera", timeout=3) as response:
                headers = {
                    key: value
                    for key, value in response.headers.items()
                    if key.startswith("X-Microduck-")
                }
                jpeg = response.read()
            (args.output / "http_head.jpg").write_bytes(jpeg)
            assert headers["X-Microduck-Episode"] == health["episode_id"]
            assert info["frame_id"] == "microduck_head_optical" and info["width"] == 640
            status, claim = post("/v1/claim", {"owner_id": "live_probe"})
            assert status == 200
            token = claim.pop("lease_token")  # Never persist or print this secret.

            def renew():
                while not done.wait(0.12):
                    post("/v1/renew", {"episode_id": health["episode_id"]}, token)

            thread = threading.Thread(target=renew, daemon=True)
            thread.start()
            motion = {
                "episode_id": health["episode_id"],
                "request_id": "probe_motion",
                "expected_generation": claim["generation"],
                "vx": 0.08,
                "vy": 0.0,
                "wz": 0.0,
                "duration_s": 1.5,
            }
            status, accepted = post("/v1/command", motion, token)
            assert status == 200 and accepted["accepted"]
            status, duplicate = post("/v1/command", motion, token)
            assert status == 409 and not duplicate["accepted"]
            time.sleep(0.35)
            status, stopped = post("/v1/stop", {"episode_id": health["episode_id"], "latch": True})
            assert status == 200 and stopped["stop_latched"]
            done.set()
            thread.join(timeout=2)
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                motion_status = get("/v1/status/probe_motion")
                if motion_status["verification_available"]:
                    break
                time.sleep(0.1)
            assert not motion_status["verified"]
            assert motion_status["status"] in ("stopped", "expired")
            final_state = get("/v1/state")
            assert final_state["stop_latched"] and not final_state["command_active"]
            assert process.wait(timeout=120) == 0
            records = [
                json.loads(line)
                for line in (server_output / "policy_trace.jsonl").read_text().splitlines()
            ]
            saw_command = any(abs(row["observation"][48] - 0.08) < 1e-6 for row in records)
            assert saw_command, (
                "HTTP ACK alone is insufficient: command never reached actual ONNX inputs"
            )
            assert all(abs(x) < 1e-9 for x in records[-1]["observation"][48:51])
            receipt = {
                "evidence_kind": "LIVE_LAB_NEWTON_HTTP_ONNX_STOP_AND_RTX_PIXELS",
                "health": health,
                "initial_native_state": state,
                "camera_headers": headers,
                "calibration": info,
                "claim_without_token": claim,
                "accepted": accepted,
                "duplicate": duplicate,
                "stop": stopped,
                "motion_status": motion_status,
                "actual_neural_command_observed": saw_command,
                "final_neural_command": records[-1]["observation"][48:51],
                "physical_walk_success": False,
                "note": "This verifies actual native transport and priority stop, not successful locomotion.",
            }
            (args.output / "http_receipt.json").write_text(json.dumps(receipt, indent=2))
            print(json.dumps(receipt, indent=2), flush=True)
        finally:
            done.set()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()

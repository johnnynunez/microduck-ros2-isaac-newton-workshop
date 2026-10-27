"""Loopback-only transport v1. HTTP threads never touch simulator objects."""

import json
import re
import threading
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from microduck_workshop.contracts import PROTOCOL_VERSION, ContractError, MotionCommand

from .intent import ObservationProof


@dataclass(frozen=True)
class Frame:
    jpeg: bytes
    episode_id: str
    sequence: int
    sim_time: float
    capture_monotonic_s: float


class SnapshotStore:
    def __init__(self, owner, *, runtime):
        self.owner = owner
        self.runtime = deepcopy(runtime)
        self.lock = threading.Lock()
        self.state = None
        self.camera = None
        self.overview = None
        self.camera_info = None
        self.ready = False

    def publish_state(self, sample):
        # Explicit allowlist: no world pose, perfect odometry or GT orientation.
        names = (
            "sequence",
            "sim_time",
            "capture_monotonic_s",
            "joint_names",
            "joint_position",
            "joint_velocity",
            "imu",
        )
        state = {name: deepcopy(sample[name]) for name in names}
        state["imu"] = {
            name: state["imu"][name] for name in ("angular_velocity", "linear_acceleration")
        }
        state["episode_id"] = self.owner.episode_id
        json.dumps(state, allow_nan=False)
        with self.lock:
            self.state = state
            self.ready = True

    def publish_camera(self, frame, calibration, *, overview=False):
        if frame.episode_id != self.owner.episode_id or not frame.jpeg.startswith(b"\xff\xd8"):
            raise ValueError("invalid frame epoch or JPEG")
        with self.lock:
            if overview:
                self.overview = frame
            else:
                self.camera_info = deepcopy(calibration)
                self.camera = frame

    def health(self):
        with self.owner.lock, self.lock:
            return {
                "protocol_version": PROTOCOL_VERSION,
                "ready": self.ready,
                "physics": "newton",
                "episode_id": self.owner.episode_id,
                "generation": self.owner.generation,
                "sim_time": self.state["sim_time"] if self.state else 0.0,
                "runtime": deepcopy(self.runtime),
            }

    def get_state(self):
        with self.owner.lock, self.lock:
            if self.state is None:
                raise LookupError("native state is not available")
            self.owner.watchdog()
            return dict(
                deepcopy(self.state),
                command_active=self.owner._pending is not None,
                stop_latched=self.owner.stop_latched,
            )


def _exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ContractError(f"body requires exactly {sorted(keys)}")
    return value


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(1.0)

    def log_message(self, *_):
        pass  # Never record lease secrets or request bodies.

    def _send(self, code, value, *, jpeg=False, headers=None):
        payload = value if jpeg else json.dumps(value, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "image/jpeg" if jpeg else "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        for key, header_value in (headers or {}).items():
            self.send_header(key, str(header_value))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        store = self.server.store
        path = urlsplit(self.path).path
        try:
            if path == "/v1/health":
                return self._send(200, store.health())
            if path == "/v1/state":
                return self._send(200, store.get_state())
            if path.startswith("/v1/status/"):
                return self._send(200, store.owner.status(path.removeprefix("/v1/status/")))
            with store.lock:
                if path == "/v1/camera_info":
                    if store.camera_info is None:
                        raise LookupError("camera calibration/frame is not available")
                    value = deepcopy(store.camera_info)
                elif path in ("/v1/camera", "/v1/overview"):
                    frame = store.camera if path == "/v1/camera" else store.overview
                    if frame is None:
                        raise LookupError("real rendered frame is not available")
                    value = frame
                else:
                    return self._send(404, {"reason": "unknown endpoint"})
            if isinstance(value, Frame):
                return self._send(
                    200,
                    value.jpeg,
                    jpeg=True,
                    headers={
                        "X-Microduck-Episode": value.episode_id,
                        "X-Microduck-Sequence": value.sequence,
                        "X-Microduck-Sim-Time": value.sim_time,
                        "X-Microduck-Capture-Monotonic": value.capture_monotonic_s,
                    },
                )
            return self._send(200, value)
        except LookupError as exc:
            return self._send(503, {"reason": str(exc)})
        except (ValueError, ContractError) as exc:
            return self._send(400, {"reason": str(exc)})

    def do_POST(self):
        owner = self.server.store.owner

        def proof():
            names = ("Episode", "Sequence", "Deadline")
            values = [self.headers.get("X-Workshop-Observation-" + name) for name in names]
            if all(value is None for value in values):
                return None
            if any(value is None for value in values) or not re.fullmatch(r"[0-9]+", values[1]):
                raise ContractError("incomplete or malformed observation proof headers")
            return ObservationProof(values[0], int(values[1]), float(values[2]))

        try:
            if self.headers.get("Transfer-Encoding"):
                raise ContractError("chunked requests are not supported")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise ContractError("body must be 1..8192 bytes")
            body = json.loads(self.rfile.read(length))
            path = urlsplit(self.path).path
            if path == "/v1/claim":
                result = owner.claim(_exact(body, ["owner_id"])["owner_id"])
            elif path == "/v1/command":
                result = owner.submit(
                    MotionCommand.from_dict(body), self.headers.get("X-Workshop-Lease")
                )
            elif path == "/v1/renew":
                episode_id = _exact(body, ["episode_id"])["episode_id"]
                token = self.headers.get("X-Workshop-Lease")
                try:
                    renewal_proof = proof()
                except (ValueError, TypeError, ContractError):
                    # Parsing must not bypass revocation, nor may a malformed
                    # unauthenticated request revoke somebody else's step.
                    owner.reject_renewal(episode_id, token)
                    raise
                result = owner.renew(episode_id, token, renewal_proof)
            elif path == "/v1/step":
                result = owner.submit_step(
                    MotionCommand.from_dict(body), self.headers.get("X-Workshop-Lease"), proof()
                )
            elif path == "/v1/stop":
                body = _exact(body, ["episode_id", "latch"])
                result = owner.stop(body["episode_id"], latch=body["latch"])
            else:
                return self._send(404, {"reason": "unknown endpoint"})
            return self._send(200, result)
        except (ValueError, TypeError, ContractError) as exc:
            return self._send(
                409,
                {
                    "accepted": False,
                    "episode_id": owner.episode_id,
                    "request_id": body.get("request_id", "")
                    if isinstance(locals().get("body"), dict)
                    else "",
                    "generation": owner.generation,
                    "status": "rejected",
                    "reason": str(exc),
                },
            )


@contextmanager
def serve(store, *, port=8766):
    """Bind only loopback; priority stop and watchdog are independent threads."""
    server = _Server(("127.0.0.1", port), _Handler)
    server.store = store
    done = threading.Event()

    def watchdog():
        while not done.wait(0.02):
            store.owner.watchdog()

    threads = [
        threading.Thread(target=server.serve_forever, daemon=True),
        threading.Thread(target=watchdog, daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        yield server
    finally:
        done.set()
        server.shutdown()
        server.server_close()
        for thread in threads:
            thread.join(timeout=2)

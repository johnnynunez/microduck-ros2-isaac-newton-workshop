"""Read-only native identity binding for the student's CASCADE provider receipts."""

import json
import socket
import threading
import time
from http.client import HTTPConnection
from urllib.parse import urlsplit

IDENTITY_TIMEOUT_S = 3.0


def verify_policy_health(health, expected, *, episode_id):
    runtime = health.get("runtime", {})
    profile = runtime.get("step_profile") or {}
    if (
        health.get("ready") is not True
        or health.get("physics") != "newton"
        or health.get("episode_id") != episode_id
        or runtime.get("policy_sha256") != expected["policy_sha256"]
        or runtime.get("policy_manifest_sha256") != expected["manifest_sha256"]
        or profile.get("policy_sha256") != expected["policy_sha256"]
        or profile.get("admission_sha256") != expected["admission_sha256"]
        or profile.get("validation_status") != "NATIVE_VALIDATED"
    ):
        raise ValueError(
            "native health does not match the selected admitted student policy/episode"
        )
    return dict(expected, episode_id=episode_id, scope="identity_only_not_physical_acceptance")


def read_policy_identity(manifest_path, admission_path, health_url, *, episode_id):
    from .student import load_admission, load_manifest

    if (
        any(ord(c) <= 32 or ord(c) == 127 for c in health_url)
        or "?" in health_url
        or "#" in health_url
    ):
        raise ValueError("exact native identity URL required; no whitespace/query/fragment")
    parsed = urlsplit(health_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.path != "/v1/health"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.port is None
    ):
        raise ValueError("explicit loopback http://host:port/v1/health URL required")
    manifest = load_manifest(manifest_path)
    admission = load_admission(admission_path, manifest)
    expected = {
        "policy_sha256": manifest["policy_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
        "admission_sha256": admission["admission_sha256"],
    }
    # Dedicated direct socket: no environment proxies, global urllib opener,
    # redirects, credentials or alternate paths. Pin localhost to loopback too.
    connection = HTTPConnection(
        "127.0.0.1" if parsed.hostname == "localhost" else parsed.hostname,
        parsed.port,
        timeout=IDENTITY_TIMEOUT_S,
    )
    deadline = time.monotonic() + IDENTITY_TIMEOUT_S
    timer = None
    try:
        connection.connect()
        sock = connection.sock

        def expire():
            # shutdown also interrupts HTTPResponse's buffered file reads. A
            # per-recv timeout alone can be kept alive forever by trickled bytes.
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        timer = threading.Timer(max(0, deadline - time.monotonic()), expire)
        timer.daemon = True
        timer.start()
        connection.request("GET", "/v1/health", headers={"Connection": "close"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("native identity requires a direct HTTP 200 response")
        raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("oversized native health response")
        health = json.loads(raw)
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()
        connection.close()
    return verify_policy_health(health, expected, episode_id=episode_id)

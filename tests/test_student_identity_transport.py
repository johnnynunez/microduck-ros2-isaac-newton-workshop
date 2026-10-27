"""Real HTTP transport regressions; metadata fixtures are not physical evidence."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from microduck_workshop.policy import identity, student


@pytest.fixture
def endpoint(monkeypatch):
    import urllib.request

    monkeypatch.setattr(urllib.request, "_opener", None)
    monkeypatch.setattr(
        student, "load_manifest", lambda _: {"policy_sha256": "p", "manifest_sha256": "m"}
    )
    monkeypatch.setattr(student, "load_admission", lambda *a, **kw: {"admission_sha256": "a"})
    health = {
        "ready": True,
        "physics": "newton",
        "episode_id": "ep",
        "runtime": {
            "policy_sha256": "p",
            "policy_manifest_sha256": "m",
            "step_profile": {
                "policy_sha256": "p",
                "admission_sha256": "a",
                "validation_status": "NATIVE_VALIDATED",
            },
        },
    }
    seen = []
    state = {"redirect": False}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            if state.get("slow"):
                try:
                    for byte in b"HTTP/1.1 200 OK\r\n" * 100:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.01)
                except OSError:
                    pass
                return
            if state["redirect"] and self.path == "/v1/health":
                self.send_response(302)
                self.send_header("Location", "/not-health")
                self.end_headers()
            else:
                raw = json.dumps(health).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    for name in list(__import__("os").environ):
        if "proxy" in name.lower():
            monkeypatch.delenv(name)
    yield f"http://127.0.0.1:{server.server_port}", seen, state
    server.shutdown()
    server.server_close()
    thread.join()


def read(url):
    return identity.read_policy_identity("fixture", "fixture", url, episode_id="ep")


def test_identity_accepts_only_direct_health(endpoint):
    base, seen, _ = endpoint
    assert read(base + "/v1/health")["policy_sha256"] == "p"
    assert seen == ["/v1/health"]


def test_identity_total_deadline_catches_trickled_headers(endpoint, monkeypatch):
    base, _, state = endpoint
    state["slow"] = True
    monkeypatch.setattr(identity, "IDENTITY_TIMEOUT_S", 0.1, raising=False)
    start = time.monotonic()
    with pytest.raises(Exception):
        read(base + "/v1/health")
    assert time.monotonic() - start < 0.5


@pytest.mark.parametrize("suffix", ["?", "#", "?q=1", "/", "\n"])
def test_identity_rejects_nonexact_endpoint(endpoint, suffix):
    base, seen, _ = endpoint
    with pytest.raises(ValueError):
        read(base + "/v1/health" + suffix)
    assert seen == []


def test_identity_does_not_follow_real_redirect(endpoint):
    base, seen, state = endpoint
    state["redirect"] = True
    with pytest.raises(Exception):
        read(base + "/v1/health")
    assert seen == ["/v1/health"]


def test_identity_does_not_use_environment_proxy(endpoint, monkeypatch):
    base, seen, _ = endpoint
    monkeypatch.setenv("http_proxy", base)
    monkeypatch.setenv("no_proxy", "")
    with pytest.raises(Exception):
        read("http://127.0.0.1:1/v1/health")
    assert seen == []


@pytest.mark.parametrize("userinfo", ["", ":", "user", "user:"])
def test_identity_rejects_any_userinfo_presence(endpoint, userinfo):
    base, seen, _ = endpoint
    with pytest.raises(ValueError):
        read(base.replace("http://", f"http://{userinfo}@") + "/v1/health")
    assert seen == []

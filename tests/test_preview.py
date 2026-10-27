"""Synthetic HTTP fixtures only: these tests are not real-camera acceptance."""

import contextlib
import http.client
import importlib.util
import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest


@contextlib.contextmanager
def running(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def request(server, path, method="GET", headers=None):
    connection = http.client.HTTPConnection(*server.server_address, timeout=3)
    connection.request(method, path, headers=headers or {})
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


def test_static_portal_and_read_only_boundary():
    assert importlib.util.find_spec("microduck_workshop.preview"), "preview module is missing"
    from microduck_workshop.preview import create_server

    with running(create_server(port=0)) as server:
        status, headers, body = request(server, "/")
        assert status == 200
        assert b"MicroDuck" in body
        assert headers["Content-Type"].startswith("text/html")
        assert headers["Cache-Control"] == "no-store"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "default-src 'self'" in headers["Content-Security-Policy"]
        for path, mime in (
            ("/index.html", "text/html"),
            ("/app.js", "text/javascript"),
            ("/style.css", "text/css"),
        ):
            status, headers, body = request(server, path)
            assert status == 200 and body
            assert headers["Content-Type"].startswith(mime)
        for path in (
            "/v1/stop",
            "/v1/state",
            "/../pyproject.toml",
            "/head.jpg?url=http://evil",
            "/?x=1",
            "/%68ead.jpg",
            "//head.jpg",
            "http://example.com/head.jpg",
        ):
            assert request(server, path)[0] == 404
        for method in ("POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "CONNECT", "TRACE"):
            status, headers, _ = request(server, "/status", method)
            assert status == 405
            assert headers["Allow"] == "GET"


@pytest.mark.parametrize(
    "upstream",
    [
        "https://127.0.0.1:8766",
        "http://127.0.0.1:8765",
        "http://127.1:8766",
        "http://0.0.0.0:8766",
        "http://example.com:8766",
        "http://localhost.evil:8766",
        "http://user:secret@localhost:8766",
        "http://localhost:8766/",
        "http://localhost:8766/x",
        "http://localhost:8766?url=x",
        "http://localhost:8766#x",
        "http://[::1]:8766",
    ],
)
def test_upstream_rejects_everything_except_exact_loopback_origins(upstream):
    from microduck_workshop.preview import create_server

    with pytest.raises(ValueError):
        create_server(upstream=upstream, port=0)


@pytest.fixture
def synthetic_upstream(monkeypatch):
    """A CPU-only synthetic fixture, never evidence of an actual camera."""
    from microduck_workshop import preview

    data = SimpleNamespace(code=200, body=b"", headers={}, seen=[], delay=0, drip=False, routes={})

    class SyntheticHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            data.seen.append((self.path, dict(self.headers)))
            code, headers, body = data.routes.get(self.path, (data.code, data.headers, data.body))
            if callable(headers):
                headers = headers()
            self.send_response(code)
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            try:
                if data.drip:
                    for byte in body:
                        time.sleep(data.delay)
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                else:
                    time.sleep(data.delay)
                    self.wfile.write(body)
            except OSError:
                pass

    with running(ThreadingHTTPServer(("127.0.0.1", 0), SyntheticHandler)) as server:
        real_connection = http.client.HTTPConnection

        def connection(host, port, **kwargs):
            assert host == "127.0.0.1" and port == 8766
            return real_connection("127.0.0.1", server.server_port, **kwargs)

        # Redirect only the internal connection to our ephemeral test fixture, not the API.
        monkeypatch.setattr(preview, "HTTPConnection", connection, raising=False)
        with running(preview.create_server(port=0)) as portal:
            data.portal = portal
            yield data


def synthetic_health(**changes):
    return dict(
        protocol_version=1,
        ready=True,
        physics="newton",
        episode_id="SYNTHETIC",
        generation=3,
        sim_time=1.25,
        **changes,
    )


def test_status_allowlist_only_and_no_forwarded_credentials(synthetic_upstream):
    source = synthetic_upstream
    source.headers = {"Content-Type": "application/json", "Set-Cookie": "secret=bad"}
    health = synthetic_health(
        runtime={"path": "/private", "lease_token": "secret"}, world_pose=[1, 2, 3], token="secret"
    )
    source.body = json.dumps(health).encode()
    status, headers, body = request(
        source.portal,
        "/status",
        headers={
            "Authorization": "Bearer secret",
            "Cookie": "secret=bad",
            "X-Workshop-Lease": "secret",
        },
    )
    assert status == 200
    assert json.loads(body) == {
        key: health[key]
        for key in ("protocol_version", "ready", "physics", "episode_id", "generation", "sim_time")
    }
    assert "Set-Cookie" not in headers
    assert source.seen[0][0] == "/v1/health"
    assert not {"Authorization", "Cookie", "X-Workshop-Lease"} & source.seen[0][1].keys()


@pytest.mark.parametrize(
    "key,value",
    [
        ("protocol_version", True),
        ("protocol_version", 2),
        ("ready", 1),
        ("physics", {}),
        ("episode_id", "bad\r\nheader"),
        ("episode_id", {}),
        ("generation", True),
        ("generation", -1),
        ("generation", 2**60),
        ("sim_time", "1.2"),
        ("sim_time", float("nan")),
        ("sim_time", float("inf")),
        ("sim_time", -1),
    ],
)
def test_reject_untrusted_status_metadata(synthetic_upstream, key, value):
    source = synthetic_upstream
    source.headers = {"Content-Type": "application/json"}
    health = synthetic_health()
    health[key] = value
    source.body = json.dumps(health).encode()
    assert request(source.portal, "/status")[0] == 503


def test_reject_nonobject_duplicate_or_nonfinite_json(synthetic_upstream):
    source = synthetic_upstream
    source.headers = {"Content-Type": "application/json"}
    for body in (
        b"[]",
        b"null",
        b"not json",
        b'{"ready":true,"ready":false}',
        json.dumps(synthetic_health(runtime={"x": float("nan")})).encode(),
    ):
        source.body = body
        assert request(source.portal, "/status")[0] == 503


def test_json_float_overflow_is_invalid_even_in_private_metadata(synthetic_upstream):
    source = synthetic_upstream
    source.headers = {"Content-Type": "application/json"}
    source.body = (
        json.dumps(synthetic_health(runtime={"x": "OVERFLOW"}))
        .replace('"OVERFLOW"', "1e999")
        .encode()
    )
    assert request(source.portal, "/status")[0] == 503


def synthetic_frame(source, *, age=0.1):
    source.body = b"\xff\xd8SYNTHETIC-NOT-A-REAL-CAMERA\xff\xd9"
    source.headers = {
        "Content-Type": "image/jpeg",
        "X-Microduck-Episode": "SYNTHETIC",
        "X-Microduck-Sequence": "42",
        "X-Microduck-Sim-Time": "1.2500",
        "X-Microduck-Capture-Monotonic": str(time.monotonic() - age),
        "X-Workshop-Lease": "never-forward",
    }


@pytest.mark.parametrize(
    "route,upstream", [("/head.jpg", "/v1/camera"), ("/overview.jpg", "/v1/overview")]
)
def test_frame_bytes_atomic_provenance_and_capture_age(synthetic_upstream, route, upstream):
    source = synthetic_upstream
    synthetic_frame(source)
    status, headers, body = request(source.portal, route)
    assert status == 200 and body == source.body
    assert headers["Content-Type"] == "image/jpeg"
    for key in ("Episode", "Sequence", "Sim-Time", "Capture-Monotonic"):
        name = "X-Microduck-" + key
        assert headers[name] == source.headers[name]
    assert 0.1 <= float(headers["X-Preview-Age-S"]) < 0.5
    assert headers["X-Preview-State"] == "fresh"
    assert "X-Workshop-Lease" not in headers
    assert source.seen[0][0] == upstream
    synthetic_frame(source, age=5)
    status, headers, _ = request(source.portal, route)
    assert status == 200 and headers["X-Preview-State"] == "stale"
    assert float(headers["X-Preview-Age-S"]) >= 5


@pytest.mark.parametrize(
    "key,value",
    [
        ("X-Microduck-Episode", "<script>"),
        ("X-Microduck-Sequence", "-1"),
        ("X-Microduck-Sequence", "1.0"),
        ("X-Microduck-Sequence", str(2**60)),
        ("X-Microduck-Sim-Time", "nan"),
        ("X-Microduck-Sim-Time", "-1"),
        ("X-Microduck-Capture-Monotonic", "inf"),
        ("X-Microduck-Capture-Monotonic", "1e99"),
        ("X-Microduck-Capture-Monotonic", ""),
        ("Content-Type", "text/html"),
    ],
)
def test_frame_metadata_is_not_trusted(synthetic_upstream, key, value):
    source = synthetic_upstream
    synthetic_frame(source)
    source.headers[key] = value
    assert request(source.portal, "/head.jpg")[0] == 503


def test_missing_frame_invalid_jpeg_and_missing_provenance(synthetic_upstream):
    source = synthetic_upstream
    source.code = 503
    assert request(source.portal, "/head.jpg")[0] == 503
    source.code = 200
    synthetic_frame(source)
    source.body = b"not a JPEG"
    assert request(source.portal, "/head.jpg")[0] == 503
    synthetic_frame(source)
    del source.headers["X-Microduck-Episode"]
    assert request(source.portal, "/head.jpg")[0] == 503


@pytest.mark.parametrize("route", ["/head.jpg", "/overview.jpg", "/status"])
def test_no_redirect_follow_or_environment_proxy(synthetic_upstream, monkeypatch, route):
    source = synthetic_upstream
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    source.code = 302
    source.headers = {"Location": "http://example.invalid/private", "X-Secret": "hidden"}
    status, headers, body = request(source.portal, route)
    assert status == 503
    assert len(source.seen) == 1
    assert "Location" not in headers and b"hidden" not in body
    source.code = 200
    if route == "/status":
        source.headers = {"Content-Type": "application/json"}
        source.body = json.dumps(synthetic_health()).encode()
    else:
        synthetic_frame(source)
    assert request(source.portal, route)[0] == 200


def test_response_byte_caps(synthetic_upstream):
    from microduck_workshop import preview

    source = synthetic_upstream
    synthetic_frame(source)
    source.body = b"\xff\xd8" + b"x" * preview.MAX_JPEG_BYTES + b"\xff\xd9"
    assert request(source.portal, "/head.jpg")[0] == 503
    source.headers = {"Content-Type": "application/json"}
    source.body = b" " * (preview.MAX_STATUS_BYTES + 1)
    assert request(source.portal, "/status")[0] == 503


def test_slow_drip_has_total_deadline(synthetic_upstream, monkeypatch):
    from microduck_workshop import preview

    monkeypatch.setattr(preview, "UPSTREAM_TIMEOUT_S", 0.2)
    source = synthetic_upstream
    synthetic_frame(source)
    source.delay, source.drip = 0.04, True
    start = time.monotonic()
    assert request(source.portal, "/head.jpg")[0] == 503
    assert time.monotonic() - start < 0.7


def test_cli_actual_http_and_invalid_origin():
    from microduck_workshop import preview

    env = dict(os.environ, PYTHONPATH=str(Path(preview.__file__).parent.parent))
    command = [sys.executable, "-m", "microduck_workshop.preview"]
    rejected = subprocess.run(
        command + ["--upstream", "http://example.com:8766"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert rejected.returncode == 2 and "upstream must be" in rejected.stderr
    process = subprocess.Popen(
        command + ["--upstream", "http://localhost:8766", "--port", "0"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        line = process.stdout.readline()
        assert line.startswith("Read-only preview: http://127.0.0.1:")
        port = int(line.rsplit(":", 1)[1])
        server = SimpleNamespace(server_address=("127.0.0.1", port))
        assert request(server, "/")[0] == 200
        assert request(server, "/v1/stop", "POST")[0] == 405
        assert request(server, "/v1/state")[0] == 404
    finally:
        process.send_signal(signal.SIGINT)
        _stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0 and not stderr

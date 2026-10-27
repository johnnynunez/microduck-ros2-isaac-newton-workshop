"""Readiness regressions: synthetic HTTP fixtures, NOT live/GPU acceptance."""
import importlib.util
import json
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def helper():
    spec = importlib.util.spec_from_file_location("readiness_workshop", ROOT / "notebooks/workshop.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cold_start_default_and_override_are_finite_bounded(tmp_path, monkeypatch):
    m = helper()
    session = m.Session(ROOT, work=tmp_path)
    clock = [0.0]
    monkeypatch.setattr(m, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0] + s)))
    monkeypatch.setattr(session, "owned", lambda *a, **kw: None)
    monkeypatch.setattr(session, "get_json", lambda *a, **kw: {"ready": False})
    monkeypatch.delenv("WORKSHOP_SIM_STARTUP_TIMEOUT", raising=False)
    with pytest.raises(RuntimeError, match="readiness deadline"):
        session.wait_sim("http://127.0.0.1:1")
    assert clock[0] == 600
    clock[0] = 0
    monkeypatch.setenv("WORKSHOP_SIM_STARTUP_TIMEOUT", "240")
    with pytest.raises(RuntimeError, match="readiness deadline"):
        session.wait_sim("http://127.0.0.1:1")
    assert clock[0] == 240
    for value in ("nan", "inf", "0", "-1", "1801", "bad"):
        monkeypatch.setenv("WORKSHOP_SIM_STARTUP_TIMEOUT", value)
        with pytest.raises(ValueError, match="startup timeout"):
            session.wait_sim("http://127.0.0.1:1")
    # Explicit per-call override remains supported and independent of bad env.
    clock[0] = 0
    with pytest.raises(RuntimeError, match="readiness deadline"):
        session.wait_sim("http://127.0.0.1:1", timeout=2)
    assert clock[0] == 2


@pytest.fixture
def sensor_server():
    import time
    scenario = {"camera_reads": 0, "state_reads": 0, "requests": [], "fault": None}
    episode = "ep-synthetic-unit-fixture"
    # Deliberately test-only bytes: this does NOT certify a rendered camera.
    payload = b"\xff\xd8synthetic-unit-fixture\xff\xd9"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            scenario["requests"].append(self.path)
            headers = {}
            code = 200
            capture = time.monotonic()
            if self.path == "/v1/health":
                value = {"ready": True, "physics": "newton", "episode_id": episode,
                         "runtime": {"isaacsim": "6.2.0.0"}}
            elif self.path == "/v1/state":
                scenario["state_reads"] += 1
                value = {"episode_id": episode, "capture_monotonic_s": capture,
                         "sequence": 20, "sim_time": .1, "stop_latched": False}
                if scenario["fault"] == "state-stale":
                    value["capture_monotonic_s"] -= 1
                if scenario["fault"] == "state-foreign":
                    value["episode_id"] = "foreign"
                if scenario["fault"] == "stopped":
                    value["stop_latched"] = True
            elif self.path == "/v1/camera_info":
                value = {"frame_id": "microduck_head_optical", "width": 320, "height": 240}
            elif self.path == "/v1/camera":
                scenario["camera_reads"] += 1
                n = scenario["camera_reads"]
                if n == 1:
                    code, value = 503, {"reason": "camera not published yet"}
                else:
                    value = payload
                    headers = {"X-Microduck-Episode": episode, "X-Microduck-Sequence": "20",
                               "X-Microduck-Sim-Time": ".1", "X-Microduck-Capture-Monotonic": str(capture)}
                    if n == 2 or scenario["fault"] == "camera-stale":
                        headers["X-Microduck-Capture-Monotonic"] = str(capture - 1)
                    if scenario["fault"] == "camera-foreign":
                        headers["X-Microduck-Episode"] = "foreign"
            else:
                code, value = 404, {}
            body = value if isinstance(value, bytes) else json.dumps(value).encode()
            self.send_response(code)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            scenario["requests"].append("POST " + self.path)
            self.send_error(405)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield scenario, f"http://127.0.0.1:{server.server_port}", episode, payload
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_native_ready_waits_for_real_http_camera_not_health_only(tmp_path, monkeypatch, sensor_server):
    scenario, url, episode, _ = sensor_server
    s = helper().Session(ROOT, work=tmp_path)
    monkeypatch.setattr(s, "owned", lambda *a, **kw: None)  # No Docker/GPU in this fixture.
    result = s.wait_sim(url, timeout=5)
    assert result["episode_id"] == episode
    assert scenario["camera_reads"] >= 3, "503 and stale frame must not establish readiness"
    assert scenario["state_reads"] >= 3
    assert "/v1/camera_info" in scenario["requests"]
    assert not any(path.startswith("POST") for path in scenario["requests"])
    assert s.state()["stages"] == {}, "Readiness must not manufacture a completion receipt"


@pytest.mark.parametrize("fault", ["state-stale", "camera-stale", "state-foreign", "camera-foreign", "stopped"])
def test_sensor_gate_refuses_stale_foreign_stopped_without_motion(tmp_path, monkeypatch, sensor_server, fault):
    scenario, url, episode, _ = sensor_server
    scenario.update(fault=fault, camera_reads=2)
    s = helper().Session(ROOT, work=tmp_path)
    monkeypatch.setattr(s, "owned", lambda *a, **kw: None)
    with pytest.raises(RuntimeError):
        s.wait_sensors(url, expected_episode=episode, timeout=.15)
    assert not any(path.startswith("POST") for path in scenario["requests"])
    assert not list((tmp_path / "runs").glob("*"))


def test_snapshot_saves_exact_checked_bytes_and_original_headers(tmp_path, monkeypatch, sensor_server):
    scenario, url, episode, payload = sensor_server
    s = helper().Session(ROOT, work=tmp_path)
    monkeypatch.setattr(s, "owned", lambda *a, **kw: None)
    path = s.camera_snapshot(url, expected_episode=episode, label="unit-fixture")
    assert path.read_bytes() == payload
    headers = json.loads(path.with_name("capture.json").read_text())
    assert headers["X-Microduck-Episode"] == episode
    assert headers["X-Microduck-Sequence"] == "20"
    assert scenario["camera_reads"] >= 3


@pytest.mark.parametrize("key,value", [("X-Microduck-Sequence", "nan"), ("X-Microduck-Sequence", "-1"),
                                       ("X-Microduck-Sim-Time", "nan"), ("X-Microduck-Sim-Time", "-1")])
def test_readiness_camera_requires_valid_capture_headers(key, value):
    import time
    m = helper()
    headers = {"X-Microduck-Episode": "fixture", "X-Microduck-Sequence": "20",
               "X-Microduck-Sim-Time": ".1", "X-Microduck-Capture-Monotonic": str(time.monotonic())}
    headers[key] = value
    with pytest.raises(RuntimeError, match="capture header"):
        m.check_camera(headers, b"\xff\xd8synthetic-test\xff\xd9", "fixture")


def test_readiness_rejects_truncated_jpeg():
    import time
    m = helper()
    headers = {"X-Microduck-Episode": "fixture", "X-Microduck-Sequence": "20",
               "X-Microduck-Sim-Time": ".1", "X-Microduck-Capture-Monotonic": str(time.monotonic())}
    with pytest.raises(RuntimeError, match="JPEG"):
        m.check_camera(headers, b"\xff\xd8truncated-test", "fixture")

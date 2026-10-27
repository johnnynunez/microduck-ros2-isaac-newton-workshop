"""Host-only orchestration checks; none assert live robot acceptance."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def helper():
    path = ROOT / "notebooks/workshop.py"
    assert path.is_file(), "Notebook orchestration helper is missing"
    spec = importlib.util.spec_from_file_location("notebook_workshop", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_root_discovery_and_real_bounded_command(tmp_path):
    module = helper()
    assert module.find_root(ROOT / "src/microduck_workshop") == ROOT
    with pytest.raises(RuntimeError, match="repository"):
        module.find_root(tmp_path)
    session = module.Session(ROOT, work=tmp_path / "session")
    result = session.run([sys.executable, "-c", "print('actual child process')"], timeout=3)
    assert result.stdout.strip() == "actual child process"
    assert list((session.work / "logs").glob("*.log"))
    with pytest.raises(RuntimeError, match="exit 3"):
        session.run([sys.executable, "-c", "raise SystemExit(3)"], timeout=3)


def test_state_requires_prior_stages_and_detects_changed_artifacts(tmp_path):
    module = helper()
    session = module.Session(ROOT, work=tmp_path / "session")
    with pytest.raises(RuntimeError, match="01"):
        session.require("01")
    artifact = tmp_path / "real.txt"
    artifact.write_text("first")
    session.complete("01", {"kind": "CPU_TUTORIAL"}, artifacts=[artifact])
    assert module.Session(ROOT, work=session.work).require("01")["kind"] == "CPU_TUTORIAL"
    artifact.write_text("changed")
    with pytest.raises(RuntimeError, match="changed"):
        session.require("01")


def test_container_command_has_caps_and_isolation(tmp_path):
    session = helper().Session(ROOT, work=tmp_path)
    argv = session.container_command("tutorial", "example:image", ["sleep", "30"])
    assert argv[:3] == ["docker", "run", "-d"]
    assert argv[argv.index("--network") + 1] == "none"
    assert argv[argv.index("--memory") + 1] == "4g"
    assert argv[argv.index("--cpus") + 1] == "2"
    assert "ROS_DOMAIN_ID=71" in argv
    assert argv[argv.index("--name") + 1].startswith("roscon-nb-")
    assert "--privileged" not in argv and "--gpus" not in argv
    with pytest.raises(ValueError, match="role"):
        session.container_command("../other", "image", [])


def test_gpu_requires_explicit_eula_before_any_launch(tmp_path):
    session = helper().Session(ROOT, work=tmp_path)
    with pytest.raises(RuntimeError, match="EULA"):
        session.gpu_preflight("0", accept_eula=False)
    with pytest.raises(ValueError, match="GPU"):
        session.gpu_options("0,1")
    options = session.gpu_options("0")
    assert options[options.index("--gpus") + 1] == "device=0"


def test_network_reads_refuse_remote_urls_and_port_collision(tmp_path):
    import socket
    session = helper().Session(ROOT, work=tmp_path)
    with pytest.raises(ValueError, match="loopback"):
        session.get_json("https://example.com/v1/health")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        with pytest.raises(RuntimeError, match="occupied"):
            session.port_available(sock.getsockname()[1])


def test_camera_headers_reject_stale_foreign_and_nonfinite():
    import time
    module = helper()
    headers = {"X-Microduck-Episode": "ep-unit-fixture", "X-Microduck-Sequence": "5",
               "X-Microduck-Sim-Time": ".025",
               "X-Microduck-Capture-Monotonic": str(time.monotonic())}
    module.check_camera(headers, b"\xff\xd8unit-test-not-rendered\xff\xd9", "ep-unit-fixture")
    with pytest.raises(RuntimeError, match="episode"):
        module.check_camera(headers, b"\xff\xd8", "different")
    for value in ("nan", "inf", str(time.monotonic() - 1), str(time.monotonic() + 10)):
        headers["X-Microduck-Capture-Monotonic"] = value
        with pytest.raises(RuntimeError, match="capture"):
            module.check_camera(headers, b"\xff\xd8", "ep-unit-fixture")


def test_checkpoint_refuses_source_changes_and_invalidates_later_stages(tmp_path):
    root = tmp_path / "repo"
    source = root / "src/microduck_workshop/example.py"
    source.parent.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='test'\n")
    source.write_text("VALUE = 1\n")
    session = helper().Session(root)
    session.complete("03", {"episode_id": "unit-fixture"})
    session.complete("04", {"kind": "unit-fixture"})
    session.complete("03", {"episode_id": "new-unit-fixture"})
    with pytest.raises(RuntimeError, match="04"):
        session.require("04")
    source.write_text("VALUE = 2\n")
    with pytest.raises(RuntimeError, match="source"):
        session.require("03")


def test_receipt_records_helper_ros_and_actual_container_identity_without_answer_binding(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import hashlib
    root = tmp_path / "repo"
    (root / "src/microduck_workshop").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    (root / "notebooks").mkdir()
    (root / "notebooks/workshop.py").write_text("# fixture helper\n")
    (root / "notebooks/01_ros2.ipynb").write_text("student prediction A")
    ros = root / "ros_ws/src/fixture/gateway.py"
    ros.parent.mkdir(parents=True)
    ros.write_text("# fixture ROS source\n")
    s = helper().Session(root)
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        if argv[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(stdout="sha256:tag-at-preflight\n")
        if argv[:2] == ["docker", "inspect"]:
            return SimpleNamespace(stdout="sha256:actual-container-image\n")
        return SimpleNamespace(stdout="unit-fixture-container-id\n")
    monkeypatch.setattr(s, "run", run)
    s.start("ros", "fixture:image", ["true"])
    s.complete("01", {"kind": "SYNTHETIC_UNIT_FIXTURE"})
    provenance = s.state()["stages"]["01"]["provenance"]
    assert provenance["images"]["ros"]["image_id"] == "sha256:actual-container-image"
    assert provenance["source_sha256"]["notebooks/workshop.py"] == hashlib.sha256(b"# fixture helper\n").hexdigest()
    assert "ros_ws/src/fixture/gateway.py" in provenance["source_sha256"]
    assert "notebooks/01_ros2.ipynb" not in provenance["source_sha256"]
    (root / "notebooks/01_ros2.ipynb").write_text("student prediction B")
    assert s.require("01")["kind"] == "SYNTHETIC_UNIT_FIXTURE"


def test_explicit_gate_reports_skipped_without_calling_action(tmp_path, capsys):
    session = helper().Session(ROOT, work=tmp_path)
    called = []
    assert session.step("gpu", False, lambda: called.append(True)) is None
    assert called == []
    output = capsys.readouterr().out
    assert "SKIPPED" in output and "PASS" not in output


def test_explicit_cpu_lane_prefix_and_ros_domain(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSHOP_NOTEBOOK_PREFIX", "roscon-nb-complete")
    monkeypatch.setenv("WORKSHOP_ROS_DOMAIN", "72")
    session = helper().Session(ROOT, work=tmp_path)
    args = session.container_command("test", "fixture:image", ["true"])
    assert session.name("test").startswith("roscon-nb-complete-")
    assert "ROS_DOMAIN_ID=72" in args and "ROS_DOMAIN_ID=71" not in args
    monkeypatch.setenv("WORKSHOP_ROS_DOMAIN", "999")
    with pytest.raises(ValueError, match="domain"):
        session.container_command("test", "fixture:image", ["true"])
    monkeypatch.setenv("WORKSHOP_NOTEBOOK_PREFIX", "bad/name")
    with pytest.raises(ValueError, match="prefix"):
        session.name("test")

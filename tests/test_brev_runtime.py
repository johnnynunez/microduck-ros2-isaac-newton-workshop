"""Deployment contracts; these never start GPU/cloud workloads."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sim_setup_requires_explicit_license_before_docker():
    result = subprocess.run(
        ["bash", "scripts/sim_setup.sh"],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "OMNI_KIT_ACCEPT_EULA": ""},
    )
    assert result.returncode == 2
    assert "--accept-nvidia-eula" in result.stderr


def test_start_requires_explicit_license_before_docker():
    result = subprocess.run(
        ["bash", "scripts/sim_start.sh"],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "OMNI_KIT_ACCEPT_EULA": ""},
    )
    assert result.returncode == 2
    assert "--accept-nvidia-eula" in result.stderr


def test_compose_isolates_sim_and_ros():
    result = subprocess.run(
        ["docker", "compose", "--profile", "agent", "config", "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "OMNI_KIT_ACCEPT_EULA": "", "WORKSHOP_GPU": "0"},
    )
    config = json.loads(result.stdout)
    services = config["services"]
    assert {"sim", "ros", "agent"} <= services.keys()
    sim = services["sim"]
    assert sim["mem_limit"] == "34359738368"
    # This is a distinct native-validated primitive, never the rejected velocity map.
    command = sim["command"]
    assert command[command.index("--step-profile") + 1] == "step-forward-v1"
    assert "--command-profile" not in command
    assert sim["environment"]["NVIDIA_DRIVER_CAPABILITIES"] == "graphics,compute,utility"
    assert sim["environment"]["OMNI_KIT_ACCEPT_EULA"] != "YES"
    assert services["ros"]["environment"]["ROS_AUTOMATIC_DISCOVERY_RANGE"] == "LOCALHOST"
    assert "tag_size:=0.20" in services["ros"]["command"]
    assert services["ros"]["ipc"] == "shareable"
    assert services["agent"]["ipc"] == "service:ros"
    assert all(service.get("ipc") != "host" for service in services.values())
    preview = services["preview"]
    assert preview["command"] == [
        "-m",
        "microduck_workshop.preview",
        "--bind",
        "127.0.0.1",
        "--port",
        "8765",
    ]
    assert services["agent"]["profiles"] == ["agent"]
    for service in services.values():
        assert service["restart"] == "no"
        assert not service.get("privileged")
        assert not service.get("ports")


def test_shell_entrypoints_parse():
    for name in ("sim_setup", "sim_start", "sim_stop", "brev_setup", "brev_start", "brev_stop"):
        subprocess.run(["bash", "-n", str(ROOT / "scripts" / (name + ".sh"))], check=True)


def test_brev_refuses_unacknowledged_setup_and_start():
    for name in ("brev_setup", "brev_start"):
        result = subprocess.run(
            ["bash", "scripts/" + name + ".sh"],
            check=False,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "--accept-nvidia-eula" in result.stderr


def test_images_include_provenance_and_not_host_runtime():
    for name in ("Dockerfile", "sim.Dockerfile"):
        dockerfile = (ROOT / "docker" / name).read_text()
        ignored = (ROOT / "docker" / (name + ".dockerignore")).read_text()
        assert "COPY provenance /opt/workshop/provenance" in dockerfile
        assert "!provenance/**" in ignored and "!NOTICE" in ignored
        assert ".workshop/runtime" not in dockerfile
        assert "OMNI_KIT_ACCEPT_EULA=YES" not in dockerfile

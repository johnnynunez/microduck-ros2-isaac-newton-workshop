"""Cold-image packaging declares student-policy dependencies explicitly."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sim_image_installs_declared_student_policy_requirement_without_repinning_sdk():
    dockerfile = (ROOT / "docker/sim.Dockerfile").read_text()
    ignore = (ROOT / "docker/sim.Dockerfile.dockerignore").read_text()
    assert "requirements-policy-training.txt" in next(
        line for line in dockerfile.splitlines() if line.startswith("COPY pyproject.toml")
    )
    assert "!requirements-policy-training.txt" in ignore.splitlines()
    install = next(line for line in dockerfile.splitlines() if line.startswith("RUN uv pip install"))
    assert "--no-deps" in install
    assert "-r /opt/workshop/requirements-policy-training.txt" in install

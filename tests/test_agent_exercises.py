"""Exercise grading uses fake CPU transport, never live actuation."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from test_agent_domain import FixtureGateway

from microduck_workshop.agent.domain import MicroduckDomain

ROOT = Path(__file__).parents[1]


def load_tools(path):
    spec = importlib.util.spec_from_file_location("capstone_tools", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_student_todos_fail_explicitly():
    student = load_tools(ROOT / "exercises/capstone/tools.py")
    if "raise NotImplementedError" not in (ROOT / "exercises/capstone/tools.py").read_text():
        pytest.skip("student has implemented the exercise; use the grading command")
    with pytest.raises(NotImplementedError):
        student.translate_observation({}, episode_id="e", frame_id="camera")
    with pytest.raises(NotImplementedError):
        student.step_forward(None, {})


def test_reference_solution_is_wired_to_actual_domain():
    tools = load_tools(ROOT / "solutions/capstone/tools.py")
    gateway = FixtureGateway()
    domain = MicroduckDomain(
        gateway,
        episode_id="episode-1",
        frame_id="microduck_camera_optical",
        observation_handler=tools.translate_observation,
        motion_handler=tools.step_forward,
    )
    assert domain.execute("observe", {})["signal"] == "GO"
    result = domain.execute("step_forward", {})
    assert result["accepted"] is True
    assert result["verified"] is False
    assert len(gateway.sent) == 1
    assert "SECRET" not in str(result)


def test_portable_run_entrypoint_has_real_help():
    process = subprocess.run(
        [sys.executable, "-m", "microduck_workshop.agent.run", "--help"],
        text=True,
        capture_output=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert process.returncode == 0, process.stderr
    assert "--tools-file" in process.stdout
    assert "--episode-id" in process.stdout

"""nbformat + real nbclient execution. Dry execution is not hardware acceptance."""
import json
import os
from pathlib import Path
import re

import nbformat
from nbclient import NotebookClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["01_ros2.ipynb", "02_isaac_ros_5.ipynb", "03_microduck_isaac_sim_6_2.ipynb",
         "04_train_isaac_lab_3.ipynb", "05_policy_inference.ipynb", "06_cascade_policy_agent.ipynb"]


def execute(name, mode, replacements=None):
    path = ROOT / "notebooks" / name
    assert path.is_file(), f"Missing actual notebook: {name}"
    notebook = nbformat.read(path, as_version=4)
    for old, new in (replacements or {}).items():
        matches = [cell for cell in notebook.cells if cell.cell_type == "code" and old in cell.source]
        assert len(matches) == 1, f"Ambiguous explicit test opt-in: {old}"
        matches[0].source = matches[0].source.replace(old, new)
    env = dict(os.environ, WORKSHOP_NOTEBOOK_MODE=mode,
               WORKSHOP_NOTEBOOK_WORK=str(ROOT / ".workshop" / f"nbclient-{mode}"))
    client = NotebookClient(notebook, timeout=180, kernel_name="python3",
                            resources={"metadata": {"path": str(ROOT / "notebooks")}})
    output = ROOT / ".workshop/executed" / mode / name
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        client.execute(env=env)
    finally:
        nbformat.write(notebook, output)
    return notebook


@pytest.mark.parametrize("name", NAMES)
def test_public_notebook_schema_teaching_and_clean_output(name):
    path = ROOT / "notebooks" / name
    assert path.is_file(), f"Missing actual notebook: {name}"
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    source = "\n".join(cell.source for cell in notebook.cells)
    for term in ("Objective", "Predict", "Task", "Observe", "Debug", "Cleanup"):
        assert term in source, f"Missing teaching section: {term}"
    code = [c for c in notebook.cells if c.cell_type == "code"]
    assert len(code) >= 5
    for cell in code:
        assert cell.execution_count is None and cell.outputs == []
        compile(cell.source, str(path), "exec")
    assert not re.search(r"/(?:home|Users)/[^/\s\"']+", source), "Public notebook embeds an absolute user-home path"
    assert "import rclpy" not in source and "import isaacsim" not in source


def test_wrong_kernel_is_rejected_before_runtime_imports():
    import subprocess
    import sys
    nb = nbformat.read(ROOT / "notebooks/01_ros2.ipynb", as_version=4)
    bootstrap = next(c.source for c in nb.cells if c.cell_type == "code")
    result = subprocess.run([sys.executable, "-c", "import sys; sys.version_info = (3, 14, 0);\n" + bootstrap],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0, "Wrong notebook kernel must fail before proceeding"
    assert "notebook_setup.sh" in result.stderr


def test_sensor_checkpoint_is_after_image_and_ros_evidence():
    nb = nbformat.read(ROOT / "notebooks/03_microduck_isaac_sim_6_2.ipynb", as_version=4)
    code = [c.source for c in nb.cells if c.cell_type == "code"]
    image_index = next(i for i, s in enumerate(code) if "camera_snapshot(" in s)
    complete_index = next(i for i, s in enumerate(code) if 'session.complete("03"' in s)
    assert complete_index > image_index, "Do not grant03 completion before an actual image"
    assert '"sensor_msgs/msg/Imu"' in code[complete_index]
    assert "artifacts=" in code[complete_index], "Bind the actual camera evidence to the checkpoint"


@pytest.mark.parametrize("name", NAMES)
def test_nbclient_validation_executes_real_safe_cells_and_marks_hardware_skipped(name):
    notebook = execute(name, "validate")
    output = "\n".join(o.get("text", "") for c in notebook.cells
                       if c.cell_type == "code" for o in c.outputs)
    assert "SKIPPED" in output
    assert "PASS" not in output
    assert all(c.execution_count for c in notebook.cells if c.cell_type == "code")


@pytest.mark.skipif(os.environ.get("RUN_NOTEBOOK_ROS") != "1", reason="Real Docker ROS opt-in")
def test_owned_container_identity_and_running_state(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / "notebooks"))
    from workshop import Session
    session = Session(ROOT, work=tmp_path)
    image = os.environ.get("WORKSHOP_ROS_IMAGE", "roscon/microduck-ros5:local")
    session.start("ownership", image, ["sleep", "60"])
    state = session.state()
    actual_id = state["containers"]["ownership"]
    try:
        state["containers"]["ownership"] = "0" * 64
        session.save(state)
        with pytest.raises(RuntimeError, match="ownership"):
            session.stop("ownership")
        state["containers"]["ownership"] = actual_id
        session.save(state)
        assert session.owned("ownership", running=True) == actual_id
        session.run(["docker", "stop", "--time", "3", session.name("ownership")])
        with pytest.raises(RuntimeError, match="running"):
            session.owned("ownership", running=True)
    finally:
        state["containers"]["ownership"] = actual_id
        session.save(state)
        session.stop("ownership")


@pytest.mark.skipif(os.environ.get("RUN_NOTEBOOK_ROS") != "1", reason="Real Docker ROS opt-in")
def test_nbclient_ros_tutorial_actual_pub_sub():
    notebook = execute("01_ros2.ipynb", "cpu")
    output = "\n".join(o.get("text", "") for c in notebook.cells
                       if c.cell_type == "code" for o in c.outputs)
    assert "data: hello from ROS 2" in output
    assert "std_msgs/msg/String" in output
    assert "tutorial_publisher" in output


def test_exactly_six_primary_notebooks_in_required_order():
    assert sorted(path.name for path in (ROOT / "notebooks").glob("[0-9][0-9]_*.ipynb")) == NAMES


def test_sensor_startup_and_prelease_gates_share_configurable_readiness():
    sensor = nbformat.read(ROOT / "notebooks/03_microduck_isaac_sim_6_2.ipynb", as_version=4)
    cells = [c.source for c in sensor.cells if c.cell_type == "code"]
    start = next(s for s in cells if "def start_sensor_episode" in s)
    assert "session.wait_sim(SIM_URL)" in start
    bridge = next(s for s in cells if "def start_and_inspect_robot_ros" in s)
    assert bridge.index("session.wait_sensors(") < bridge.index('session.start("ros"')
    agent = nbformat.read(ROOT / "notebooks/06_cascade_policy_agent.ipynb", as_version=4)
    attempt = next(c.source for c in agent.cells if c.cell_type == "code" and "def run_one_agent_attempt" in c.source)
    assert attempt.index("session.wait_sensors(") < attempt.index("session.claim_attempt(")
    # Never move readiness polling inside an acquired gateway lease.
    assert attempt.index("session.wait_sensors(") < attempt.index('session.start("ros"')


def test_capstone_guards_do_not_substitute_policy_or_adapter():
    notebook = nbformat.read(ROOT / "notebooks/06_cascade_policy_agent.ipynb", as_version=4)
    code = "\n".join(c.source for c in notebook.cells if c.cell_type == "code")
    for term in ("USE_REFERENCE = False", "INSTRUCTOR_RELEASE_APPROVED = False", 'session.selection("04")',
                 'session.selection("05")', "microduck_workshop.agent.run", '"--policy-manifest"',
                 '"--policy-admission"', '"--native-health-url"', "session.claim_attempt", "require_unstopped=False"):
        assert term in code
    attempt = next(c.source for c in notebook.cells if c.cell_type == "code" and "def run_one_agent_attempt" in c.source)
    assert attempt.index('session.get_json(MODEL_URL') < attempt.index('session.start("ros"')
    assert attempt.index("session.claim_attempt") < attempt.index('session.start("ros"')
    assert "velstand.onnx" not in code


@pytest.mark.skipif(os.environ.get("RUN_NOTEBOOK_POLICY_CPU") != "1", reason="Real Docker adapter opt-in")
def test_nbclient_capstone_explicit_reference_runs_actual_cpu_checker(monkeypatch):
    monkeypatch.setenv("WORKSHOP_NOTEBOOK_PREFIX", "roscon-nb-complete")
    monkeypatch.setenv("WORKSHOP_ROS_DOMAIN", "72")
    notebook = execute("06_cascade_policy_agent.ipynb", "adapter-reference", {
        "RUN_ADAPTER_TESTS = False": "RUN_ADAPTER_TESTS = True",
        "USE_REFERENCE = False": "USE_REFERENCE = True",
    })
    output = "\n".join(o.get("text", "") for c in notebook.cells if c.cell_type == "code" for o in c.outputs)
    assert "EXPLICIT INSTRUCTOR REFERENCE" in output
    assert "16 passed" in output
    assert "SKIPPED: single real CASCADE/ROS attempt" in output
    state = json.loads((ROOT / ".workshop/nbclient-adapter-reference/state.json").read_text())
    assert state["adapter"]["kind"] == "EXPLICIT_REFERENCE"
    assert not state.get("containers")

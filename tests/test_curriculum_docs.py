"""Static course checks, not claims that any live-runtime lesson has passed."""

import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT / "docs/labs"
COURSE_FILES = [
    LABS / "README.md", LABS / "00-before-class.md", LABS / "01-ros-basics.md",
    LABS / "02-simulation.md", LABS / "03-reinforcement-learning.md",
    LABS / "04-isaac-ros.md", LABS / "05-cascade.md", LABS / "06-wrap-up.md",
    ROOT / "docs/instructor.md", ROOT / "docs/troubleshooting.md",
    ROOT / "docs/brev.md", ROOT / "docs/capstone.md",
    ROOT / "exercises/ros_basics/README.md", ROOT / "solutions/ros_basics/README.md",
]


def test_all_course_files_exist():
    assert all(path.is_file() for path in COURSE_FILES)


def test_agenda_is_contiguous_and_exactly_120_minutes():
    text = (LABS / "README.md").read_text()
    rows = re.findall(r"\| (\d{2}:\d{2})–(\d{2}:\d{2}) \| (\d+) \|", text)
    assert len(rows) == 7
    assert [int(row[2]) for row in rows] == [15, 20, 20, 20, 15, 25, 5]
    previous = "15:00"
    for start, end, duration in rows:
        assert start == previous
        delta = datetime.strptime(end, "%H:%M") - datetime.strptime(start, "%H:%M")
        assert delta.total_seconds() == int(duration) * 60
        previous = end
    assert previous == "17:00"
    assert sum(int(row[2]) for row in rows) == 120


def test_all_course_relative_links_resolve_within_repository():
    failures = []
    for path in COURSE_FILES:
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
            url = urlsplit(link)
            if url.scheme or link.startswith("#"):
                continue
            target = (path.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(ROOT) or not target.exists():
                failures.append(f"{path.relative_to(ROOT)} -> {link}")
    assert not failures, "Broken links:\n" + "\n".join(failures)


def test_course_relative_markdown_anchors_resolve():
    for path in COURSE_FILES:
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
            url = urlsplit(link)
            if url.scheme or not url.fragment:
                continue
            target = (path.parent / unquote(url.path)).resolve() if url.path else path
            if target.suffix != ".md":
                continue
            headings = re.findall(r"^#+ (.+)$", target.read_text(), re.MULTILINE)
            anchors = {
                re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
                for heading in headings
            }
            assert unquote(url.fragment) in anchors, f"{path.name}: {link}"


def test_each_lab_has_observable_checkpoint_and_timebox():
    for path in COURSE_FILES:
        if path.parent == LABS and path.name != "README.md":
            text = path.read_text()
            assert "## Checkpoint" in text, path.name
            assert "minutes" in text or "Before 15:00" in text, path.name


def test_solution_has_no_exercise_todos_or_motion_writes():
    text = (ROOT / "solutions/ros_basics/joint_watch.py").read_text()
    assert "NotImplementedError" not in text
    assert "create_publisher(" not in text
    assert "create_client(" not in text
    assert "/workshop/microduck/joint_states" in text


def test_reference_policy_lesson_points_to_pinned_contract():
    text = (LABS / "03-reinforcement-learning.md").read_text()
    assert "../../provenance/policy_contract.json" in text
    assert "ONNX" in text and "PPO" in text
    assert "not convergence" in text


def test_numbered_lab_steps_fit_their_timeboxes():
    budgets = {
        "01-ros-basics.md": 20,
        "02-simulation.md": 20,
        "03-reinforcement-learning.md": 20,
        "04-isaac-ros.md": 15,
        "05-cascade.md": 25,
        "06-wrap-up.md": 5,
    }
    for name, budget in budgets.items():
        durations = re.findall(r"^## \d+\. .+ — (\d+) minutes?$", (LABS / name).read_text(), re.MULTILINE)
        assert durations, name
        assert sum(map(int, durations)) == budget, name


def test_all_course_pages_reachable_from_student_index():
    pending = [LABS / "README.md"]
    visited = set()
    course_set = set(COURSE_FILES)
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
            url = urlsplit(link)
            if url.scheme or not url.path:
                continue
            target = (path.parent / unquote(url.path)).resolve()
            if target in course_set:
                pending.append(target)
    assert course_set <= visited, sorted(str(path.relative_to(ROOT)) for path in course_set - visited)


def test_course_bash_examples_parse_without_executing_them():
    """Check copy/paste syntax only; never start Docker, a model, GPU or cloud job."""
    checked = 0
    for path in COURSE_FILES:
        blocks = re.findall(
            r"^[ \t]*```bash\n(.*?)^[ \t]*```", path.read_text(), re.MULTILINE | re.DOTALL
        )
        for number, block in enumerate(blocks, start=1):
            result = subprocess.run(
                ["bash", "-n"], input=block, text=True, capture_output=True, check=False
            )
            assert result.returncode == 0, f"{path.name} block {number}: {result.stderr}"
            checked += 1
    assert checked > 20


def test_classroom_teaches_fixed_step_not_numeric_velocity_task():
    text = (LABS / "05-cascade.md").read_text()
    assert "microduck.step_forward" in text
    assert "step-forward-v1" in text
    assert "1.0 second" in text and "2.0-second" in text
    assert "0.05 m/s" not in text
    assert "calibration remains FAILED / NOT_READY" in text
    assert "one attempt per episode" in text
    assert "--tools-file /opt/workshop/exercises/capstone/tools.py" in text
    assert "--workdir /opt/workshop" in text
    assert "--max-steps 6" in text


def test_instructor_preparation_and_student_cpu_environment_agree():
    setup = (ROOT / "docs/brev.md").read_text()
    assert "python3.12 -m venv .workshop/student-venv" in setup
    assert "--accept-nvidia-eula --accept-mesh-license" in setup
    for name in ["00-before-class.md", "01-ros-basics.md", "05-cascade.md"]:
        assert ".workshop/student-venv/bin/python" in (LABS / name).read_text()
    for name in ["README.md", "00-before-class.md"]:
        assert "Aula 2-7" in (LABS / name).read_text()
    assert "Aula 2-7" in (ROOT / "docs/instructor.md").read_text()


def test_detector_parameter_matches_launch_and_live_scene():
    launch = (ROOT / "ros_ws/src/microduck_gateway/launch/apriltag.launch.py").read_text()
    compose = (ROOT / "compose.yaml").read_text()
    assert "'size': ParameterValue(LaunchConfiguration('tag_size')" in launch
    assert '"tag_size:=0.20"' in compose
    for path in [LABS / "04-isaac-ros.md", ROOT / "docs/brev.md"]:
        text = path.read_text()
        assert "ros2 param get /workshop/microduck/apriltag size" in text
        assert "ros2 param get /workshop/microduck/apriltag tag_size" not in text


def test_model_and_episode_lifecycle_are_explicit():
    for path in [LABS / "03-reinforcement-learning.md", LABS / "05-cascade.md",
                 ROOT / "docs/brev.md", ROOT / "docs/capstone.md"]:
        text = path.read_text()
        assert "MODEL_GPU=0 MODEL_PORT=8080 bash scripts/model_start.sh" in text
        assert "brev_start.sh --accept-nvidia-eula" in text
    text = (ROOT / "docs/brev.md").read_text()
    assert "--step-profile step-forward-v1" in text
    assert "`0` is not infinite" not in text
    assert "no unvalidated `step-forward-v1` profile is enabled" not in text
    assert "only the ROS container's private IPC namespace" in text


def test_course_links_to_preserved_failures_and_distinct_evidence():
    text = (ROOT / "docs/capstone.md").read_text()
    for target in ["step.md", "calibration.md", "local_model.md", "runtime.md",
                   "../solutions/capstone/evidence/README.md"]:
        assert f"]({target})" in text
    assert "No Brev VM or L40S execution is established" in text
    assert "same actual episode and request" in text
    assert '"$PWD/solutions:/opt/workshop/solutions:ro"' in text

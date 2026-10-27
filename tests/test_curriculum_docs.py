"""Static course checks, not claims that any live-runtime lesson has passed."""

from datetime import datetime
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT / "docs/labs"
COURSE_FILES = [
    LABS / "README.md", LABS / "00-before-class.md", LABS / "01-ros-basics.md",
    LABS / "02-simulation.md", LABS / "03-reinforcement-learning.md",
    LABS / "04-isaac-ros.md", LABS / "05-cascade.md", LABS / "06-wrap-up.md",
    ROOT / "docs/instructor.md", ROOT / "docs/troubleshooting.md",
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
        durations = re.findall(r"^## \d+\. .+ — (\d+) minutes?$", (LABS / name).read_text(), re.M)
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

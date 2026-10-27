import subprocess
from types import SimpleNamespace

import pytest

from microduck_workshop import doctor
from microduck_workshop.doctor import evaluate_version_pins


def git(root, *args):
    return subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=CPU fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def lab_checkout(tmp_path, monkeypatch):
    """Real Git integrity fixtures, not evidence of an installed GA runtime."""
    root = tmp_path / "lab"
    package = root / "source/isaaclab/isaaclab"
    package.mkdir(parents=True)
    origin = package / "__init__.py"
    origin.write_text("# fixture package\n")
    (package / "module.py").write_text("VALUE = 'fixture'\n")
    (root / ".gitignore").write_text("__pycache__/\nignored.py\n")
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-qm", "CPU source fixture")
    fixture_commit = git(root, "rev-parse", "HEAD")
    monkeypatch.setattr(doctor, "LAB_GA_COMMIT", fixture_commit)
    installed = {"isaacsim": "6.2.0.0", "isaaclab": "37.2.0", "newton": "1.6.1"}
    monkeypatch.setattr(doctor.importlib.metadata, "version", lambda name: installed.get(name))
    monkeypatch.setattr(
        doctor.importlib.util, "find_spec", lambda name: SimpleNamespace(origin=str(origin))
    )
    monkeypatch.setenv("ROS_DISTRO", "lyrical")
    ros = tmp_path / "ros"
    xml = ros / "share/isaac_ros_apriltag/package.xml"
    xml.parent.mkdir(parents=True)
    xml.write_text("<package><version>5.0.0</version></package>")
    original_command = doctor.command

    def fixture_command(args):
        if args[0] == "git":
            return original_command(args)
        if args == ["ros2", "pkg", "prefix", "isaac_ros_apriltag"]:
            return str(ros)
        return None  # Never invoke GPU/SDK tools in CPU fixtures.

    monkeypatch.setattr(doctor, "command", fixture_command)
    return root, origin


@pytest.mark.parametrize(
    "mutation",
    [
        "edited_init",
        "edited_module",
        "staged_module",
        "deleted_module",
        "untracked_module",
        "ignored_module",
        "shadow_package",
        "untracked_init",
        "assume_unchanged",
        "skip_worktree",
        "symlink_module",
    ],
)
def test_inspect_environment_rejects_nonpinned_source(lab_checkout, monkeypatch, mutation):
    root, origin = lab_checkout
    module = origin.parent / "module.py"
    if mutation == "edited_init":
        origin.write_text("# edited source\n")
    elif mutation in {"edited_module", "staged_module", "assume_unchanged", "skip_worktree"}:
        if mutation in {"assume_unchanged", "skip_worktree"}:
            git(
                root,
                "update-index",
                "--" + mutation.replace("_", "-"),
                "source/isaaclab/isaaclab/module.py",
            )
        module.write_text("VALUE = 'edited'\n")
        if mutation == "staged_module":
            git(root, "add", str(module))
    elif mutation == "deleted_module":
        module.unlink()
    elif mutation in {"untracked_module", "ignored_module"}:
        (origin.parent / ("ignored.py" if mutation == "ignored_module" else "extra.py")).write_text(
            "# extra importable code\n"
        )
    elif mutation == "shadow_package":
        shadow = root / "shadow/isaaclab/__init__.py"
        shadow.parent.mkdir(parents=True)
        shadow.write_text("# shadow package\n")
        monkeypatch.setattr(
            doctor.importlib.util, "find_spec", lambda name: SimpleNamespace(origin=str(shadow))
        )
    elif mutation == "untracked_init":
        git(root, "rm", "--cached", str(origin))
        git(root, "commit", "-qm", "Remove package from fixture tree")
        monkeypatch.setattr(doctor, "LAB_GA_COMMIT", git(root, "rev-parse", "HEAD"))
    elif mutation == "symlink_module":
        outside = root.parent / "module.py"
        outside.write_bytes(module.read_bytes())
        module.unlink()
        module.symlink_to(outside)
    report = doctor.inspect_environment(root)
    assert report["version_checks"]["isaac_lab_ga_source"] is False
    assert report["version_checks"]["version_pins_match"] is False
    assert report["version_checks"]["runtime_exercised"] is False


@pytest.mark.parametrize("corrupt", [False, True])
def test_inspect_environment_verifies_hydrated_lfs_bytes(lab_checkout, monkeypatch, corrupt):
    import hashlib

    root, origin = lab_checkout
    asset = origin.parent / "fixture.usd"
    data = b"CPU fixture for hydrated LFS data, not a real USD asset"
    pointer = (
        "version https://git-lfs.github.com/spec/v1\n"
        f"oid sha256:{hashlib.sha256(data).hexdigest()}\nsize {len(data)}\n"
    )
    asset.write_text(pointer)
    git(root, "add", str(asset))
    git(root, "commit", "-qm", "Add fixture LFS pointer")
    monkeypatch.setattr(doctor, "LAB_GA_COMMIT", git(root, "rev-parse", "HEAD"))
    asset.write_bytes(b"x" * len(data) if corrupt else data)
    report = doctor.inspect_environment(root)
    assert report["version_checks"]["isaac_lab_ga_source"] is (not corrupt)
    assert report["version_checks"]["runtime_exercised"] is False


def test_inspect_environment_accepts_clean_tracked_fixture_not_runtime(lab_checkout):
    root, origin = lab_checkout
    # Ordinary interpreter bytecode must not make clean source unusable.
    cache = origin.parent / "__pycache__"
    cache.mkdir()
    (cache / "module.cpython-312.pyc").write_bytes(b"fixture bytecode, not executed")
    metadata = origin.parent.parent / "isaaclab.egg-info"
    metadata.mkdir()
    (metadata / "PKG-INFO").write_text("Generated editable-install metadata\n")
    report = doctor.inspect_environment(root)
    assert report["status"] == "INSPECTED"
    assert report["version_checks"]["version_pins_match"] is True
    assert report["version_checks"]["runtime_exercised"] is False


GA = "e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4"


def test_dev_package_number_is_not_an_isaaclab_release():
    report = evaluate_version_pins(
        {
            "isaacsim": "6.2.0.0",
            "isaac_ros_apriltag": "5.0.0",
            "isaaclab": "37.2.0",
            "newton": "1.6.1",
        },
        None,
        False,
        "lyrical",
    )
    assert report["isaac_lab_ga_source"] is False
    assert report["version_pins_match"] is False
    assert report["runtime_exercised"] is False


def test_matching_pins_still_do_not_claim_runtime_execution():
    report = evaluate_version_pins(
        {
            "isaacsim": "6.2.0.0",
            "isaac_ros_apriltag": "5.0.0",
            "isaaclab": "37.2.0",
            "newton": "1.6.1",
        },
        GA,
        True,
        "lyrical",
    )
    assert report["version_pins_match"] is True
    assert report["runtime_exercised"] is False


def test_old_ros_and_wrong_import_origin_fail_preflight():
    report = evaluate_version_pins(
        {"isaacsim": "6.2.0.0", "isaac_ros_apriltag": "5.0.0", "newton": "1.6.1"}, GA, True, "jazzy"
    )
    assert report["ros_lyrical"] is False
    report = evaluate_version_pins(
        {"isaacsim": "6.2.0.0", "isaac_ros_apriltag": "5.0.0", "newton": "1.6.1"},
        GA,
        False,
        "lyrical",
    )
    assert report["version_pins_match"] is False


def test_rc_or_old_sim_is_not_silently_relabelled_ga():
    for version in ["6.1.0.0", "6.2.0-rc.14", None]:
        report = evaluate_version_pins(
            {"isaacsim": version, "newton": "1.6.1"}, GA, True, "lyrical"
        )
        assert report["isaac_sim_62_wheel"] is False

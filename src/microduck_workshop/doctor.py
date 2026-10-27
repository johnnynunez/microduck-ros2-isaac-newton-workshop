"""Inspect configuration and actual import locations, without pretending to exercise a robot."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

LAB_GA_COMMIT = "e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4"
# Confirmed in the public tree at LAB_GA_COMMIT, not inferred from containment.
LAB_PACKAGE_INIT = Path("source/isaaclab/isaaclab/__init__.py")


def evaluate_version_pins(
    installed: dict, lab_commit: str | None, origin_matches: bool, ros_distro: str | None
) -> dict:
    checks = {
        "isaac_sim_62_wheel": installed.get("isaacsim") == "6.2.0.0",
        "isaac_lab_ga_source": lab_commit == LAB_GA_COMMIT and origin_matches,
        "newton_ga": installed.get("newton") == "1.6.1",
        "ros_lyrical": ros_distro == "lyrical",
        "isaac_ros_50": installed.get("isaac_ros_apriltag") == "5.0.0",
    }
    return {**checks, "version_pins_match": all(checks.values()), "runtime_exercised": False}


def command(args: list[str]) -> str | None:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _lab_source_matches(root: Path, origin: Path | None, commit: str | None) -> bool:
    """Check source bytes against Git objects, independent of index trust flags."""
    root = root.resolve()
    if commit != LAB_GA_COMMIT or origin != root / LAB_PACKAGE_INIT:
        return False
    git = ["git", "--no-replace-objects", "-C", str(root)]
    if command([*git, "rev-parse", "--show-toplevel"]) != str(root):
        return False
    tree = command([*git, "ls-tree", "-rz", "--full-tree", commit, "--", "source"])
    if not tree:
        return False
    tracked = set()
    try:
        for record in tree.rstrip("\0").split("\0"):
            metadata, name = record.split("\t", 1)
            mode, kind, expected = metadata.split()
            path = root / name
            if mode not in {"100644", "100755"} or kind != "blob" or not path.is_file():
                return False
            # Reject symlinked files and parent directories even when bytes match.
            if path.is_symlink():
                return False
            relative = path.relative_to(root)
            if any((root / parent).is_symlink() for parent in relative.parents):
                return False
            size = path.stat().st_size
            digest = hashlib.sha1(f"blob {size}\0".encode(), usedforsecurity=False)
            content_digest = hashlib.sha256()
            with path.open("rb") as source:
                while block := source.read(1 << 16):
                    digest.update(block)
                    content_digest.update(block)
            if digest.hexdigest() != expected:
                # GA tracks LFS assets. Verify hydrated bytes against the pinned
                # pointer without invoking configurable Git clean filters.
                object_size = command([*git, "cat-file", "-s", expected])
                if object_size is None or not 0 < int(object_size) <= 1024:
                    return False
                pointer = command([*git, "cat-file", "blob", expected])
                lfs = re.fullmatch(
                    r"version https://git-lfs.github.com/spec/v1\n"
                    r"oid sha256:([0-9a-f]{64})\nsize ([0-9]+)",
                    pointer or "",
                )
                if not lfs or int(lfs[2]) != size or lfs[1] != content_digest.hexdigest():
                    return False
            tracked.add(relative)
        if LAB_PACKAGE_INIT not in tracked:
            return False
        # Inspect the filesystem, not just `git status`: ignored/staged additions
        # can introduce importable code without appearing as untracked changes.
        for path in (root / "source").rglob("*"):
            if path.is_symlink():
                return False
            if path.is_dir() or path.relative_to(root) in tracked:
                continue
            if path.parent.name == "__pycache__" and path.suffix == ".pyc":
                continue  # Source inspection is not bytecode/runtime attestation.
            if path.parent.name.endswith(".egg-info") and path.name in {
                "PKG-INFO",
                "SOURCES.txt",
                "dependency_links.txt",
                "entry_points.txt",
                "requires.txt",
                "top_level.txt",
            }:
                continue
            return False
    except (OSError, ValueError):
        return False
    return True


def inspect_environment(lab_root: Path | None = None) -> dict:
    installed = {}
    for name in (
        "isaacsim",
        "isaaclab",
        "newton",
        "mujoco-warp",
        "warp-lang",
        "torch",
        "onnxruntime",
    ):
        try:
            installed[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed[name] = None
    ros_prefix = command(["ros2", "pkg", "prefix", "isaac_ros_apriltag"])
    installed["isaac_ros_apriltag"] = None
    if ros_prefix:
        package = Path(ros_prefix) / "share/isaac_ros_apriltag/package.xml"
        try:
            installed["isaac_ros_apriltag"] = ET.parse(package).findtext("version")
        except (OSError, ET.ParseError):
            pass
    spec = importlib.util.find_spec("isaaclab")
    origin = Path(spec.origin).resolve() if spec is not None and spec.origin else None
    commit = command(["git", "-C", str(lab_root), "rev-parse", "HEAD"]) if lab_root else None
    origin_matches = bool(lab_root and _lab_source_matches(lab_root, origin, commit))
    pins = evaluate_version_pins(installed, commit, origin_matches, os.environ.get("ROS_DISTRO"))
    gpu = command(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total",
            "--format=csv,noheader,nounits",
        ]
    )
    return {
        "status": "INSPECTED",
        "python": platform.python_version(),
        "python_supported": sys.version_info[:2] == (3, 12),
        "platform": platform.platform(),
        "packages_in_this_interpreter": installed,
        "isaaclab_source_commit": commit,
        "isaaclab_import_origin": str(origin) if origin else None,
        "isaaclab_source_integrity": origin_matches,
        "isaaclab_source_integrity_scope": "Expected tracked package origin and source/ tree bytes; excludes generated bytecode, egg-info metadata, dependencies and runtime state.",
        "ros_distro": os.environ.get("ROS_DISTRO"),
        "gpu_inventory": gpu,
        "docker_command_available": shutil.which("docker") is not None,
        "version_checks": pins,
        "scope": "Configuration/import-origin inspection only; no simulator, ROS graph, inference or policy motion was executed. Separate processes may have different environments.",
        "next_gate": "Use the actual runtime and end-to-end acceptance receipts before declaring the workshop ready.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--isaaclab-root",
        type=Path,
        default=Path(os.environ["ISAACLAB_ROOT"]) if os.environ.get("ISAACLAB_ROOT") else None,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail unless all version/import pins match in THIS process",
    )
    args = parser.parse_args()
    report = inspect_environment(args.isaaclab_root)
    print(json.dumps(report, indent=2))
    matched = report["python_supported"] and report["version_checks"]["version_pins_match"]
    return 2 if args.strict and not matched else 0


if __name__ == "__main__":
    raise SystemExit(main())

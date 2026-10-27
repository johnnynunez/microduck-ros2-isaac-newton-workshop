"""Run CPU-only student checks. Passing is not ROS, model or physical evidence."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-file", type=Path, default=root / "exercises/capstone/tools.py")
    args = parser.parse_args()
    if not args.tools_file.is_file():
        parser.error("tools file does not exist")
    print("CPU fixtures only; not Isaac ROS, local model, Newton or physical success.", flush=True)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(root / "tests/test_agent_exercise_contract.py")],
        cwd=root,
        env={**os.environ, "CAPSTONE_TOOLS_FILE": str(args.tools_file.resolve())},
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())

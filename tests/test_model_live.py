"""Opt-in tests of REAL compiled CUDA artifacts and REAL CASCADE model inference.

MODEL_LIVE_TEST=1 enables these; they never substitute model responses.
Run in the pinned CASCADE Python environment with PYTHONPATH=src.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    os.environ.get("MODEL_LIVE_TEST") != "1", reason="real CUDA/model opt-in"
)


def test_compiled_binary_identifies_the_pinned_source():
    manifest = json.loads((ROOT / "provenance/local_model.json").read_text())
    cache = Path(os.environ.get("MODEL_CACHE", ROOT / ".workshop/model-cache"))
    revision = manifest["llama_cpp"]["revision"]
    result = subprocess.run(
        [str(cache / f"build-{revision}/bin/llama-server"), "--version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert revision in result.stdout + result.stderr
    config = (cache / f"build-{revision}/CMakeCache.txt").read_text()
    assert f"GGML_BUILD_COMMIT:STRING={revision}" in config
    assert not (cache / f"build-{revision}/tools/ui/dist/index.html").exists()
    import ctypes

    library = ctypes.CDLL(str(cache / f"build-{revision}/bin/libggml-base.so"))
    library.ggml_commit.restype = ctypes.c_char_p
    assert library.ggml_commit().decode() in {revision, revision[:7], "unknown"}


def test_real_cascade_three_turn_stop_diagnostic(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/agent_model_probe.py"),
            "--base-url",
            os.environ.get("MODEL_LIVE_URL", "http://127.0.0.1:18511/v1"),
            "--model",
            "qwen3.8-27b",
            "--out",
            str(tmp_path / "probe"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=210,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path / "probe/result.json").read_text())
    assert data["provider_requests"] == 3
    assert data["physical_success"] is False
    assert data["ros_integration"] is False
    assert [row["tool"] for row in data["report"]["tool_log"]] == [
        "microduck.observe",
        "microduck.verify",
        "task_done",
    ]

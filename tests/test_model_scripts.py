"""Portable model lifecycle contracts; unit tests never download or run inference."""

import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_script(name, *args, **env):
    return subprocess.run(
        ["bash", str(ROOT / "scripts" / name), *args],
        check=False,
        env={**os.environ, **env},
        text=True,
        capture_output=True,
        timeout=15,
    )


def test_setup_plan_is_pinned_and_bounded_without_side_effects(tmp_path):
    cache = tmp_path / "cache"
    result = run_script("model_setup.sh", "--plan", MODEL_CACHE=str(cache))
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["cuda_architectures"] == ["89", "120"]
    assert 1 <= plan["build_jobs"] <= 8
    assert len(plan["llama_cpp"]["revision"]) == 40
    assert len(plan["model"]["sha256"]) == 64
    assert len(plan["model"]["revision"]) == 40
    assert plan["model"]["repository"] == "unsloth/Qwen3.8-27B-GGUF"
    assert not cache.exists()


def test_setup_rejects_oversubscribed_build_before_creating_cache(tmp_path):
    cache = tmp_path / "cache"
    result = run_script("model_setup.sh", "--plan", MODEL_CACHE=str(cache), MODEL_BUILD_JOBS="9")
    assert result.returncode != 0
    assert "MODEL_BUILD_JOBS must be 1..8" in result.stderr
    assert not cache.exists()


def test_setup_refuses_corrupt_source_without_replacing_it(tmp_path):
    (tmp_path / "source.tar.gz").write_bytes(b"not the pinned upstream source")
    result = run_script("model_setup.sh", "--build-only", MODEL_CACHE=str(tmp_path))
    assert result.returncode != 0
    assert "SHA256 mismatch" in result.stderr
    assert (tmp_path / "source.tar.gz").read_bytes() == b"not the pinned upstream source"


def test_start_plan_is_local_single_gpu_and_bounded(tmp_path):
    result = run_script(
        "model_start.sh", "--plan", MODEL_CACHE=str(tmp_path / "absent"), MODEL_GPU="1"
    )
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    cmd = plan["command"]
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert cmd[cmd.index("--port") + 1] == "18511"
    assert cmd[cmd.index("--ctx-size") + 1] == "4096"
    assert cmd[cmd.index("--parallel") + 1] == "1"
    assert cmd[cmd.index("--alias") + 1] == "qwen3.8-27b"
    assert cmd[cmd.index("--cache-type-k") + 1] == "f16"
    assert "--jinja" in cmd and "--no-context-shift" in cmd
    assert plan["gpu"] == "1"
    assert plan["min_free_vram_mib"] == 24576
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize(
    "key,value",
    [
        ("MODEL_GPU", "0,1"),
        ("MODEL_CONTEXT", "8192"),
        ("MODEL_CONTEXT", "NaN"),
        ("MODEL_PORT", "80"),
        ("MODEL_PORT", "65536"),
    ],
)
def test_start_rejects_unsafe_configuration(key, value, tmp_path):
    result = run_script("model_start.sh", "--plan", MODEL_CACHE=str(tmp_path), **{key: value})
    assert result.returncode != 0
    assert key in result.stderr


def test_start_refuses_occupied_port_before_loading_weights(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        result = run_script(
            "model_start.sh", MODEL_CACHE=str(tmp_path), MODEL_PORT=str(sock.getsockname()[1])
        )
    assert result.returncode != 0
    assert "port is already in use" in result.stderr


def test_start_requires_completed_verified_setup(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    result = run_script("model_start.sh", MODEL_CACHE=str(tmp_path), MODEL_PORT=str(port))
    assert result.returncode != 0
    assert "run model_setup.sh first" in result.stderr


def test_stop_is_idempotent_when_nothing_was_started(tmp_path):
    result = run_script("model_stop.sh", MODEL_CACHE=str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "not running" in result.stdout


def test_stop_never_signals_an_unrelated_pid(tmp_path):
    child = subprocess.Popen(["sleep", "20"])
    try:
        directory = tmp_path / "run"
        directory.mkdir()
        (directory / "server.json").write_text(
            json.dumps(
                {
                    "pid": child.pid,
                    "start_ticks": "0",
                    "executable": "/usr/bin/sleep",
                    "port": 18511,
                }
            )
        )
        result = run_script("model_stop.sh", MODEL_CACHE=str(tmp_path))
        assert result.returncode != 0
        assert "identity mismatch" in result.stderr
        assert child.poll() is None
    finally:
        child.terminate()
        child.wait(timeout=5)


def test_download_uses_resumable_bounded_retries(tmp_path):
    # Command recorder only: deliberately fails, produces no weights or fake model response.
    tool = tmp_path / "curl"
    tool.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" > "$CURL_ARGS"\nexit 86\n')
    tool.chmod(0o755)
    output = tmp_path / "curl-args"
    result = run_script(
        "model_setup.sh",
        "--download-only",
        MODEL_CACHE=str(tmp_path / "cache"),
        PATH=f"{tmp_path}:{os.environ['PATH']}",
        CURL_ARGS=str(output),
    )
    assert result.returncode != 0
    args = output.read_text().splitlines()
    assert args[0] == "--disable"  # Do not inherit ~/.curlrc credentials or extra URLs.
    assert "--retry-all-errors" in args
    assert "--http1.1" in args
    assert args[args.index("--max-time") + 1] == "3600"
    assert args[args.index("--continue-at") + 1] == "-"
    assert args[args.index("--proto-redir") + 1] == "=https"


def test_setup_refuses_to_modify_a_running_servers_cache(tmp_path):
    import fcntl

    run = tmp_path / "run"
    run.mkdir()
    (tmp_path / "source.tar.gz").write_bytes(b"must not reach archive validation")
    with (run / "server.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = run_script("model_setup.sh", "--build-only", MODEL_CACHE=str(tmp_path))
    assert result.returncode != 0
    assert "stop the model before setup" in result.stderr

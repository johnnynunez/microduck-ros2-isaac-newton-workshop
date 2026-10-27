"""Secure notebook launcher contract; setup stays outside ROS / Kit environments."""
import json
import os
from pathlib import Path
import subprocess
import shlex
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def launcher_checkout(tmp_path):
    """Use the real test interpreter/Jupyter, never a prepared repository venv."""
    checkout = tmp_path / "checkout"
    (checkout / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/notebook_start.sh", checkout / "scripts/notebook_start.sh")
    python = checkout / ".workshop/notebook-venv/bin/python"
    python.parent.mkdir(parents=True)
    # A Python symlink here would lose sys.executable's venv/installed packages.
    python.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + ' "$@"\n')
    python.chmod(0o700)
    return checkout


def test_launcher_keeps_loopback_auth_and_private_config(tmp_path, launcher_checkout):
    import socket
    launcher = launcher_checkout / "scripts/notebook_start.sh"
    assert launcher.is_file(), "Notebook launcher missing"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, WORKSHOP_NOTEBOOK_RUNTIME=str(tmp_path), WORKSHOP_NOTEBOOK_PORT=str(port))
    result = subprocess.run(["bash", str(launcher), "--check"], cwd=tmp_path,
                            env=env, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    path = tmp_path / "jupyter_server_config.json"
    config = json.loads(path.read_text())
    assert config["ServerApp"]["ip"] == "127.0.0.1"
    assert config["ServerApp"]["open_browser"] is False
    assert config["ServerApp"]["port"] == port
    assert config["ServerApp"]["port_retries"] == 0
    assert config["ServerApp"]["root_dir"] == str(launcher_checkout)
    token = config["IdentityProvider"]["token"]
    assert len(token) >= 32 and token not in result.stdout + result.stderr
    assert path.stat().st_mode & 0o077 == 0


def test_launcher_does_not_overwrite_token_when_port_is_occupied(tmp_path, launcher_checkout):
    import socket
    launcher = launcher_checkout / "scripts/notebook_start.sh"
    old = tmp_path / "jupyter_server_config.json"
    old.write_text("existing private config")
    tmp_path.chmod(0o755)
    old.chmod(0o644)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        env = dict(os.environ, WORKSHOP_NOTEBOOK_RUNTIME=str(tmp_path),
                   WORKSHOP_NOTEBOOK_PORT=str(sock.getsockname()[1]))
        result = subprocess.run(["bash", str(launcher), "--check"], env=env,
                                capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert "Notebook port occupied" in result.stderr
    assert old.read_text() == "existing private config"
    assert tmp_path.stat().st_mode & 0o777 == 0o755
    assert old.stat().st_mode & 0o777 == 0o644


def test_launcher_tightens_existing_runtime_and_log(tmp_path, launcher_checkout):
    import socket
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o755)
    log = runtime / "server.log"
    log.write_text("retained prior log")
    log.chmod(0o644)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    result = subprocess.run(["bash", str(launcher_checkout / "scripts/notebook_start.sh"), "--check"],
                            env=dict(os.environ, WORKSHOP_NOTEBOOK_RUNTIME=str(runtime), WORKSHOP_NOTEBOOK_PORT=str(port)),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert runtime.stat().st_mode & 0o777 == 0o700
    assert log.stat().st_mode & 0o777 == 0o600
    assert log.read_text() == "retained prior log"


def test_launcher_refuses_linked_runtime_without_chmod_external_directory(tmp_path, launcher_checkout):
    outside = tmp_path / "external"
    outside.mkdir(mode=0o755)
    runtime = tmp_path / "runtime-link"
    runtime.symlink_to(outside, target_is_directory=True)
    result = subprocess.run(["bash", str(launcher_checkout / "scripts/notebook_start.sh"), "--check"],
                            env=dict(os.environ, WORKSHOP_NOTEBOOK_RUNTIME=str(runtime)),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert "symlink" in result.stderr
    assert outside.stat().st_mode & 0o777 == 0o755
    assert list(outside.iterdir()) == []


def test_real_jupyter_server_requires_token(tmp_path, launcher_checkout):
    import socket
    import time
    from urllib.error import HTTPError, URLError
    from urllib.request import ProxyHandler, Request, build_opener
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, WORKSHOP_NOTEBOOK_RUNTIME=str(tmp_path), WORKSHOP_NOTEBOOK_PORT=str(port),
               JUPYTER_CONFIG_DIR=str(tmp_path / "user-config"), JUPYTER_NO_CONFIG="1")
    opener = build_opener(ProxyHandler({}))
    process = subprocess.Popen(["bash", str(launcher_checkout / "scripts/notebook_start.sh")],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 30
        url = f"http://127.0.0.1:{port}/api/status"
        while time.monotonic() < deadline:
            assert process.poll() is None, "Jupyter exited before readiness"
            try:
                opener.open(url, timeout=1)
            except HTTPError as exc:
                assert exc.code in (401, 403)
                unauthenticated_status = exc.code
                break
            except URLError:
                time.sleep(.2)
            else:
                raise AssertionError("Unauthenticated Jupyter API was exposed")
        else:
            raise AssertionError("Jupyter readiness deadline exceeded")
        config = json.loads((tmp_path / "jupyter_server_config.json").read_text())
        token = config["IdentityProvider"]["token"]
        with opener.open(Request(url, headers={"Authorization": "token " + token}), timeout=3) as response:
            assert response.status == 200
            assert "started" in json.load(response)
        # The real server log may redact its URL. Exercise the user's private
        # retrieval command without printing the secret or changing config.
        private = subprocess.run(["bash", str(launcher_checkout / "scripts/notebook_start.sh"), "--url"],
                                 env=env, capture_output=True, text=True, timeout=5)
        assert private.returncode == 0, "Private URL retrieval failed"
        from urllib.parse import parse_qs, urlsplit
        local = urlsplit(private.stdout.strip())
        if local.scheme != "http" or local.netloc != f"127.0.0.1:{port}" or local.path != "/lab":
            raise AssertionError("Private URL is not the configured loopback lab")
        if parse_qs(local.query).get("token") != [token]:
            raise AssertionError("Private URL does not preserve configured token")
        with opener.open(url + "?" + local.query, timeout=3) as response:
            assert response.status == 200
        if json.loads((tmp_path / "jupyter_server_config.json").read_text()) != config:
            raise AssertionError("Reading the URL must not rotate the live server's config/token")
        print(f"Real Jupyter HTTP: unauthenticated={unauthenticated_status}; token-header=200; private-URL=200; token unchanged (not printed)")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_setup_is_separate_and_does_not_source_ros_or_disable_auth():
    path = ROOT / "scripts/notebook_setup.sh"
    assert path.is_file(), "Notebook setup missing"
    source = path.read_text()
    assert ".workshop/notebook-venv" in source
    assert "requirements-notebooks.txt" in source
    assert "/opt/ros" not in source and "sudo" not in source
    result = subprocess.run(["bash", "-n", str(path)], capture_output=True, timeout=5)
    assert result.returncode == 0

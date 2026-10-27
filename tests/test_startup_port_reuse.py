"""Actual localhost TCP lifecycle checks; never launches a robot or container."""

import errno
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_startup_port_check(port):
    script = (ROOT / "scripts/sim_start.sh").read_text()
    code = script.split("python3 - <<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    assert code.count("8766") == 1
    # Exercise the exact production preflight with only its bind port relocated.
    return subprocess.run(
        [sys.executable, "-c", code.replace("8766", str(port))],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )


@pytest.mark.skipif(sys.platform != "linux", reason="Brev/Linux TCP TIME_WAIT regression")
def test_startup_preflight_accepts_reusable_port_after_server_active_close():
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            connection, _ = listener.accept()
            # Active close by the server leaves its local port in TIME_WAIT.
            connection.close()
            assert client.recv(1) == b""
    with socket.socket() as plain:
        with pytest.raises(OSError) as error:
            plain.bind(("127.0.0.1", port))
        assert error.value.errno == errno.EADDRINUSE
    result = run_startup_port_check(port)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("listener_reuse", [False, True])
def test_startup_preflight_still_rejects_an_actual_listener(listener_reuse):
    with socket.socket() as listener:
        if listener_reuse:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        result = run_startup_port_check(port)
        assert result.returncode != 0
        assert "Address already in use" in result.stderr
        # The check did not close, commandeer or replace the existing listener.
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            connection, _ = listener.accept()
            with connection:
                connection.sendall(b"owned")
                assert client.recv(5) == b"owned"

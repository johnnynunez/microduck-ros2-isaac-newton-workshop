#!/usr/bin/env bash
# Loopback + token authentication; no browser launch, no public listener.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.workshop/notebook-venv/bin/python"
[[ -x "$PYTHON" ]] || { printf '%s\n' 'Run bash scripts/notebook_setup.sh first.' >&2; exit 2; }
[[ $# == 0 || ( $# == 1 && ( $1 == --check || $1 == --url ) ) ]] || { printf '%s\n' 'Usage: notebook_start.sh [--check|--url]' >&2; exit 2; }
RUNTIME="${WORKSHOP_NOTEBOOK_RUNTIME:-$ROOT/.workshop/jupyter}"
export WORKSHOP_ROOT="$ROOT"
CONFIG="$RUNTIME/jupyter_server_config.json"
if [[ "${1:-}" == --url ]]; then
  # Explicit private-terminal action only; never put this output in shared logs.
  exec "$PYTHON" - "$CONFIG" <<'PY'
import json, os, stat, sys
from pathlib import Path
from urllib.parse import urlencode
path = Path(sys.argv[1])
if path.is_symlink() or not path.is_file():
    raise SystemExit('Start the notebook server first; private config is missing or linked')
info = path.stat()
if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
    raise SystemExit('Refusing a config that is not owned and mode 0600')
config = json.loads(path.read_text())
server, token = config['ServerApp'], config['IdentityProvider']['token']
if server['ip'] != '127.0.0.1' or not 1024 <= server['port'] <= 65535 or not isinstance(token, str) or len(token) < 32:
    raise SystemExit('Refusing invalid loopback/auth configuration')
print('http://127.0.0.1:' + str(server['port']) + '/lab?' + urlencode({'token': token}))
PY
fi
"$PYTHON" - "$ROOT" "$RUNTIME" <<'PY'
import json, os, secrets, stat, sys
from pathlib import Path
root, directory = map(Path, sys.argv[1:])
if directory.is_symlink():
    raise SystemExit('Notebook runtime symlink refused; external directory left untouched')
port = int(os.environ.get('WORKSHOP_NOTEBOOK_PORT', '8888'))
if not 1024 <= port <= 65535:
    raise SystemExit('WORKSHOP_NOTEBOOK_PORT must be 1024..65535')
import socket
with socket.socket() as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(('127.0.0.1', port))
    except OSError:
        raise SystemExit('Notebook port occupied; existing server/config left untouched')
# Only our explicitly selected leaf/files, never recursive chmod or external links.
# Do this AFTER the port check: an occupied server's state is not ours to alter.
directory.mkdir(parents=True, exist_ok=True, mode=0o700)
if directory.stat().st_uid != os.geteuid():
    raise SystemExit('Notebook runtime is not owned by this user')
path = directory / 'jupyter_server_config.json'
log = directory / 'server.log'
for target in (path, log):
    if target.is_symlink():
        raise SystemExit('Notebook runtime file symlink refused')
    if target.exists():
        info = target.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
            raise SystemExit('Notebook runtime file must be an owned unlinked regular file')
directory.chmod(0o700)
log.touch(exist_ok=True)
log.chmod(0o600)
config = {
    'ServerApp': {'ip': '127.0.0.1', 'port': port, 'port_retries': 0,
                  'open_browser': False, 'root_dir': str(root), 'allow_remote_access': False},
    'IdentityProvider': {'token': secrets.token_urlsafe(32)},
    'FileContentsManager': {'delete_to_trash': False},
}
path.write_text(json.dumps(config, indent=2))
path.chmod(0o600)
print(f'Notebook listener: 127.0.0.1:{port}; token enabled; no public access.')
print('Private token/config and server log stay in the configured runtime directory.')
PY
if [[ "${1:-}" == --check ]]; then
  exit 0
fi
printf '%s\n' 'Jupyter is foreground-supervised. In a second PRIVATE terminal run: bash scripts/notebook_start.sh --url' 'That command reads the mode-0600 config; do not paste its secret URL into chat, screenshots or shared logs.'
exec "$PYTHON" -m jupyterlab --config="$CONFIG" > "$RUNTIME/server.log" 2>&1

#!/usr/bin/env bash
# Small host environment only; never install into the ROS or simulator interpreter.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.workshop/notebook-venv"
command -v uv >/dev/null || { printf '%s\n' 'uv is required; ask staff to prepare the host.' >&2; exit 2; }
if [[ ! -x "$VENV/bin/python" ]]; then
  uv venv --python 3.12 "$VENV"
fi
"$VENV/bin/python" -c 'import sys; assert sys.version_info[:2] == (3,12), "Use a clean Python 3.12 notebook environment"'
uv pip install --python "$VENV/bin/python" -r "$ROOT/requirements-notebooks.txt"
"$VENV/bin/python" -m ipykernel install --prefix "$VENV" --name python3 --display-name 'MicroDuck notebooks (host only)'
"$VENV/bin/python" -c 'import nbformat, nbclient, jupyterlab; print("Host notebook dependencies imported; hardware NOT tested")'
printf '%s\n' 'Setup complete. Start with bash scripts/notebook_start.sh; keep the private token local.'
